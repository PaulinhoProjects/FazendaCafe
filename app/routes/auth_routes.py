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