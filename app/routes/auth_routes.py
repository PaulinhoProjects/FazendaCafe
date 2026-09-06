from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules import auth
from app.modules.login_manager import login_required
from werkzeug.security import generate_password_hash
from config.database import executar_query

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
            session['login'] = user['login']
            session['tipo'] = user.get('tipo', 'user')
            return redirect(url_for('dashboard.index'))
        flash('Usuário ou senha inválidos.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')

@auth_bp.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
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

    login = session.get('login')
    if not login:
        flash('Sessão expirada. Faça login novamente.', 'error')
        return redirect(url_for('auth.login'))

    usuario, erro = auth.autenticar_usuario(login, senha_atual)
    if not usuario:
        flash('Senha atual incorreta.', 'error')
        return redirect(url_for('auth.perfil'))

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