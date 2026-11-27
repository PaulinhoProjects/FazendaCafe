"""
Supervisor do servidor Kaldi: inicia/para/reinicia o processo do servidor, vigia travamentos
(checagem de saúde) e quedas, reinicia sozinho, coleta métricas e guarda os eventos.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
import logging

import psutil

from painel import ARQUIVO_MANUTENCAO, PASTA_PAINEL, PASTA_PROJETO, ROTA_INTERNA

ARQUIVO_CONFIG = os.path.join(PASTA_PAINEL, 'config.json')
CONFIG_PADRAO = {
    'host': '0.0.0.0',
    'porta': 5000,
    'threads': 8,
    'python': '',                 # vazio = Python que roda o painel ou o "python" do sistema
    'iniciar_ao_abrir': True,
    'reiniciar_automatico': True,
    'tempo_resposta_max_s': 5,    # sem resposta da checagem por mais que isso conta como falha
    'falhas_para_reiniciar': 3,   # checagens seguidas sem resposta = travado
    'limite_memoria_mb': 1500,    # acima disso o servidor é reiniciado
    'max_reinicios_10min': 5,     # proteção contra laço de reinício
    'tempo_subida_max_s': 90,
}

ESTADOS = ('parado', 'iniciando', 'online', 'manutencao', 'reiniciando', 'parando', 'falhou')


def _agora():
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def carregar_config():
    config = dict(CONFIG_PADRAO)
    try:
        with open(ARQUIVO_CONFIG, encoding='utf-8') as arquivo:
            config.update({k: v for k, v in json.load(arquivo).items() if k in CONFIG_PADRAO})
    except (OSError, ValueError):
        pass
    return config


def salvar_config(config):
    temporario = ARQUIVO_CONFIG + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_CONFIG)


def _python():
    """Python para rodar o servidor: o configurado, o atual (fora do .exe) ou o do sistema."""
    configurado = carregar_config().get('python')
    if configurado and os.path.exists(configurado):
        return configurado
    if not getattr(sys, 'frozen', False):
        return sys.executable.replace('pythonw.exe', 'python.exe')
    return shutil.which('python') or shutil.which('py') or 'python'


def ips_locais():
    ips = set()
    try:
        for nome, enderecos in psutil.net_if_addrs().items():
            for e in enderecos:
                if e.family == socket.AF_INET and not e.address.startswith(('127.', '169.254.')):
                    ips.add(e.address)
    except Exception:
        pass
    return sorted(ips)


class Supervisor:
    def __init__(self):
        self.config = carregar_config()
        self.trava = threading.RLock()
        self.processo = None
        self.estado = 'parado'
        self.desejado = 'parado'           # o que o usuário pediu: 'online' ou 'parado'
        self.iniciado_em = None
        self.falhas_seguidas = 0
        self.reinicios = deque(maxlen=50)  # instantes dos reinícios automáticos
        self.total_reinicios_auto = 0
        self.ultimo_motivo = None
        self.saude = None
        self.ultima_saude_em = None
        self.eventos = deque(maxlen=200)
        self.logs = deque(maxlen=400)
        self.historico = deque(maxlen=180)  # 1 ponto a cada 2 s = 6 minutos
        self._anterior = None
        self._rede_anterior = None
        self._procs_cache = {}          # psutil precisa do mesmo objeto para medir CPU entre amostras
        self._log = self._criar_log()
        self._parar_threads = threading.Event()
        psutil.cpu_percent(None)
        threading.Thread(target=self._vigia, daemon=True, name='kaldi-vigia').start()

    # ------------------------------------------------------------ registro
    def _criar_log(self):
        pasta = os.path.join(PASTA_PROJETO, 'logs')
        os.makedirs(pasta, exist_ok=True)
        log = logging.getLogger('kaldi.servidor')
        log.setLevel(logging.INFO)
        if not log.handlers:
            manipulador = RotatingFileHandler(os.path.join(pasta, 'servidor.log'), maxBytes=2_000_000,
                                              backupCount=5, encoding='utf-8')
            manipulador.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            log.addHandler(manipulador)
        return log

    def evento(self, tipo, texto):
        item = {'quando': _agora(), 'tipo': tipo, 'texto': texto}
        self.eventos.appendleft(item)
        self.logs.append(f"{item['quando']} [painel] {texto}")
        self._log.info(f'[painel] {texto}')

    def _ler_saida(self, processo):
        for linha in iter(processo.stdout.readline, ''):
            linha = linha.rstrip()
            if linha:
                self.logs.append(f'{_agora()} {linha}')
                self._log.info(linha)
        processo.stdout.close()

    # ------------------------------------------------------------ controle
    def _porta_ocupada(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('127.0.0.1', int(self.config['porta']))) == 0

    def iniciar(self, motivo='Iniciado pelo painel'):
        with self.trava:
            self.desejado = 'online'
            if self.processo and self.processo.poll() is None:
                return False, 'O servidor já está rodando.'
            if self._porta_ocupada():
                self.estado = 'falhou'
                self.evento('erro', f"A porta {self.config['porta']} já está em uso por outro programa. "
                                    f"Feche o servidor antigo (janela 'Kaldi - servidor') e tente de novo.")
                return False, f"Porta {self.config['porta']} ocupada por outro programa."
            comando = [_python(), '-u', '-m', 'painel.servidor', '--host', str(self.config['host']),
                       '--porta', str(self.config['porta']), '--threads', str(self.config['threads'])]
            ambiente = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
            try:
                self.processo = subprocess.Popen(
                    comando, cwd=PASTA_PROJETO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', env=ambiente,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except OSError as e:
                self.estado = 'falhou'
                self.evento('erro', f'Não foi possível iniciar o Python ({comando[0]}): {e}')
                return False, 'Não foi possível iniciar o servidor.'
            threading.Thread(target=self._ler_saida, args=(self.processo,), daemon=True).start()
            self.estado = 'iniciando'
            self.iniciado_em = time.time()
            self.falhas_seguidas = 0
            self.saude = None
            self._anterior = None
            self.evento('inicio', f'{motivo} (pid {self.processo.pid}).')
            return True, 'Servidor iniciando.'

    def _matar(self, processo):
        try:
            pai = psutil.Process(processo.pid)
            for filho in pai.children(recursive=True):
                filho.kill()
            pai.kill()
        except psutil.NoSuchProcess:
            pass

    def parar(self, motivo='Parado pelo painel', desejado='parado'):
        with self.trava:
            self.desejado = desejado
            processo = self.processo
            if not processo or processo.poll() is not None:
                self.estado = 'parado' if desejado == 'parado' else self.estado
                return True, 'O servidor já estava parado.'
            self.estado = 'parando'
        # 1) pede para desligar com calma; 2) espera; 3) encerra à força
        try:
            pedido = urllib.request.Request(self._url(ROTA_INTERNA + '/desligar'), data=b'', method='POST')
            urllib.request.urlopen(pedido, timeout=2).close()
        except Exception:
            pass
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._matar(processo)
            try:
                processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        with self.trava:
            if desejado == 'parado':
                self.estado = 'parado'
                self.iniciado_em = None
                self.saude = None
            self.evento('parada', f'{motivo}.')
        return True, 'Servidor parado.'

    def reiniciar(self, motivo='Reiniciado pelo painel', automatico=False):
        with self.trava:
            self.estado = 'reiniciando'
        self.parar(motivo=motivo, desejado='online')
        if automatico:
            self.total_reinicios_auto += 1
            self.reinicios.append(time.time())
            self.ultimo_motivo = f'{_agora()} — {motivo}'
        return self.iniciar(motivo='Reinício automático' if automatico else 'Reiniciado pelo painel')

    # ------------------------------------------------------------ manutenção
    def manutencao(self, ativar, mensagem='', previsao='', permitir_local=True):
        os.makedirs(os.path.dirname(ARQUIVO_MANUTENCAO), exist_ok=True)
        dados = {'ativo': bool(ativar), 'mensagem': (mensagem or '').strip()[:300],
                 'previsao': (previsao or '').strip()[:60], 'permitir_local': bool(permitir_local),
                 'desde': _agora() if ativar else None}
        temporario = ARQUIVO_MANUTENCAO + '.tmp'
        with open(temporario, 'w', encoding='utf-8') as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False)
        os.replace(temporario, ARQUIVO_MANUTENCAO)
        self.evento('manutencao', 'Modo manutenção ligado: usuários veem a tela de manutenção.'
                    if ativar else 'Modo manutenção desligado: sistema liberado para todos.')
        return True, 'Modo manutenção ligado.' if ativar else 'Modo manutenção desligado.'

    def estado_manutencao(self):
        try:
            with open(ARQUIVO_MANUTENCAO, encoding='utf-8') as arquivo:
                return json.load(arquivo)
        except (OSError, ValueError):
            return {'ativo': False}

    # ------------------------------------------------------------ vigia
    def _url(self, caminho):
        return f"http://127.0.0.1:{self.config['porta']}{caminho}"

    def _checar_saude(self):
        try:
            with urllib.request.urlopen(self._url(ROTA_INTERNA + '/saude'),
                                        timeout=float(self.config['tempo_resposta_max_s'])) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            return None

    def _reinicios_recentes(self):
        limite = time.time() - 600
        return sum(1 for t in self.reinicios if t >= limite)

    def _reiniciar_automatico(self, motivo):
        if not self.config.get('reiniciar_automatico'):
            self.evento('erro', f'{motivo}. Reinício automático desligado: inicie manualmente.')
            with self.trava:
                self.estado = 'falhou'
            return
        if self._reinicios_recentes() >= int(self.config['max_reinicios_10min']):
            self.evento('erro', f'{motivo}. Já foram {self._reinicios_recentes()} reinícios em 10 minutos; '
                                'o vigia parou de reiniciar para não ficar em laço. Veja o registro.')
            with self.trava:
                self.estado = 'falhou'
                self.desejado = 'parado'
            return
        self.evento('alerta', f'{motivo}. Reiniciando automaticamente…')
        threading.Thread(target=self.reiniciar, kwargs={'motivo': motivo, 'automatico': True}, daemon=True).start()

    def _vigia(self):
        while not self._parar_threads.is_set():
            inicio_ciclo = time.time()
            try:
                self._ciclo()
            except Exception as e:  # o vigia nunca pode morrer
                self._log.info(f'[painel] erro no vigia: {e}')
            self._parar_threads.wait(max(0.2, 2 - (time.time() - inicio_ciclo)))

    def _ciclo(self):
        processo = self.processo
        estado = self.estado
        if estado in ('parando', 'reiniciando'):
            self._amostrar(None)
            return
        vivo = processo is not None and processo.poll() is None

        if self.desejado == 'online' and processo is not None and not vivo and estado != 'falhou':
            codigo = processo.poll()
            self._amostrar(None)
            self._reiniciar_automatico(f'O servidor encerrou sozinho (código {codigo})')
            return
        if not vivo:
            self._amostrar(None)
            return

        saude = self._checar_saude()
        if saude:
            self.saude = saude
            self.ultima_saude_em = time.time()
            self.falhas_seguidas = 0
            with self.trava:
                if self.estado in ('iniciando', 'online', 'manutencao'):
                    novo = 'manutencao' if saude.get('manutencao') else 'online'
                    if self.estado == 'iniciando':
                        self.evento('online', f'Servidor no ar em {time.time() - self.iniciado_em:.1f} s.')
                    self.estado = novo
        elif self.estado == 'iniciando':
            if time.time() - (self.iniciado_em or time.time()) > float(self.config['tempo_subida_max_s']):
                self._reiniciar_automatico('O servidor não terminou de subir a tempo')
        else:
            self.falhas_seguidas += 1
            if self.falhas_seguidas >= int(self.config['falhas_para_reiniciar']):
                self.falhas_seguidas = 0
                self._reiniciar_automatico(
                    f"O sistema parou de responder (travado por mais de "
                    f"{int(self.config['falhas_para_reiniciar']) * 2 + int(self.config['tempo_resposta_max_s'])} s)")
                return
        memoria = self._amostrar(processo)
        if memoria and memoria > float(self.config['limite_memoria_mb']):
            self._reiniciar_automatico(f'Uso de memória alto ({memoria:.0f} MB)')

    # ------------------------------------------------------------ métricas
    def _processos(self, processo):
        try:
            pai = self._procs_cache.get(processo.pid) or psutil.Process(processo.pid)
            todos = [pai] + pai.children(recursive=True)
        except psutil.NoSuchProcess:
            self._procs_cache.clear()
            return []
        cache = {}
        for p in todos:
            cache[p.pid] = self._procs_cache.get(p.pid, p)
        self._procs_cache = cache
        return list(cache.values())

    def _amostrar(self, processo):
        agora = time.time()
        rede = psutil.net_io_counters()
        ponto = {'t': agora, 'cpu': 0, 'mem': 0, 'rps': 0, 'lat': 0, 'down': 0, 'up': 0,
                 'rede_down': 0, 'rede_up': 0, 'cpu_sistema': psutil.cpu_percent(None), 'erros': 0}
        if self._rede_anterior:
            dt = max(agora - self._rede_anterior[0], 0.001)
            ponto['rede_down'] = (rede.bytes_recv - self._rede_anterior[1]) / dt
            ponto['rede_up'] = (rede.bytes_sent - self._rede_anterior[2]) / dt
        self._rede_anterior = (agora, rede.bytes_recv, rede.bytes_sent)

        memoria = None
        if processo is not None:
            procs = self._processos(processo)
            try:
                ponto['cpu'] = sum(p.cpu_percent(None) for p in procs) / (psutil.cpu_count() or 1)
                memoria = sum(p.memory_info().rss for p in procs) / 1048576
                ponto['mem'] = memoria
            except psutil.Error:
                pass
        metricas = (self.saude or {}).get('metricas') if processo is not None else None
        if metricas:
            atual = (agora, metricas['total'], metricas['bytes_recebidos'], metricas['bytes_enviados'],
                     metricas['por_status'].get('5xx', 0))
            if self._anterior and atual[1] >= self._anterior[1]:
                dt = max(agora - self._anterior[0], 0.001)
                ponto['rps'] = (atual[1] - self._anterior[1]) / dt
                ponto['down'] = (atual[2] - self._anterior[2]) / dt
                ponto['up'] = (atual[3] - self._anterior[3]) / dt
                ponto['erros'] = atual[4] - self._anterior[4]
            self._anterior = atual
            ponto['lat'] = metricas.get('tempo_medio_ms') or 0
        self.historico.append(ponto)
        return memoria

    def _info_processo(self):
        processo = self.processo
        if not processo or processo.poll() is not None:
            return None
        try:
            p = psutil.Process(processo.pid)
            procs = self._processos(processo)
            conexoes = 0
            try:
                conexoes = sum(1 for c in p.net_connections(kind='tcp')
                               if c.status == psutil.CONN_ESTABLISHED and c.laddr and c.laddr.port == int(self.config['porta']))
            except (psutil.AccessDenied, AttributeError):
                pass
            return {
                'pid': p.pid,
                'threads': sum(x.num_threads() for x in procs),
                'memoria_mb': round(sum(x.memory_info().rss for x in procs) / 1048576, 1),
                'conexoes': conexoes,
                'comando': ' '.join(p.cmdline()[:6]),
            }
        except psutil.Error:
            return None

    # ------------------------------------------------------------ painel
    def instantaneo(self):
        """Tudo o que o painel mostra, em um dicionário."""
        disco = psutil.disk_usage(PASTA_PROJETO)
        memoria = psutil.virtual_memory()
        try:
            versao = subprocess.run(['git', 'log', '-1', '--format=%h · %cd', '--date=format:%d/%m/%Y %H:%M'],
                                    cwd=PASTA_PROJETO, capture_output=True, text=True, timeout=2,
                                    encoding='utf-8', errors='replace',
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
        except Exception:
            versao = ''
        uptime = time.time() - self.iniciado_em if self.iniciado_em and self.estado in ('online', 'manutencao') else 0
        return {
            'estado': self.estado,
            'desejado': self.desejado,
            'uptime_s': uptime,
            'config': self.config,
            'saude': self.saude,
            'ultima_saude_ha_s': (time.time() - self.ultima_saude_em) if self.ultima_saude_em else None,
            'falhas_seguidas': self.falhas_seguidas,
            'reinicios_auto': self.total_reinicios_auto,
            'reinicios_10min': self._reinicios_recentes(),
            'ultimo_motivo': self.ultimo_motivo,
            'processo': self._info_processo(),
            'historico': list(self.historico),
            'eventos': list(self.eventos)[:40],
            'logs': list(self.logs)[-150:],
            'manutencao': self.estado_manutencao(),
            'sistema': {
                'ips': ips_locais(),
                'host_nome': socket.gethostname(),
                'cpu_nucleos': psutil.cpu_count(),
                'memoria_total_gb': round(memoria.total / 1073741824, 1),
                'memoria_uso_pct': memoria.percent,
                'disco_livre_gb': round(disco.free / 1073741824, 1),
                'disco_uso_pct': disco.percent,
                'python': _python(),
                'versao': versao,
                'pasta': PASTA_PROJETO,
                'iniciado_windows_ha_h': round((time.time() - psutil.boot_time()) / 3600, 1),
            },
        }

    def atualizar_config(self, novos):
        permitidos = {
            'porta': (int, 1, 65535), 'threads': (int, 2, 64), 'tempo_resposta_max_s': (int, 2, 60),
            'falhas_para_reiniciar': (int, 1, 20), 'limite_memoria_mb': (int, 200, 16000),
            'max_reinicios_10min': (int, 1, 50),
        }
        for chave, (tipo, minimo, maximo) in permitidos.items():
            if chave in novos:
                try:
                    self.config[chave] = max(minimo, min(maximo, tipo(novos[chave])))
                except (TypeError, ValueError):
                    pass
        for chave in ('iniciar_ao_abrir', 'reiniciar_automatico'):
            if chave in novos:
                self.config[chave] = bool(novos[chave])
        if novos.get('host') in ('0.0.0.0', '127.0.0.1'):
            self.config['host'] = novos['host']
        salvar_config(self.config)
        self.evento('config', 'Configurações do servidor salvas (porta e host valem no próximo início).')
        return True, 'Configurações salvas.'

    def encerrar(self):
        self._parar_threads.set()
        if self.processo and self.processo.poll() is None:
            self.parar('Painel fechado')
