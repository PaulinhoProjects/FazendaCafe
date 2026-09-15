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
        count_res = executar_query("SELECT COUNT(*) FROM usuarios", fetch_one=True)
        count = count_res[0] if count_res else 0
        if count == 0:
            criar_usuario("Administrador", "admin", "admin123", "admin")
            print("Usuario admin padrao criado: admin / admin123")
        return True
    except Exception as e:
        print(f"Erro ao criar tabela: {e}")
        return False

def buscar_usuario_por_id(user_id):
    query = "SELECT id, nome, login, tipo FROM usuarios WHERE id = %s AND ativo = TRUE"
    try:
        r = executar_query(query, (user_id,), fetch_one=True, dict_cursor=True)
        if r:
            return Usuario(r['id'], r['nome'], r['login'], r['tipo'])
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None

def buscar_usuario_por_login(login):
    query = "SELECT id, nome, login, tipo, senha_hash FROM usuarios WHERE login = %s AND ativo = TRUE"
    try:
        return executar_query(query, (login,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        print(f"Erro: {e}")
        return None

def autenticar_usuario(login, senha):
    usuario_data = buscar_usuario_por_login(login)
    if not usuario_data:
        return None, "Usuario nao encontrado"
    hash_banco = usuario_data['senha_hash']
    if not verificar_senha(hash_banco, senha):
        return None, "Senha incorreta"
    try:
        executar_query("UPDATE usuarios SET ultimo_acesso = %s WHERE id = %s", (datetime.now(), usuario_data['id']))
    except Exception:
        pass
    return {
        'id': usuario_data['id'],
        'nome': usuario_data['nome'],
        'login': usuario_data['login'],
        'tipo': usuario_data['tipo']
    }, None

def validar_usuario(login, senha):
    usuario, erro = autenticar_usuario(login, senha)
    return usuario

def criar_usuario(nome, login, senha, tipo='user'):
    if buscar_usuario_por_login(login):
        return False, "Login ja cadastrado"
    senha_hash = generate_password_hash(senha)
    query = """
    INSERT INTO usuarios (nome, login, senha_hash, tipo, ativo)
    VALUES (%s, %s, %s, %s, TRUE) RETURNING id
    """
    try:
        resultado = executar_query(query, (nome, login, senha_hash, tipo), fetch_one=True)
        if resultado:
            return True, resultado[0]
        return False, "Erro ao criar usuario"
    except Exception as e:
        return False, str(e)

def listar_usuarios():
    query = "SELECT id, nome, login, tipo, ativo, data_cadastro, ultimo_acesso FROM usuarios ORDER BY id"
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        usuarios = []
        for r in resultado:
            usuarios.append({
                'id': r['id'], 'nome': r['nome'], 'login': r['login'], 'tipo': r['tipo'],
                'ativo': r['ativo'], 'data_cadastro': r['data_cadastro'], 'ultimo_acesso': r['ultimo_acesso']
            })
        return usuarios
    except Exception as e:
        print(f"Erro: {e}")
        return []

def desativar_usuario(user_id, admin_id):
    if str(user_id) == str(admin_id):
        return False, "Nao pode desativar proprio usuario"
    try:
        executar_query("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (user_id,))
        return True, "Usuario desativado"
    except Exception as e:
        return False, str(e)

def alterar_nivel_usuario(user_id, novo_tipo, admin_id):
    if novo_tipo not in ['admin', 'operador', 'agronomista', 'produtor', 'user']:
        return False, "Tipo invalido"
    try:
        executar_query("UPDATE usuarios SET tipo = %s WHERE id = %s", (novo_tipo, user_id))
        return True, "Nivel alterado"
    except Exception as e:
        return False, str(e)


def ativar_usuario(user_id):
    """Reativa um usuário previamente desativado."""
    try:
        executar_query("UPDATE usuarios SET ativo = TRUE WHERE id = %s", (user_id,))
        return True, "Usuário reativado com sucesso"
    except Exception as e:
        return False, str(e)

def alterar_senha_usuario(user_id, nova_senha):
    """Redefine a senha de um usuário (uso administrativo)."""
    try:
        senha_hash = generate_password_hash(nova_senha)
        executar_query("UPDATE usuarios SET senha_hash = %s WHERE id = %s", (senha_hash, user_id))
        return True, "Senha redefinida com sucesso"
    except Exception as e:
        return False, str(e)