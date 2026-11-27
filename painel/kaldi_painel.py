"""
Kaldi Servidor — painel de controle (janela própria no padrão do sistema).

Abre um painel local (127.0.0.1) numa janela do Microsoft Edge em modo aplicativo (sem barra
de endereço), inicia o servidor de produção e vigia travamentos. Só uma instância roda por vez:
abrir de novo apenas traz a janela do painel existente.
"""
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from painel import PASTA_PAINEL, PASTA_PROJETO, VERSAO_PAINEL  # noqa: E402

if getattr(sys, 'frozen', False):
    os.chdir(PASTA_PROJETO)
from painel.supervisor import Supervisor  # noqa: E402

PORTA_PAINEL = 5099
ARQUIVO_SESSAO = os.path.join(PASTA_PAINEL, '.sessao')


def _recurso(nome):
    base = getattr(sys, '_MEIPASS', None)
    caminho = os.path.join(base, 'painel', nome) if base else os.path.join(PASTA_PAINEL, nome)
    with open(caminho, 'rb') as arquivo:
        return arquivo.read()


def _logo_svg():
    try:
        return _recurso('logo.svg')
    except OSError:
        with open(os.path.join(PASTA_PROJETO, 'app', 'static', 'img', 'kaldi-icone.svg'), 'rb') as arquivo:
            return arquivo.read()


class Painel:
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.supervisor = Supervisor()
        self.ultimo_contato = time.time()

    def acao(self, dados):
        acao = dados.get('acao')
        s = self.supervisor
        if acao == 'iniciar':
            return s.iniciar()
        if acao == 'parar':
            return s.parar()
        if acao == 'reiniciar':
            threading.Thread(target=s.reiniciar, daemon=True).start()
            return True, 'Reiniciando o servidor…'
        if acao == 'manutencao':
            return s.manutencao(bool(dados.get('ativar')), dados.get('mensagem'), dados.get('previsao'),
                                dados.get('permitir_local', True))
        if acao == 'config':
            return s.atualizar_config(dados.get('config') or {})
        if acao == 'abrir_sistema':
            webbrowser.open(f"http://127.0.0.1:{s.config['porta']}/")
            return True, 'Abrindo o sistema no navegador.'
        if acao == 'abrir_logs':
            os.startfile(os.path.join(PASTA_PROJETO, 'logs'))
            return True, 'Abrindo a pasta de registros.'
        if acao == 'sair':
            threading.Thread(target=encerrar, args=(self,), daemon=True).start()
            return True, 'Encerrando o painel e o servidor.'
        return False, 'Ação desconhecida.'


def criar_manipulador(painel):
    class Manipulador(BaseHTTPRequestHandler):
        server_version = 'KaldiPainel'

        def log_message(self, *args):
            pass

        def _enviar(self, codigo, corpo, tipo='application/json; charset=utf-8'):
            if isinstance(corpo, (dict, list)):
                corpo = json.dumps(corpo, default=str, ensure_ascii=False).encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(corpo)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(corpo)

        def _autorizado(self):
            return secrets.compare_digest(self.headers.get('X-Painel-Token', ''), painel.token)

        def do_GET(self):
            caminho = self.path.split('?', 1)[0]
            if caminho in ('/', '/index.html'):
                html = _recurso('ui.html').replace(b'{{TOKEN}}', painel.token.encode()) \
                                          .replace(b'{{VERSAO}}', VERSAO_PAINEL.encode())
                return self._enviar(200, html, 'text/html; charset=utf-8')
            if caminho == '/logo.svg':
                return self._enviar(200, _logo_svg(), 'image/svg+xml')
            if caminho == '/api/estado':
                if not self._autorizado():
                    return self._enviar(403, {'erro': 'sem autorização'})
                painel.ultimo_contato = time.time()
                return self._enviar(200, painel.supervisor.instantaneo())
            self._enviar(404, {'erro': 'não encontrado'})

        def do_POST(self):
            if self.path != '/api/acao' or not self._autorizado():
                return self._enviar(403, {'erro': 'sem autorização'})
            try:
                tamanho = min(int(self.headers.get('Content-Length') or 0), 20000)
                dados = json.loads(self.rfile.read(tamanho) or b'{}')
                ok, mensagem = painel.acao(dados)
            except Exception as e:
                ok, mensagem = False, f'Erro: {e}'
            self._enviar(200, {'ok': ok, 'mensagem': mensagem})

    return Manipulador


def _edge():
    for caminho in (r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'):
        if os.path.exists(caminho):
            return caminho
    return None


def abrir_janela(url):
    """Janela em modo aplicativo (Edge); sem Edge, usa o navegador padrão."""
    edge = _edge()
    if not edge:
        webbrowser.open(url)
        return None
    perfil = os.path.join(os.environ.get('LOCALAPPDATA', PASTA_PAINEL), 'KaldiServidor', 'janela')
    os.makedirs(perfil, exist_ok=True)
    return subprocess.Popen([edge, f'--app={url}', f'--user-data-dir={perfil}', '--window-size=1320,860',
                             '--no-first-run', '--disable-features=Translate', '--no-default-browser-check'])


def encerrar(painel, codigo=0):
    try:
        painel.supervisor.encerrar()
    finally:
        try:
            os.remove(ARQUIVO_SESSAO)
        except OSError:
            pass
        os._exit(codigo)


def main():
    painel = Painel()
    try:
        servidor_http = ThreadingHTTPServer(('127.0.0.1', PORTA_PAINEL), criar_manipulador(painel))
    except OSError:
        # Já existe um painel aberto: só mostra a janela dele
        try:
            with open(ARQUIVO_SESSAO, encoding='utf-8') as arquivo:
                url = arquivo.read().strip()
            abrir_janela(url)
        except OSError:
            webbrowser.open(f'http://127.0.0.1:{PORTA_PAINEL}/')
        return
    url = f'http://127.0.0.1:{PORTA_PAINEL}/?t={painel.token}'
    with open(ARQUIVO_SESSAO, 'w', encoding='utf-8') as arquivo:
        arquivo.write(url)
    threading.Thread(target=servidor_http.serve_forever, daemon=True, name='kaldi-painel-http').start()

    if painel.supervisor.config.get('iniciar_ao_abrir', True):
        painel.supervisor.iniciar('Iniciado ao abrir o painel')

    janela = abrir_janela(url)
    if '--sem-janela' in sys.argv:
        janela = None
    try:
        if janela is not None:
            # Fechar a janela do painel encerra o servidor (o painel pergunta antes)
            while True:
                time.sleep(1)
                if janela.poll() is not None and time.time() - painel.ultimo_contato > 6:
                    break
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    encerrar(painel)


if __name__ == '__main__':
    main()
