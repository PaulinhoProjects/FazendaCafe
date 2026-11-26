import os
import importlib.util
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for, flash, session,
                   current_app, send_from_directory)
from app.modules.login_manager import login_required, admin_required
from app.modules import auth, seguranca
from config.database import get_config, set_config, executar_query
from app.models import get_logger

logger = get_logger(__name__)
config_bp = Blueprint('config', __name__, url_prefix='/configuracoes')

# Campos editáveis em cada aba (só estes podem ser gravados pelo formulário)
GRUPOS = {
    'fazenda': [
        ('nome_fazenda', 'Nome da fazenda', 'Aparece no rodapé dos relatórios em PDF.', 'text', ''),
        ('proprietario', 'Produtor responsável', 'Nome do produtor ou da empresa.', 'text', ''),
        ('cidade', 'Cidade', 'Usada na previsão do tempo.', 'text', 'Campos Gerais'),
        ('estado', 'Estado (UF)', 'Sigla com 2 letras, ex.: MG.', 'text', 'MG'),
    ],
    'sistema': [
        ('nome_sistema', 'Nome do sistema', 'Nome exibido em telas de configuração.', 'text', 'Kaldi'),
        ('slogan', 'Slogan', 'Frase exibida no login e nos rodapés.', 'text', 'Tecnologia que Colhe Resultados'),
        ('itens_por_pagina', 'Itens por página', 'Quantidade de linhas nas listagens.', 'number', '20'),
    ],
    'seguranca': [
        ('seguranca_sessao_horas', 'Sessão expira após (horas sem uso)', 'Entre 1 e 720 horas.', 'number', '12'),
        ('seguranca_max_tentativas', 'Tentativas de senha antes de bloquear', 'Entre 3 e 20.', 'number', '5'),
        ('seguranca_bloqueio_minutos', 'Tempo de bloqueio (minutos)', 'Entre 1 e 1440.', 'number', '15'),
        ('seguranca_senha_minimo', 'Tamanho mínimo de senha', 'Entre 6 e 64 caracteres.', 'number', '6'),
    ],
}

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_BACKUPS = os.path.join(PASTA_PROJETO, 'database', 'backups')


def _listar_backups():
    """Arquivos de backup do banco (mais recentes primeiro)."""
    arquivos = []
    try:
        for nome in os.listdir(PASTA_BACKUPS):
            caminho = os.path.join(PASTA_BACKUPS, nome)
            if os.path.isfile(caminho) and nome.endswith(('.sql', '.backup', '.dump')):
                info = os.stat(caminho)
                arquivos.append({
                    'nome': nome,
                    'tamanho_kb': info.st_size / 1024,
                    'data': datetime.fromtimestamp(info.st_mtime),
                })
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"config_routes._listar_backups: {e}")
    return sorted(arquivos, key=lambda a: a['data'], reverse=True)


def _status_banco():
    try:
        r = executar_query(
            "SELECT version() AS versao, pg_size_pretty(pg_database_size(current_database())) AS tamanho",
            fetch_one=True, dict_cursor=True
        )
        return {'ok': True, 'versao': (r['versao'] or '').split(',')[0], 'tamanho': r['tamanho']}
    except Exception as e:
        logger.error(f"config_routes._status_banco: {e}")
        return {'ok': False, 'versao': '-', 'tamanho': '-'}


@config_bp.route('/')
@login_required
@admin_required
def index():
    valores = {}
    try:
        resultado = executar_query(
            "SELECT chave, valor FROM configuracoes_sistema", fetch_all=True, dict_cursor=True
        ) or []
        valores = {r['chave']: r['valor'] for r in resultado}
    except Exception as e:
        logger.error(f"config_routes.index: {e}")

    try:
        usuarios = auth.listar_usuarios()
    except Exception as e:
        logger.error(f"config_routes.index usuarios: {e}")
        usuarios = []

    return render_template(
        'config/index.html',
        grupos=GRUPOS,
        valores=valores,
        usuarios=usuarios,
        diagnostico=seguranca.diagnostico(current_app),
        acessos=seguranca.listar_acessos(100),
        resumo_acessos=seguranca.resumo_acessos(7),
        backups=_listar_backups(),
        banco=_status_banco(),
        senha_minimo=seguranca.senha_minimo(),
    )


