import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

_ARQUIVO_CHAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')


def _carregar_chave_secreta():
    """A SECRET_KEY assina o cookie de sessão: com uma chave fraca, qualquer pessoa
    consegue forjar uma sessão de administrador. Usa a do .env se for forte (32+
    caracteres); senão gera uma aleatória e guarda em config/.secret_key (fora do Git)."""
    chave_env = os.environ.get('SECRET_KEY', '')
    if len(chave_env) >= 32:
        return chave_env, 'env'
    try:
        if os.path.exists(_ARQUIVO_CHAVE):
            with open(_ARQUIVO_CHAVE, encoding='utf-8') as f:
                chave = f.read().strip()
            if len(chave) >= 32:
                return chave, 'arquivo'
        chave = secrets.token_urlsafe(48)
        with open(_ARQUIVO_CHAVE, 'w', encoding='utf-8') as f:
            f.write(chave)
        return chave, 'arquivo'
    except OSError as e:
        raise RuntimeError(
            "Não foi possível carregar ou gravar a SECRET_KEY. "
            "Defina SECRET_KEY com pelo menos 32 caracteres no .env ou permita "
            "escrita em config/.secret_key."
        ) from e


_CHAVE, _ORIGEM_CHAVE = _carregar_chave_secreta()


class Config:
    """Configurações centrais da aplicação Flask."""

    # Segurança
    SECRET_KEY = _CHAVE
    SECRET_KEY_ORIGEM = _ORIGEM_CHAVE

    # Banco de dados
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'fazenda_cafe')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

    # Uploads
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # Sessão
    SESSION_COOKIE_NAME = 'kaldi_sessao'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('1', 'true', 'sim')
    # Limite máximo do cookie; a expiração por inatividade é controlada em Configurações > Segurança
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

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
