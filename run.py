import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Debug vem do .env (FLASK_DEBUG). Com debug ligado e host 0.0.0.0, qualquer
    # aparelho da rede vê detalhes internos dos erros: use só em desenvolvimento.
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('1', 'true', 'sim')
    host = os.environ.get('HOST', '0.0.0.0')
    porta = int(os.environ.get('PORT', '5000'))
    if debug and host == '0.0.0.0':
        print('ATENÇÃO: modo debug ligado e aberto para a rede. Desligue (FLASK_DEBUG=False) em uso real.')
    app.run(host=host, port=porta, debug=debug)