@config_bp.route('/salvar/<grupo>', methods=['POST'])
@login_required
@admin_required
def salvar(grupo):
    campos = GRUPOS.get(grupo)
    if not campos:
        flash('Grupo de configurações inválido.', 'error')
        return redirect(url_for('config.index'))
    try:
        for chave, rotulo, _ajuda, tipo, _padrao in campos:
            valor = (request.form.get(chave) or '').strip()
            if tipo == 'number' and not valor.isdigit():
                flash(f'"{rotulo}" precisa ser um número inteiro.', 'error')
                return redirect(url_for('config.index') + f'#{grupo}')
            if chave == 'estado':
                valor = valor.upper()[:2]
            set_config(chave, valor[:255])
        flash('Configurações salvas.', 'success')
    except Exception as e:
        logger.error(f"config_routes.salvar: {e}")
        flash('Não foi possível salvar as configurações.', 'error')
    return redirect(url_for('config.index') + f'#{grupo}')


@config_bp.route('/backup', methods=['POST'])
@login_required
@admin_required
def backup_agora():
    """Gera um backup do banco usando o script scripts/backup.py (pg_dump)."""
    try:
        caminho_script = os.path.join(PASTA_PROJETO, 'scripts', 'backup.py')
        especificacao = importlib.util.spec_from_file_location('kaldi_backup', caminho_script)
        modulo = importlib.util.module_from_spec(especificacao)
        especificacao.loader.exec_module(modulo)
        arquivo = modulo.criar_backup_local()
        if arquivo:
            flash(f'Backup criado: {os.path.basename(arquivo)}', 'success')
        else:
            flash('Não foi possível criar o backup. Veja logs/backup.log '
                  '(confira o caminho do PostgreSQL em PG_PATH).', 'error')
    except Exception as e:
        logger.error(f"config_routes.backup_agora: {e}")
        flash('Erro ao executar o backup. Detalhes no log do sistema.', 'error')
    return redirect(url_for('config.index') + '#backups')


@config_bp.route('/backup/<nome>')
@login_required
@admin_required
def baixar_backup(nome):
    """Baixa um arquivo de backup (só nomes que existem na pasta de backups)."""
    if nome not in {b['nome'] for b in _listar_backups()}:
        flash('Arquivo de backup não encontrado.', 'error')
        return redirect(url_for('config.index') + '#backups')
    return send_from_directory(PASTA_BACKUPS, nome, as_attachment=True)

# =====================================================
# GESTÃO DE USUÁRIOS
# =====================================================

@config_bp.route('/usuarios/novo', methods=['POST'])
@login_required
@admin_required
def usuario_novo():
    nome = (request.form.get('nome') or '').strip()
    login = (request.form.get('login') or '').strip()
    senha = request.form.get('senha') or ''
    tipo = request.form.get('tipo') or 'user'
    if tipo not in ('admin', 'operador', 'agronomista', 'user'):
        tipo = 'user'

    if not nome or not login or not senha:
        flash('Preencha nome, login e senha.', 'error')
    elif len(senha) < seguranca.senha_minimo():
        flash(f'A senha deve ter no mínimo {seguranca.senha_minimo()} caracteres.', 'error')
    else:
        ok, resultado = auth.criar_usuario(nome, login, senha, tipo)
        if ok:
            flash(f'Usuário "{nome}" criado com sucesso!', 'success')
        else:
            flash(f'Não foi possível criar: {resultado}', 'error')
    return redirect(url_for('config.index') + '#usuarios')

@config_bp.route('/usuarios/<int:user_id>/nivel', methods=['POST'])
@login_required
@admin_required
def usuario_nivel(user_id):
    novo_tipo = request.form.get('tipo') or 'user'
    if user_id == session.get('user_id') and novo_tipo != 'admin':
        flash('Você não pode rebaixar o seu próprio nível.', 'error')
    else:
        ok, msg = auth.alterar_nivel_usuario(user_id, novo_tipo, session.get('user_id'))
        flash(msg, 'success' if ok else 'error')
    return redirect(url_for('config.index') + '#usuarios')

@config_bp.route('/usuarios/<int:user_id>/desativar', methods=['POST'])
@login_required
@admin_required
def usuario_desativar(user_id):
    ok, msg = auth.desativar_usuario(user_id, session.get('user_id'))
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('config.index') + '#usuarios')

@config_bp.route('/usuarios/<int:user_id>/ativar', methods=['POST'])
@login_required
@admin_required
def usuario_ativar(user_id):
    ok, msg = auth.ativar_usuario(user_id)
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('config.index') + '#usuarios')

@config_bp.route('/usuarios/<int:user_id>/senha', methods=['POST'])
@login_required
@admin_required
def usuario_senha(user_id):
    nova_senha = request.form.get('nova_senha') or ''
    if len(nova_senha) < seguranca.senha_minimo():
        flash(f'A senha deve ter no mínimo {seguranca.senha_minimo()} caracteres.', 'error')
    else:
        ok, msg = auth.alterar_senha_usuario(user_id, nova_senha)
        flash(msg, 'success' if ok else 'error')
    return redirect(url_for('config.index') + '#usuarios')