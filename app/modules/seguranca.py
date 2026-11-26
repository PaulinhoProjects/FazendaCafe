"""
Módulo de Segurança — Kaldi
Controle de tentativas de login, registro de acessos, expiração de sessão
e diagnóstico de segurança exibido em Configurações.
"""
import os
import threading
from datetime import datetime, timedelta
from urllib.parse import urlparse

from config.database import executar_query, get_config
from app.models import get_logger

logger = get_logger(__name__)

# Valores padrão (podem ser alterados em Configurações > Segurança)
PADROES = {
    'seguranca_sessao_horas': ('12', 'Horas sem uso até a sessão expirar'),
    'seguranca_max_tentativas': ('5', 'Tentativas de senha erradas antes de bloquear'),
    'seguranca_bloqueio_minutos': ('15', 'Minutos de bloqueio após errar a senha'),
    'seguranca_senha_minimo': ('6', 'Tamanho mínimo da senha'),
}

# Tentativas falhas em memória: chave (ip, login) -> lista de datas
_tentativas = {}
_trava = threading.Lock()


def _config_int(chave, minimo, maximo):
    padrao = int(PADROES[chave][0])
    try:
        valor = int(get_config(chave, padrao) or padrao)
    except (TypeError, ValueError):
        valor = padrao
    return max(minimo, min(maximo, valor))


def sessao_horas():
    return _config_int('seguranca_sessao_horas', 1, 720)


def max_tentativas():
    return _config_int('seguranca_max_tentativas', 3, 20)


def bloqueio_minutos():
    return _config_int('seguranca_bloqueio_minutos', 1, 1440)


def senha_minimo():
    return _config_int('seguranca_senha_minimo', 6, 64)


def garantir_configs_padrao():
    """Cria as chaves de segurança em configuracoes_sistema se ainda não existirem."""
    for chave, (valor, descricao) in PADROES.items():
        try:
            existe = executar_query(
                "SELECT id FROM configuracoes_sistema WHERE chave = %s", (chave,), fetch_one=True
            )
            if not existe:
                executar_query(
                    "INSERT INTO configuracoes_sistema (chave, valor, descricao) VALUES (%s, %s, %s)",
                    (chave, valor, descricao)
                )
        except Exception as e:
            logger.error(f"seguranca.garantir_configs_padrao: {e}")


def criar_tabela_acessos():
    """Tabela com o histórico de tentativas de login (sucesso e falha)."""
    try:
        executar_query("""
            CREATE TABLE IF NOT EXISTS log_acessos (
                id SERIAL PRIMARY KEY,
                login VARCHAR(50),
                usuario_id INTEGER,
                sucesso BOOLEAN NOT NULL,
                motivo VARCHAR(100),
                ip VARCHAR(45),
                navegador VARCHAR(255),
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_log_acessos_data ON log_acessos(data_hora DESC);
        """)
    except Exception as e:
        logger.error(f"seguranca.criar_tabela_acessos: {e}")


# -------------------------------------------------------------------------
# Tentativas e bloqueio
# -------------------------------------------------------------------------

def _limpar_antigas(lista, agora):
    janela = timedelta(minutes=bloqueio_minutos())
    return [t for t in lista if agora - t < janela]


