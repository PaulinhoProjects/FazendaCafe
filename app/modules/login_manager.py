"""
Configuração do Flask-Login para gerenciamento de sessões
"""
from flask_login import LoginManager, UserMixin
from flask import session, redirect, url_for, flash
from functools import wraps
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config')))
from app.modules.auth import autenticar_usuario

# Classe de usuário para o Flask-Login
class Usuario(UserMixin):
    def __init__(self, id, nome, login, nivel_acesso):
        self.id = id
        self.nome = nome
        self.login = login
        self.nivel_acesso = nivel_acesso

    def is_admin(self):
        return self.nivel_acesso == 'admin'

    def pode_editar(self):
        """Admin pode editar/excluir, usuários comuns não"""
        return self.nivel_acesso == 'admin'

    def pode_excluir(self):
        return self.nivel_acesso == 'admin'

# Configurar LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    """Carrega usuário da sessão"""
    from app.modules.auth import buscar_usuario_por_id
    resultado = buscar_usuario_por_id(user_id)
    if resultado:
        return Usuario(resultado.id, resultado.nome, resultado.login, resultado.tipo)
    return None

# =====================================================
# DECORATORS DE PROTEÇÃO DE ROTA
# =====================================================

def login_required(f):
    """Decorator que verifica se o usuário está logado."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator que verifica se o usuário é admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('tipo') != 'admin':
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function