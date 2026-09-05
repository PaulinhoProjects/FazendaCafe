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
        r = executar_query(query, (user_id,), fetch_one=True)
        if r:
            return Usuario(r[0], r[1], r[2], r[3])
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None

def buscar_usuario_por_login(login):
    query = "SELECT id, nome, login, tipo, senha_hash FROM usuarios WHERE login = %s AND ativo = TRUE"
    try:
        return executar_query(query, (login,), fetch_one=True)
    except Exception as e:
        print(f"Erro: {e}")
        return None

def autenticar_usuario(login, senha):
    usuario_data = buscar_usuario_por_login(login)
    if not usuario_data:
        return None, "Usuario nao encontrado"
    hash_banco = usuario_data[4]
    if not verificar_senha(hash_banco, senha):
        return None, "Senha incorreta"
    try:
        executar_query("UPDATE usuarios SET ultimo_acesso = %s WHERE id = %s", (datetime.now(), usuario_data[0]))
    except Exception:
        pass
    return {
        'id': usuario_data[0],
        'nome': usuario_data[1],
        'login': usuario_data[2],
        'tipo': usuario_data[3]
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
        resultado = executar_query(query, fetch_all=True)
        usuarios = []
        for r in resultado:
            usuarios.append({
                'id': r[0], 'nome': r[1], 'login': r[2], 'tipo': r[3],
                'ativo': r[4], 'data_cadastro': r[5], 'ultimo_acesso': r[6]
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
    if novo_tipo not in ['admin', 'user', 'agronomista', 'produtor']:
        return False, "Tipo invalido"
    try:
        executar_query("UPDATE usuarios SET tipo = %s WHERE id = %s", (novo_tipo, user_id))
        return True, "Nivel alterado"
    except Exception as e:
        return False, str(e)