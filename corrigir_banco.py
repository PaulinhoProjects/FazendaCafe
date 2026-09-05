from config.database import executar_query

print("Corrigindo tabela usuarios...")

try:
    executar_query("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_acesso TIMESTAMP")
    print("Coluna ultimo_acesso adicionada com sucesso!")
except Exception as e:
    print(f"Erro: {e}")

# Confirmar
r = executar_query("SELECT id, nome, login FROM usuarios WHERE login = 'admin'", fetch_one=True)
print(f"Admin no banco: ID={r[0]}, Nome={r[1]}, Login={r[2]}")