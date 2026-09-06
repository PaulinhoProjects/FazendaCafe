import os
from flask import Flask
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Pasta de uploads usada por notas fiscais, devoluções e PDFs do dashboard
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_dir

    # Jinja filters
    @app.template_filter('format_data')
    def format_data(date):
        if date is None:
            return '—'
        try:
            return date.strftime('%d/%m/%Y')
        except (AttributeError, TypeError):
            return str(date)

    @app.template_filter('format_moeda')
    def format_moeda(value):
        try:
            return f"R$ {float(value):.2f}".replace('.', ',')
        except (ValueError, TypeError):
            return 'R$ 0,00'

    @app.template_filter('format_quantidade')
    def format_quantidade(value):
        if value is None:
            return '0'
        try:
            val = float(value)
            if val == int(val):
                return str(int(val))
            return f"{val:.2f}".rstrip('0').rstrip('.') if '.' in f"{val:.2f}" else f"{val:.2f}"
        except (ValueError, TypeError):
            return str(value)

    # Context processors
    try:
        from app.context_processors import alertas_context, config_context
        app.context_processor(alertas_context)
        app.context_processor(config_context)
    except Exception as e:
        print(f"Aviso: context processors não carregados: {e}")

    @app.context_processor
    def utility_processor():
        try:
            from app.modules.clima import get_icone_clima
            return dict(get_icone_clima=get_icone_clima)
        except Exception:
            return dict()

    # Registrar Blueprints - TODOS
    from app.routes.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.routes.talhoes_routes import talhoes_bp
    app.register_blueprint(talhoes_bp)

    from app.routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.estoque_routes import estoque_bp
    app.register_blueprint(estoque_bp)

    try:
        from app.routes.pulverizacao_routes import pulverizacao_bp
        app.register_blueprint(pulverizacao_bp)
    except Exception as e:
        print(f"Aviso: blueprint pulverizacao nao carregado: {e}")

    try:
        from app.routes.adubacao_routes import adubacao_bp
        app.register_blueprint(adubacao_bp)
    except Exception as e:
        print(f"Aviso: blueprint adubacao nao carregado: {e}")

    try:
        from app.routes.analises_routes import analises_bp
        app.register_blueprint(analises_bp)
    except Exception as e:
        print(f"Aviso: blueprint analises nao carregado: {e}")

    try:
        from app.routes.manejo_mato_routes import manejo_mato_bp
        app.register_blueprint(manejo_mato_bp)
    except Exception as e:
        print(f"Aviso: blueprint manejo_mato nao carregado: {e}")

    try:
        from app.routes.manejo_routes import manejo_bp
        app.register_blueprint(manejo_bp)
    except Exception as e:
        print(f"Aviso: blueprint manejo nao carregado: {e}")

    try:
        from app.routes.clima_routes import clima_bp
        app.register_blueprint(clima_bp)
    except Exception as e:
        print(f"Aviso: blueprint clima nao carregado: {e}")

    try:
        from app.routes.notas_fiscais_routes import notas_fiscais_bp
        app.register_blueprint(notas_fiscais_bp)
    except Exception as e:
        print(f"Aviso: blueprint notas_fiscais nao carregado: {e}")

    try:
        from app.routes.devolucao_embalagens_routes import devolucao_bp
        app.register_blueprint(devolucao_bp)
    except Exception as e:
        print(f"Aviso: blueprint devolucao nao carregado: {e}")

    try:
        from app.routes.relatorios_routes import relatorios_bp
        app.register_blueprint(relatorios_bp)
    except Exception as e:
        print(f"Aviso: blueprint relatorios nao carregado: {e}")

    try:
        from app.routes.config_routes import config_bp
        app.register_blueprint(config_bp)
    except Exception as e:
        print(f"Aviso: blueprint config nao carregado: {e}")

    # Handlers de erro globais
    try:
        from app.models import register_error_handlers
        register_error_handlers(app)
    except Exception as e:
        print(f"Aviso: error handlers nao carregados: {e}")

    # Error handlers diretos
    from flask import render_template

    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('erro.html', codigo=404, titulo='Página não encontrada', mensagem='A página que você procura não existe ou foi movida.'), 404

    @app.errorhandler(500)
    def erro_interno(e):
        return render_template('erro.html', codigo=500, titulo='Erro interno', mensagem='Algo deu errado no servidor. Tente novamente.'), 500

    @app.errorhandler(403)
    def acesso_negado(e):
        return render_template('erro.html', codigo=403, titulo='Acesso negado', mensagem='Você não tem permissão para acessar esta página.'), 403

    # Garante a tabela de usuários em instalações novas
    try:
        from app.modules.auth import criar_tabela_usuarios
        criar_tabela_usuarios()
    except Exception as e:
        print(f"Aviso: tabela de usuarios nao verificada: {e}")

    # Criar tabela de configuracoes se nao existir
    try:
        from config.database import executar_query
        executar_query("""
            CREATE TABLE IF NOT EXISTS configuracoes_sistema (
                id SERIAL PRIMARY KEY,
                chave VARCHAR(100) UNIQUE NOT NULL,
                valor TEXT,
                descricao VARCHAR(255),
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Inserir configs padrao
        configs_padrao = [
            ('nome_sistema', 'AgroCafe', 'Nome do sistema'),
            ('slogan', 'Tecnologia que Colhe Resultados', 'Slogan do sistema'),
            ('cidade', 'Campos Gerais', 'Cidade para clima'),
            ('estado', 'MG', 'Estado para clima'),
            ('api_clima_key', '', 'Chave da API OpenWeather'),
            ('itens_por_pagina', '20', 'Itens por pagina nas listagens'),
        ]
        for chave, valor, desc in configs_padrao:
            existe = executar_query("SELECT id FROM configuracoes_sistema WHERE chave = %s", (chave,), fetch_one=True)
            if not existe:
                executar_query(
                    "INSERT INTO configuracoes_sistema (chave, valor, descricao) VALUES (%s, %s, %s)",
                    (chave, valor, desc)
                )
        print("Tabela configuracoes_sistema criada/verificada!")
    except Exception as e:
        print(f"Aviso: nao foi possivel criar tabela de configuracoes: {e}")

    # Corrigir tabela talhoes
    try:
        from config.database import corrigir_tabela_talhoes
        corrigir_tabela_talhoes()
    except Exception as e:
        print(f"Aviso: nao foi possivel corrigir tabela talhoes: {e}")

    try:
        from config.database import criar_tabela_categorias_estoque
        criar_tabela_categorias_estoque()
    except Exception as e:
        print(f"Aviso: categorias_estoque: {e}")

    return app