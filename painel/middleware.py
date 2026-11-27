"""
Camada WSGI do servidor de produção.

- Mede requisições: total, por faixa de status, em andamento, bytes recebidos/enviados,
  tempo de resposta (média e p95) e rotas mais acessadas.
- Responde /__kaldi/saude (só para 127.0.0.1) com as métricas: o vigia do painel usa
  essa resposta para saber se o sistema está vivo ou travado.
- Modo manutenção: com storage/manutencao.json ativo, devolve a tela de manutenção (503)
  para todos, exceto arquivos estáticos e, se permitido, quem acessa do próprio servidor.
"""
import json
import os
import re
import threading
import time
from collections import Counter, deque
from html import escape

from painel import ARQUIVO_MANUTENCAO, ROTA_INTERNA

_LOCAIS = {'127.0.0.1', '::1', 'localhost'}
_NUMEROS = re.compile(r'/\d+(?=/|$)')


class Metricas:
    def __init__(self):
        self.trava = threading.Lock()
        self.inicio = time.time()
        self.total = 0
        self.em_andamento = 0
        self.por_status = Counter()
        self.bytes_recebidos = 0
        self.bytes_enviados = 0
        self.tempos = deque(maxlen=600)          # (instante, duração ms)
        self.rotas = Counter()
        self.erros = deque(maxlen=20)            # últimos 5xx
        self.manutencao_bloqueadas = 0

    def registrar(self, caminho, status, duracao_ms, recebidos, enviados, metodo):
        rota = _NUMEROS.sub('/<id>', caminho or '/')
        with self.trava:
            self.total += 1
            self.por_status[f'{str(status)[0]}xx'] += 1
            self.bytes_recebidos += recebidos
            self.bytes_enviados += enviados
            self.tempos.append((time.time(), duracao_ms))
            if not rota.startswith('/static/'):
                self.rotas[rota] += 1
            if str(status).startswith('5'):
                self.erros.append({'quando': time.time(), 'rota': f'{metodo} {rota}', 'status': status})

    def resumo(self):
        with self.trava:
            agora = time.time()
            recentes = sorted(d for t, d in self.tempos if agora - t <= 60)
            return {
                'iniciado_em': self.inicio,
                'total': self.total,
                'em_andamento': self.em_andamento,
                'por_status': dict(self.por_status),
                'bytes_recebidos': self.bytes_recebidos,
                'bytes_enviados': self.bytes_enviados,
                'tempo_medio_ms': round(sum(recentes) / len(recentes), 1) if recentes else 0,
                'tempo_p95_ms': round(recentes[int(len(recentes) * 0.95) - 1], 1) if recentes else 0,
                'requisicoes_ultimo_minuto': len(recentes),
                'rotas': self.rotas.most_common(6),
                'erros': list(self.erros)[-6:],
                'manutencao_bloqueadas': self.manutencao_bloqueadas,
            }


class EstadoManutencao:
    """Lê storage/manutencao.json no máximo uma vez por segundo."""
    def __init__(self, caminho=ARQUIVO_MANUTENCAO):
        self.caminho = caminho
        self._lido_em = 0
        self._mtime = None
        self._dados = {'ativo': False}

    def atual(self):
        agora = time.time()
        if agora - self._lido_em < 1:
            return self._dados
        self._lido_em = agora
        try:
            mtime = os.path.getmtime(self.caminho)
        except OSError:
            self._dados, self._mtime = {'ativo': False}, None
            return self._dados
        if mtime != self._mtime:
            try:
                with open(self.caminho, encoding='utf-8') as arquivo:
                    self._dados = json.load(arquivo)
                self._mtime = mtime
            except (OSError, ValueError):
                pass
        return self._dados


def pagina_manutencao(dados):
    mensagem = escape(dados.get('mensagem') or 'Estamos fazendo melhorias no sistema.')
    previsao = escape(dados.get('previsao') or '')
    linha_previsao = f'<p class="prev">Previsão de volta: <strong>{previsao}</strong></p>' if previsao else ''
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Em manutenção | Kaldi</title>
<link rel="icon" href="/static/img/kaldi-favicon-32.png">
<style>
:root {{ --verde:#1A5A3B; --verde2:#2E8A5C; --fundo:#F5F4F0; --texto:#1C2420; --texto2:#5B665F; --cartao:#fff; --borda:#E4E2DA; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fundo:#0E1411; --texto:#E8EEEA; --texto2:#9AA8A0; --cartao:#151D19; --borda:#26312B; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:24px; background:var(--fundo); color:var(--texto);
       font-family:Inter, "Segoe UI", system-ui, sans-serif; }}
.cartao {{ max-width:520px; width:100%; background:var(--cartao); border:1px solid var(--borda); border-radius:20px; padding:40px 32px;
          text-align:center; box-shadow:0 20px 60px -30px rgba(15,53,36,.45); position:relative; overflow:hidden; }}
