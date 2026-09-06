from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules import auth

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        user = auth.validar_usuario(usuario, senha)
        if user:
            session['user_id'] = user['id']
            session['usuario'] = user['nome']
            session['tipo'] = user.get('tipo', 'user')
            return redirect(url_for('dashboard.index'))
        flash('Usuario ou senha invalidos.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

from flask import session, redirect, url_for, render_template, flash, request
from app.modules.auth import autenticar_usuario, buscar_usuario_por_login
from werkzeug.security import generate_password_hash
from config.database import executar_query
from app.modules.login_manager import login_required

@auth_bp.route('/perfil')
@login_required
def perfil():
    """Página de perfil do usuário logado."""
    return render_template('perfil.html')

@auth_bp.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    """Permite o usuário trocar a própria senha."""
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    confirmar = request.form.get('confirmar_senha')

    if not senha_atual or not nova_senha:
        flash('Preencha todos os campos.', 'error')
        return redirect(url_for('auth.perfil'))

    if nova_senha != confirmar:
        flash('As senhas não coincidem.', 'error')
        return redirect(url_for('auth.perfil'))

    if len(nova_senha) < 6:
        flash('A nova senha deve ter pelo menos 6 caracteres.', 'error')
        return redirect(url_for('auth.perfil'))

    # Verificar senha atual
    login = session.get('login')
    usuario, erro = autenticar_usuario(login, senha_atual)
    if not usuario:
        flash('Senha atual incorreta.', 'error')
        return redirect(url_for('auth.perfil'))

    # Atualizar senha
    novo_hash = generate_password_hash(nova_senha)
    try:
        executar_query(
            "UPDATE usuarios SET senha_hash = %s WHERE login = %s",
            (novo_hash, login)
        )
        flash('Senha alterada com sucesso!', 'success')
    except Exception as e:
        flash('Erro ao alterar senha.', 'error')

    return redirect(url_for('auth.perfil'))