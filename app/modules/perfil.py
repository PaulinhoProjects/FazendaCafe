"""
Perfil do usuário: dados pessoais, foto, cor do avatar e preferências.

A foto é recortada em quadrado, reduzida para 320 px e salva em WEBP
(sem metadados) em app/static/uploads/avatars/.
"""
import os
import re
import secrets
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query  # noqa: E402
from app.models import get_logger  # noqa: E402

logger = get_logger(__name__)

PASTA_AVATARES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'static', 'uploads', 'avatars')
TAMANHO_FOTO = 320
MAX_FOTO_MB = 5
EXTENSOES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.bmp'}

CORES = {
    'verde': 'Verde Kaldi', 'cereja': 'Cereja', 'terra': 'Terra',
    'azul': 'Azul', 'roxo': 'Roxo', 'grafite': 'Grafite',
}
PAGINAS_INICIAIS = {
    'dashboard.index': 'Dashboard',
    'manejo.visao_geral': 'Manejo do Cafezal',
    'manejo.calendario': 'Calendário do café',
    'pulverizacao.fila_aplicacao': 'Fila de aplicação',
    'estoque.dashboard': 'Estoque',
    'cotacoes.index': 'Cotações',
    'clima.index': 'Clima',
    'maquinario.dashboard': 'Maquinário',
}
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def garantir_colunas():
    """Acrescenta à tabela de usuários os campos do perfil (instalações antigas)."""
    try:
        executar_query("""
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email VARCHAR(150);
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telefone VARCHAR(30);
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cargo VARCHAR(80);
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto VARCHAR(120);
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cor_avatar VARCHAR(20);
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pagina_inicial VARCHAR(60);
        """)
        os.makedirs(PASTA_AVATARES, exist_ok=True)
    except Exception as e:
        logger.error(f"perfil.garantir_colunas: {e}")