.cartao::before {{ content:""; position:absolute; inset:0 0 auto 0; height:6px; background:linear-gradient(90deg,var(--verde2),var(--verde),#D9381F); }}
img {{ width:76px; height:76px; }}
h1 {{ font-family:Manrope, "Segoe UI", sans-serif; font-weight:800; letter-spacing:-.02em; margin:18px 0 8px; font-size:1.6rem; }}
p {{ color:var(--texto2); line-height:1.55; margin:6px 0; }}
.prev {{ margin-top:14px; color:var(--texto); }}
.engrenagem {{ display:inline-flex; gap:6px; margin-top:22px; }}
.engrenagem span {{ width:9px; height:9px; border-radius:50%; background:var(--verde2); animation:pulsa 1.4s infinite ease-in-out; }}
.engrenagem span:nth-child(2) {{ animation-delay:.2s; }} .engrenagem span:nth-child(3) {{ animation-delay:.4s; background:#D9381F; }}
@keyframes pulsa {{ 0%,80%,100% {{ transform:scale(.6); opacity:.4; }} 40% {{ transform:scale(1); opacity:1; }} }}
small {{ display:block; margin-top:22px; color:var(--texto2); font-size:.78rem; }}
</style></head>
<body><main class="cartao" role="main">
<img src="/static/img/kaldi-icone.svg" alt="Kaldi">
<h1>Sistema em manutenção</h1>
<p>{mensagem}</p>
{linha_previsao}
<div class="engrenagem" aria-hidden="true"><span></span><span></span><span></span></div>
<small>Esta página tenta de novo sozinha a cada minuto.</small>
</main></body></html>""".encode('utf-8')


class KaldiMiddleware:
    def __init__(self, app, ao_desligar=None):
        self.app = app
        self.metricas = Metricas()
        self.manutencao = EstadoManutencao()
        self.ao_desligar = ao_desligar
        self.banco = {'ok': None, 'latencia_ms': None, 'erro': None, 'verificado_em': None}
        threading.Thread(target=self._vigiar_banco, daemon=True, name='kaldi-banco').start()

    # ------------------------------------------------------------ banco
    def _vigiar_banco(self):
        import psycopg2
        while True:
            inicio = time.time()
            try:
                conn = psycopg2.connect(
                    host=os.getenv('DB_HOST', 'localhost'), port=os.getenv('DB_PORT', '5432'),
                    dbname=os.getenv('DB_NAME', 'fazenda_cafe'), user=os.getenv('DB_USER', 'postgres'),
                    password=os.getenv('DB_PASSWORD'), connect_timeout=3)
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())), "
                                "(SELECT count(*) FROM pg_stat_activity WHERE datname = current_database())")
                    tamanho, conexoes = cur.fetchone()
                conn.close()
                self.banco = {'ok': True, 'latencia_ms': round((time.time() - inicio) * 1000, 1),
                              'tamanho': tamanho, 'conexoes': conexoes, 'erro': None, 'verificado_em': time.time()}
            except Exception as e:
                self.banco = {'ok': False, 'latencia_ms': None, 'erro': str(e).strip()[:160],
                              'verificado_em': time.time()}
            time.sleep(10)

    # ------------------------------------------------------------ WSGI
    def __call__(self, environ, start_response):
        caminho = environ.get('PATH_INFO', '/')
        endereco = environ.get('REMOTE_ADDR', '')
        if caminho.startswith(ROTA_INTERNA + '/'):
            return self._interna(caminho, endereco, environ, start_response)

        estado = self.manutencao.atual()
        if (estado.get('ativo') and not caminho.startswith('/static/')
                and not (estado.get('permitir_local', True) and endereco in _LOCAIS)):
            with self.metricas.trava:
                self.metricas.manutencao_bloqueadas += 1
            corpo = pagina_manutencao(estado)
            start_response('503 Service Unavailable', [
                ('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(corpo))),
                ('Retry-After', '120'), ('Cache-Control', 'no-store')])
            return [corpo]

        return self._servir(caminho, environ, start_response)

    def _servir(self, caminho, environ, start_response):
        """Caminho normal: repassa ao sistema medindo tempo, status e bytes."""
        inicio = time.perf_counter()
        status_final = {'codigo': 500}
        try:
            recebidos = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError:
            recebidos = 0
        # linha do pedido + cabeçalhos (GETs não têm corpo, mas também usam banda)
        recebidos += len(environ.get('REQUEST_METHOD', '')) + len(caminho) + len(environ.get('QUERY_STRING', '')) + 12
        recebidos += sum(len(k) - 5 + len(str(v)) + 4 for k, v in environ.items() if k.startswith('HTTP_'))

        def start(status, headers, exc_info=None):
            try:
                status_final['codigo'] = int(status.split(' ', 1)[0])
            except ValueError:
                pass
            return start_response(status, headers, exc_info)

        with self.metricas.trava:
            self.metricas.em_andamento += 1
        enviados = 0
        try:
            resposta = self.app(environ, start)
            try:
                for pedaco in resposta:
                    enviados += len(pedaco)
                    yield pedaco
            finally:
                if hasattr(resposta, 'close'):
                    resposta.close()
        finally:
            with self.metricas.trava:
                self.metricas.em_andamento -= 1
            self.metricas.registrar(caminho, status_final['codigo'], (time.perf_counter() - inicio) * 1000,
                                    recebidos, enviados, environ.get('REQUEST_METHOD', 'GET'))

    def _interna(self, caminho, endereco, environ, start_response):
        if endereco not in _LOCAIS:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'']
        if caminho == ROTA_INTERNA + '/saude':
            dados = {'ok': True, 'pid': os.getpid(), 'metricas': self.metricas.resumo(),
                     'banco': self.banco, 'manutencao': bool(self.manutencao.atual().get('ativo'))}
            corpo = json.dumps(dados, default=str).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json'), ('Cache-Control', 'no-store'),
                                      ('Content-Length', str(len(corpo)))])
            return [corpo]
        if caminho == ROTA_INTERNA + '/desligar' and environ.get('REQUEST_METHOD') == 'POST':
            start_response('202 Accepted', [('Content-Type', 'text/plain')])
            if self.ao_desligar:
                threading.Timer(0.3, self.ao_desligar).start()
            return [b'desligando']
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'']
