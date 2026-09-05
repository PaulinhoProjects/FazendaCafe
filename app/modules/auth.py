"""
Módulo de Autenticação e Controle de Usuários
Gerencia login, logout, criação de usuários e permissões
"""

import sys
import os
import hashlib
from config.database import executar_query
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

class Usuario(UserMixin):
    def __init__(self, id, nome, login, tipo):
        self.id = id
        self.nome = nome
        self.login = login
        self.tipo = tipo
    
    @property
    def is_admin(self):
        return self.tipo == 'admin'
    
    def get_id(self):
        return str(self.id)

def verificar_senha(hash_armazenado, senha):
    """Verifica se a senha coincide com hash werkzeug ou sha256 legado."""
    if not hash_armazenado or not senha:
        return False
    try:
        if check_password_hash(hash_armazenado, senha):
            return True
    except Exception:
        pass
    if hashlib.sha256(senha.encode()).hexdigest() == hash_armazenado:
        return True
    if hash_armazenado == senha:
        return True
    return False

def criar_tabela_usuarios():
    query = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        produtor_id INTEGER,
        nome VARCHAR(100) NOT NULL,
        login VARCHAR(50) UNIQUE NOT NULL,
        senha_hash VARCHAR(200) NOT NULL,
        tipo VARCHAR(20) NOT NULL DEFAULT 'user',
        ativo BOOLEAN DEFAULT TRUE,
        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ultimo_acesso TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login);
    """
    try:
        executar_query(query)
        # Verificar se existe admin padrão
        count_res = executar_query("SELECT COUNT(*) FROM usuarios", fetch_one=True)
        count = count_res[0] if count_res else 0
        if count == 0:
            criar_usuario("Administrador", "admin", "admin123", "admin")
            print("Usuário admin padrão criado: admin / admin123")
        return True
    except Exception as e:
        print(f"Erro ao criar tabela de usuários: {e}")
        return False

def buscar_usuario_por_id(user_id):
    """Busca usuário pelo ID (usado pelo Flask-Login)"""
    query = "SELECT id, nome, login, tipo FROM usuarios WHERE id = %s AND ativo = TRUE"
    try:
        resultado = executar_query(query, (user_id,), fetch_one=True)
        if resultado:
            return Usuario(resultado['id'], resultado['nome'], resultado['login'], resultado['tipo'])
        return None
    except Exception as e:
        print(f"Erro ao buscar usuário por ID: {e}")
        return None

def buscar_usuario_por_login(login):
    """Busca usuário por login/email (para autenticação)"""
    query = "SELECT id, nome, login, tipo, senha_hash FROM usuarios WHERE login = %s AND ativo = TRUE"
    try:
        return executar_query(query, (login,), fetch_one=True)
    except Exception as e:
        print(f"Erro ao buscar usuário por login: {e}")
        return None

def autenticar_usuario(login, senha):
    """
    Verifica credenciais e retorna (dados_usuario, erro)
    Se sucesso, dados_usuario é um dicionário com id, nome, login, tipo
    Se falha, dados_usuario = None e erro é uma string
    """
    usuario_data = buscar_usuario_por_login(login)
    if not usuario_data:
        return None, "Usuário não encontrado"
    
    hash_banco = usuario_data['senha_hash']
    if not verificar_senha(hash_banco, senha):
        return None, "Senha incorreta"
    
    # Atualizar último acesso se possível
    try:
        query = "UPDATE usuarios SET ultimo_acesso = %s WHERE id = %s"
        executar_query(query, (datetime.now(), usuario_data['id']))
    except Exception:
        pass
    
    return {
        'id': usuario_data['id'],
        'nome': usuario_data['nome'],
        'login': usuario_data['login'],
        'tipo': usuario_data['tipo']
    }, None

def validar_usuario(login, senha):
    """Função utilitária que retorna o usuário se autenticado com sucesso."""
    usuario, erro = autenticar_usuario(login, senha)
    return usuario

def criar_usuario(nome, login, senha, tipo='user'):
    """
    Cria um novo usuário.
    Retorna (sucesso: bool, mensagem ou id)
    """
    if buscar_usuario_por_login(login):
        return False, "Login já cadastrado"
    
    senha_hash = generate_password_hash(senha)
    query = """
    INSERT INTO usuarios (nome, login, senha_hash, tipo, ativo)
    VALUES (%s, %s, %s, %s, TRUE) RETURNING id
    """
    try:
        resultado = executar_query(query, (nome, login, senha_hash, tipo), fetch_one=True)
        if resultado:
            return True, resultado['id']
        return False, "Erro ao criar usuário"
    except Exception as e:
        return False, str(e)

def listar_usuarios():
    """Retorna lista de todos os usuários (para admin)"""
    query = """
    SELECT id, nome, login, tipo, ativo, data_cadastro, ultimo_acesso
    FROM usuarios ORDER BY id
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        usuarios = []
        for r in resultado:
            usuarios.append({
                'id': r['id'],
                'nome': r['nome'],
                'login': r['login'],
                'tipo': r['tipo'],
                'ativo': r['ativo'],
                'data_cadastro': r['data_cadastro'],
                'ultimo_acesso': r['ultimo_acesso']
            })
        return usuarios
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []

def desativar_usuario(user_id, admin_id):
    """
    Desativa um usuário (apenas admin pode).
    Retorna (sucesso, mensagem)
    """
    if str(user_id) == str(admin_id):
        return False, "Não é possível desativar seu próprio usuário"
    
    query = "UPDATE usuarios SET ativo = FALSE WHERE id = %s"
    try:
        executar_query(query, (user_id,))
        return True, "Usuário desativado com sucesso"
    except Exception as e:
        return False, str(e)

def alterar_nivel_usuario(user_id, novo_tipo, admin_id):
    """
    Altera o nível de acesso de um usuário.
    Retorna (sucesso, mensagem)
    """
    if novo_tipo not in ['admin', 'user', 'agronomista', 'produtor']:
        return False, "Tipo inválido"
    
    query = "UPDATE usuarios SET tipo = %s WHERE id = %s"
    try:
        executar_query(query, (novo_tipo, user_id))
        return True, "Nível alterado com sucesso"
    except Exception as e:
        return False, str(e)