def esta_bloqueado(ip, login):
    """Retorna quantos minutos faltam para desbloquear (0 = liberado)."""
    agora = datetime.now()
    chave = (ip or '-', (login or '').lower())
    with _trava:
        lista = _limpar_antigas(_tentativas.get(chave, []), agora)
        _tentativas[chave] = lista
        if len(lista) >= max_tentativas():
            restante = timedelta(minutes=bloqueio_minutos()) - (agora - lista[0])
            return max(1, int(restante.total_seconds() // 60) + 1)
    return 0


def registrar_falha(ip, login):
    agora = datetime.now()
    chave = (ip or '-', (login or '').lower())
    with _trava:
        lista = _limpar_antigas(_tentativas.get(chave, []), agora)
        lista.append(agora)
        _tentativas[chave] = lista
        return max(0, max_tentativas() - len(lista))


def limpar_falhas(ip, login):
    with _trava:
        _tentativas.pop((ip or '-', (login or '').lower()), None)


# -------------------------------------------------------------------------
# Registro de acessos
# -------------------------------------------------------------------------

def registrar_acesso(login, sucesso, motivo=None, usuario_id=None, ip=None, navegador=None):
    try:
        executar_query(
            "INSERT INTO log_acessos (login, usuario_id, sucesso, motivo, ip, navegador) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            ((login or '')[:50], usuario_id, bool(sucesso), (motivo or '')[:100] or None,
             (ip or '')[:45], (navegador or '')[:255])
        )
    except Exception as e:
        logger.error(f"seguranca.registrar_acesso: {e}")


def listar_acessos(limite=100):
    try:
        return executar_query(
            "SELECT id, login, usuario_id, sucesso, motivo, ip, navegador, data_hora "
            "FROM log_acessos ORDER BY data_hora DESC LIMIT %s",
            (limite,), fetch_all=True, dict_cursor=True
        ) or []
    except Exception as e:
        logger.error(f"seguranca.listar_acessos: {e}")
        return []


def resumo_acessos(dias=7):
    try:
        r = executar_query(
            "SELECT COUNT(*) FILTER (WHERE sucesso) AS sucesso, "
            "COUNT(*) FILTER (WHERE NOT sucesso) AS falha "
            "FROM log_acessos WHERE data_hora >= CURRENT_TIMESTAMP - (%s || ' days')::interval",
            (str(dias),), fetch_one=True, dict_cursor=True
        )
        return {'sucesso': r['sucesso'] or 0, 'falha': r['falha'] or 0} if r else {'sucesso': 0, 'falha': 0}
    except Exception as e:
        logger.error(f"seguranca.resumo_acessos: {e}")
        return {'sucesso': 0, 'falha': 0}


# -------------------------------------------------------------------------
# Utilidades de sessão
# -------------------------------------------------------------------------

def ip_do_pedido(request):
    return request.remote_addr or '-'


def destino_seguro(destino):
    """Aceita só caminhos internos (evita redirecionar para outro site após o login)."""
    if not destino:
        return None
    partes = urlparse(destino)
    if partes.scheme or partes.netloc or not destino.startswith('/') or destino.startswith('//'):
        return None
    return destino


def usuario_ainda_ativo(user_id):
    """Confere no banco se o usuário continua ativo e qual o nível atual."""
    try:
        return executar_query(
            "SELECT id, nome, login, tipo FROM usuarios WHERE id = %s AND ativo = TRUE",
            (user_id,), fetch_one=True, dict_cursor=True
        )
    except Exception as e:
        logger.error(f"seguranca.usuario_ainda_ativo: {e}")
        return {'id': user_id}  # em falha de banco não derruba a sessão


# -------------------------------------------------------------------------
# Diagnóstico exibido em Configurações > Segurança
# -------------------------------------------------------------------------

def diagnostico(app):
    itens = []
    chave = app.config.get('SECRET_KEY') or ''
    itens.append({
        'ok': len(chave) >= 32 and app.config.get('SECRET_KEY_ORIGEM') != 'padrao',
        'titulo': 'Chave de proteção da sessão',
        'detalhe': ('Chave forte gerada automaticamente.' if app.config.get('SECRET_KEY_ORIGEM') == 'arquivo'
                    else 'Chave definida no arquivo .env.' if len(chave) >= 32
                    else 'Chave curta ou padrão: defina SECRET_KEY com 32+ caracteres no .env.'),
    })
    itens.append({
        'ok': not app.debug,
        'titulo': 'Modo de depuração (debug)',
        'detalhe': ('Desligado.' if not app.debug else
                    'Ligado: mostra detalhes internos em caso de erro. Use FLASK_DEBUG=False no .env '
                    'quando o sistema for usado por outras pessoas na rede.'),
    })
    itens.append({
        'ok': bool(app.config.get('SESSION_COOKIE_SECURE')),
        'titulo': 'Conexão segura (HTTPS)',
        'detalhe': ('Cookies só trafegam por HTTPS.' if app.config.get('SESSION_COOKIE_SECURE') else
                    'O sistema roda em HTTP. Na rede da fazenda é aceitável; para acesso pela internet use HTTPS '
                    'e SESSION_COOKIE_SECURE=True no .env.'),
    })
    admin_padrao = False
    try:
        from werkzeug.security import check_password_hash
        r = executar_query("SELECT senha_hash FROM usuarios WHERE login = 'admin' AND ativo = TRUE",
                           fetch_one=True, dict_cursor=True)
        if r and r['senha_hash']:
            try:
                admin_padrao = check_password_hash(r['senha_hash'], 'admin123')
            except Exception:
                admin_padrao = False
    except Exception:
        pass
    itens.append({
        'ok': not admin_padrao,
        'titulo': 'Senha padrão do administrador',
        'detalhe': ('O usuário "admin" ainda usa a senha padrão admin123. Troque agora.' if admin_padrao
                    else 'Nenhum usuário com a senha padrão de instalação.'),
    })
    itens.append({
        'ok': True,
        'titulo': 'Proteção contra tentativas de senha',
        'detalhe': f'Bloqueio de {bloqueio_minutos()} min após {max_tentativas()} senhas erradas.',
    })
    return itens
