from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules.login_manager import login_required, admin_required
from app.modules import auth
from config.database import get_config, set_config, executar_query

config_bp = Blueprint('config', __name__, url_prefix='/configuracoes')

@config_bp.route('/')
@login_required
@admin_required
def index():
    configs = {}
    try:
        resultado = executar_query(
            "SELECT chave, valor, descricao FROM configuracoes_sistema ORDER BY chave",
            fetch_all=True, dict_cursor=True
        )
        for r in resultado:
            configs[r['chave']] = {'valor': r['valor'], 'descricao': r['descricao']}
    except Exception:
        pass

    usuarios = []
    try:
        usuarios = auth.listar_usuarios()
    except Exception:
        usuarios = []

    return render_template('config/index.html', configs=configs, usuarios=usuarios)

@config_bp.route('/salvar', methods=['POST'])
@login_required
@admin_required
def salvar():
    try:
        chaves = request.form.getlist('chaves')
        for chave in chaves:
            valor = request.form.get(f'valor_{chave}')
            if valor is not None:
                set_config(chave, valor)
        flash('Configurações salvas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao salvar: {e}', 'error')
    return redirect(url_for('config.index'))

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

    if not nome or not login or not senha:
        flash('Preencha nome, login e senha.', 'error')
    elif len(senha) < 6:
        flash('A senha deve ter no mínimo 6 caracteres.', 'error')
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
    if len(nova_senha) < 6:
        flash('A senha deve ter no mínimo 6 caracteres.', 'error')
    else:
        ok, msg = auth.alterar_senha_usuario(user_id, nova_senha)
        flash(msg, 'success' if ok else 'error')
    return redirect(url_for('config.index') + '#usuarios')