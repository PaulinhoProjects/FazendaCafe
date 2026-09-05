import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

class Config:
    """Configurações centrais da aplicação Flask."""

    # Segurança
    SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-padrao-trocar-em-producao')

    # Banco de dados
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'fazenda_cafe')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    # Uploads
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # Sessão
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    @classmethod
    def get_dsn(cls):
        """Retorna a string de conexão DSN para psycopg2."""
        return (
            f"host={cls.DB_HOST} "
            f"port={cls.DB_PORT} "
            f"dbname={cls.DB_NAME} "
            f"user={cls.DB_USER} "
            f"password={cls.DB_PASSWORD}"
        )

class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = 'production'

class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = 'development'
