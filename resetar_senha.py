from config.database import executar_query
from werkzeug.security import generate_password_hash

nova_senha_hash = generate_password_hash("admin123")

executar_query(
    "UPDATE usuarios SET senha_hash = %s WHERE login = 'admin'",
    (nova_senha_hash,)
)

print("Senha do admin resetada para: admin123")

# Testar
from app.modules.auth import validar_usuario
user = validar_usuario("admin", "admin123")
if user:
    print(f"SUCESSO! Login funciona: {user}")
else:
    print("FALHA ainda!")