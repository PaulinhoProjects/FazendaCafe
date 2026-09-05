"""
Configuração do Flask-Login para gerenciamento de sessões
"""

from flask_login import LoginManager, UserMixin
from flask import session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config')))
from modules.auth import autenticar_usuario

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
    from modules.auth import executar_query  # Import aqui para evitar circular
    query = "SELECT id, nome, login, nivel_acesso FROM usuarios WHERE id = %s AND ativo = TRUE"
    resultado = executar_query(query, (user_id,), fetch_one=True)
    if resultado:
        return Usuario(resultado[0], resultado[1], resultado[2], resultado[3])
    return None