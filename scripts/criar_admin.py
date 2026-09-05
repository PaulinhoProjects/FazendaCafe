"""
Script para criar o primeiro usuário administrador
Execute apenas uma vez!
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
from modules.auth import criar_usuario

# ALTERE AQUI
NOME = "Paulo"  # Seu nome
LOGIN = "paulo"
SENHA = "admin123"  # Mude depois!
NIVEL = "admin"

print("Criando usuário administrador...")
sucesso, resultado = criar_usuario(NOME, LOGIN, SENHA, NIVEL)

if sucesso:
    print(f"✅ Usuário criado com sucesso! ID: {resultado}")
    print(f"Login: {LOGIN}")
    print(f"Senha: {SENHA} (MUDE DEPOIS NO SISTEMA!)")
else:
    print(f"❌ Erro: {resultado}")