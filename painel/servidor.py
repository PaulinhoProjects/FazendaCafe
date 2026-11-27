"""
Servidor de produção do Kaldi (waitress), iniciado e vigiado pelo painel.

Uso direto:  python -m painel.servidor --porta 5000 --host 0.0.0.0 --threads 8
"""
import argparse
import os
import sys

from painel import PASTA_PROJETO


def main():
    parser = argparse.ArgumentParser(description='Servidor de produção do Kaldi')
    parser.add_argument('--host', default=os.getenv('HOST', '0.0.0.0'))
    parser.add_argument('--porta', type=int, default=int(os.getenv('PORT', '5000')))
    parser.add_argument('--threads', type=int, default=8)
    args = parser.parse_args()

    os.chdir(PASTA_PROJETO)
    sys.path.insert(0, PASTA_PROJETO)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PASTA_PROJETO, '.env'))
    except ImportError:
        pass
    os.environ['FLASK_DEBUG'] = 'False'      # produção: nunca com debug

    from waitress import create_server
    from app import create_app
    from painel.middleware import KaldiMiddleware

    app = create_app()
    servidor = {'instancia': None}

    def desligar():
        print('[kaldi] desligamento pedido pelo painel', flush=True)
        if servidor['instancia']:
            servidor['instancia'].close()          # para de aceitar conexões novas
        # dá alguns segundos para terminar as respostas em andamento e encerra
        import threading
        threading.Timer(5, lambda: os._exit(0)).start()

    wsgi = KaldiMiddleware(app, ao_desligar=desligar)
    instancia = create_server(wsgi, host=args.host, port=args.porta, threads=args.threads,
                              ident='Kaldi', channel_timeout=60, connection_limit=200,
                              cleanup_interval=15)
    servidor['instancia'] = instancia
    print(f'[kaldi] servidor no ar em http://{args.host}:{args.porta} (pid {os.getpid()}, '
          f'{args.threads} threads)', flush=True)
    try:
        instancia.run()
    except (KeyboardInterrupt, SystemExit):
        pass
    except OSError as e:
        print(f'[kaldi] erro ao abrir a porta {args.porta}: {e}', flush=True)
        sys.exit(3)
    print('[kaldi] servidor encerrado', flush=True)


if __name__ == '__main__':
    main()
