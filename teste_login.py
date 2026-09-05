from config.database import executar_query

print("=== TESTE DE LOGIN ===")

# 1. Tabela existe?
try:
    r = executar_query("SELECT COUNT(*) FROM usuarios", fetch_one=True)
    print(f"Total de usuarios na tabela: {r[0]}")
except Exception as e:
    print(f"ERRO ao acessar tabela: {e}")
    print("A tabela usuarios provavelmente nao existe!")
    exit()

# 2. Usuario admin existe?
try:
    r = executar_query("SELECT id, nome, login, senha_hash FROM usuarios WHERE login = 'admin'", fetch_one=True)
    if r:
        print(f"Usuario encontrado:")
        print(f"  ID: {r[0]}")
        print(f"  Nome: {r[1]}")
        print(f"  Login: {r[2]}")
        print(f"  Hash: {r[3][:30]}...")
    else:
        print("Usuario 'admin' NAO encontrado na tabela!")
        print("Criando usuario admin agora...")
        from werkzeug.security import generate_password_hash
        senha_hash = generate_password_hash("admin123")
        executar_query(
            "INSERT INTO usuarios (nome, login, senha_hash, tipo, ativo) VALUES (%s, %s, %s, %s, TRUE)",
            ("Administrador", "admin", senha_hash, "admin")
        )
        print("Usuario admin criado com sucesso!")
except Exception as e:
    print(f"ERRO: {e}")

# 3. Testar autenticacao
print("\n=== TESTANDO AUTENTICACAO ===")
from app.modules.auth import validar_usuario
user = validar_usuario("admin", "admin123")
if user:
    print(f"SUCESSO! Usuario autenticado: {user}")
else:
    print("FALHA! Nao foi possivel autenticar admin/admin123")