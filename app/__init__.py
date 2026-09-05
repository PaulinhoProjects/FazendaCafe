import os
from flask import Flask
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Pasta de uploads
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_dir

    # Filtros Jinja personalizados
    @app.template_filter('format_data')
    def format_data(value):
        if value:
            if hasattr(value, 'strftime'):
                return value.strftime('%d/%m/%Y')
            return str(value)
        return ''

    @app.template_filter('format_moeda')
    def format_moeda(value):
        if value is not None:
            try:
                val = float(value)
                return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except (ValueError, TypeError):
                return str(value)
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

    # Processadores de contexto para templates
    @app.context_processor
    def utility_processor():
        from app.modules.clima import get_icone_clima
        return dict(get_icone_clima=get_icone_clima)

    # Registrar Blueprints
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.talhoes_routes import talhoes_bp
    from app.routes.auth_routes import auth_bp
    
    # Comentado por enquanto até refatorar os outros
    # from app.routes.estoque_routes import estoque_bp
    # from app.routes.adubacao_routes import adubacao_bp
    # from app.routes.pulverizacao_routes import pulverizacao_bp
    # from app.routes.analises_routes import analises_bp
    # from app.routes.manejo_mato_routes import manejo_mato_bp
    # from app.routes.clima_routes import clima_bp
    # from app.routes.notas_fiscais_routes import notas_fiscais_bp
    # from app.routes.devolucao_embalagens_routes import devolucao_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(talhoes_bp)
    app.register_blueprint(auth_bp)
    
    # app.register_blueprint(estoque_bp)
    # app.register_blueprint(adubacao_bp)
    # app.register_blueprint(pulverizacao_bp)
    # app.register_blueprint(analises_bp)
    # app.register_blueprint(manejo_mato_bp)
    # app.register_blueprint(clima_bp)
    # app.register_blueprint(notas_fiscais_bp)
    # app.register_blueprint(devolucao_bp)

    # Handlers de erro globais (Etapa 4)
    from app.models import register_error_handlers
    register_error_handlers(app)

    return app