def buscar(user_id):
    try:
        return executar_query("""
            SELECT id, nome, login, tipo, email, telefone, cargo, foto, cor_avatar,
                   pagina_inicial, data_cadastro, ultimo_acesso
            FROM usuarios WHERE id = %s AND ativo = TRUE
        """, (user_id,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"perfil.buscar: {e}")
        return None


def dados_sessao(user_id):
    """Campos do perfil guardados na sessão (foto e cor aparecem em todas as telas)."""
    u = buscar(user_id) or {}
    return {
        'foto': u.get('foto'),
        'cor_avatar': u.get('cor_avatar') if u.get('cor_avatar') in CORES else 'verde',
        'pagina_inicial': u.get('pagina_inicial') if u.get('pagina_inicial') in PAGINAS_INICIAIS else None,
    }


def atualizar_dados(user_id, dados):
    nome = (dados.get('nome') or '').strip()
    email = (dados.get('email') or '').strip().lower()
    telefone = re.sub(r'[^\d()+\- ]', '', dados.get('telefone') or '').strip()
    cargo = (dados.get('cargo') or '').strip()
    if len(nome) < 2:
        return False, 'Informe seu nome.'
    if email and not _EMAIL.match(email):
        return False, 'E-mail inválido.'
    try:
        executar_query("""
            UPDATE usuarios SET nome = %s, email = %s, telefone = %s, cargo = %s
            WHERE id = %s AND ativo = TRUE
        """, (nome[:100], email[:150] or None, telefone[:30] or None, cargo[:80] or None, user_id))
        return True, 'Dados do perfil atualizados.'
    except Exception as e:
        logger.error(f"perfil.atualizar_dados: {e}")
        return False, 'Não foi possível salvar os dados.'


def atualizar_preferencias(user_id, dados):
    cor = dados.get('cor_avatar') if dados.get('cor_avatar') in CORES else 'verde'
    pagina = dados.get('pagina_inicial') if dados.get('pagina_inicial') in PAGINAS_INICIAIS else None
    try:
        executar_query("UPDATE usuarios SET cor_avatar = %s, pagina_inicial = %s WHERE id = %s AND ativo = TRUE",
                       (cor, pagina, user_id))
        return True, 'Preferências salvas.'
    except Exception as e:
        logger.error(f"perfil.atualizar_preferencias: {e}")
        return False, 'Não foi possível salvar as preferências.'


def _apagar_arquivo(nome):
    if not nome or '/' in nome or '\\' in nome:
        return
    caminho = os.path.join(PASTA_AVATARES, nome)
    try:
        if os.path.isfile(caminho):
            os.remove(caminho)
    except OSError as e:
        logger.error(f"perfil._apagar_arquivo: {e}")


def salvar_foto(user_id, arquivo):
    """Valida a imagem, recorta em quadrado e grava. Retorna (ok, mensagem, nome_arquivo)."""
    if not arquivo or not arquivo.filename:
        return False, 'Escolha uma imagem.', None
    extensao = os.path.splitext(arquivo.filename)[1].lower()
    if extensao not in EXTENSOES:
        return False, 'Formato não aceito. Use JPG, PNG ou WEBP.', None
    conteudo = arquivo.read(MAX_FOTO_MB * 1024 * 1024 + 1)
    if len(conteudo) > MAX_FOTO_MB * 1024 * 1024:
        return False, f'A imagem passa de {MAX_FOTO_MB} MB.', None
    try:
        import io
        from PIL import Image, ImageOps
        imagem = Image.open(io.BytesIO(conteudo))
        imagem.verify()
        imagem = Image.open(io.BytesIO(conteudo))
        imagem = ImageOps.exif_transpose(imagem).convert('RGB')
        imagem = ImageOps.fit(imagem, (TAMANHO_FOTO, TAMANHO_FOTO), Image.LANCZOS, centering=(0.5, 0.4))
    except Exception as e:
        logger.error(f"perfil.salvar_foto (imagem invalida): {e}")
        return False, 'Não foi possível ler a imagem. Tente outra foto.', None

    os.makedirs(PASTA_AVATARES, exist_ok=True)
    nome = f"u{int(user_id)}_{secrets.token_hex(6)}.webp"
    try:
        imagem.save(os.path.join(PASTA_AVATARES, nome), 'WEBP', quality=86, method=6)
        anterior = (buscar(user_id) or {}).get('foto')
        executar_query("UPDATE usuarios SET foto = %s WHERE id = %s AND ativo = TRUE", (nome, user_id))
        _apagar_arquivo(anterior)
        return True, 'Foto atualizada.', nome
    except Exception as e:
        logger.error(f"perfil.salvar_foto: {e}")
        _apagar_arquivo(nome)
        return False, 'Não foi possível salvar a foto.', None


def remover_foto(user_id):
    try:
        anterior = (buscar(user_id) or {}).get('foto')
        executar_query("UPDATE usuarios SET foto = NULL WHERE id = %s", (user_id,))
        _apagar_arquivo(anterior)
        return True, 'Foto removida.'
    except Exception as e:
        logger.error(f"perfil.remover_foto: {e}")
        return False, 'Não foi possível remover a foto.'


def acessos(user_id, login, limite=8):
    """Entradas da conta e tentativas com senha errada usando o mesmo login."""
    try:
        return executar_query("""
            SELECT sucesso, motivo, ip, navegador, data_hora
            FROM log_acessos WHERE usuario_id = %s OR login = %s
            ORDER BY data_hora DESC LIMIT %s
        """, (user_id, login, limite), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"perfil.acessos: {e}")
        return []


def resumo_navegador(texto):
    """'Chrome no Windows' a partir do User-Agent."""
    t = (texto or '').lower()
    navegador = ('Edge' if 'edg/' in t else 'Chrome' if 'chrome' in t else 'Firefox' if 'firefox' in t
                 else 'Safari' if 'safari' in t else 'Navegador')
    sistema = ('Android' if 'android' in t else 'iPhone' if 'iphone' in t else 'Windows' if 'windows' in t
               else 'macOS' if 'mac os' in t else 'Linux' if 'linux' in t else '')
    return f"{navegador} no {sistema}" if sistema else navegador
