"""
Script para restaurar um backup em caso de emergência
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path

# Configurações
# Conexão lida do .env (mesmo arquivo usado pelo sistema). Nunca escreva a senha aqui.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass
DB_NAME = os.environ.get("DB_NAME", "fazenda_cafe")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

BASE_DIR = Path(__file__).parent.parent
BACKUP_DIR = BASE_DIR / "database" / "backups"

def listar_backups():
    """Lista todos os backups disponíveis"""
    backups = sorted(BACKUP_DIR.glob("backup_*.sql"), key=os.path.getmtime, reverse=True)
    
    print("\n" + "="*50)
    print("BACKUPS DISPONÍVEIS")
    print("="*50)
    
    if not backups:
        print("Nenhum backup encontrado!")
        return []
    
    for i, backup in enumerate(backups, 1):
        tamanho = backup.stat().st_size / 1024
        data_mod = datetime.datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{i}. {backup.name} - {tamanho:.2f} KB - {data_mod.strftime('%d/%m/%Y %H:%M')}")
    
    return backups

def restaurar_backup(arquivo_backup):
    """Restaura um backup no banco de dados"""
    print(f"\n⚠️  ATENÇÃO: Isso vai SUBSTITUIR todo o banco de dados atual!")
    print(f"Banco: {DB_NAME}")
    print(f"Backup: {arquivo_backup.name}")
    
    confirmar = input("\nTem certeza? (digite 'RESTAURAR' para confirmar): ")
    
    if confirmar != "RESTAURAR":
        print("Operação cancelada.")
        return False
    
    try:
        # Comando para restaurar
        comando = [
            "pg_restore",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-d", DB_NAME,
            "-c",  # Limpa (drop) objetos antes de criar
            "-v",  # Verboso
            str(arquivo_backup)
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASSWORD
        
        print("\nIniciando restauração...")
        print("Isso pode levar alguns minutos...\n")
        
        resultado = subprocess.run(
            comando,
            env=env,
            capture_output=True,
            text=True
        )
        
        if resultado.returncode == 0:
            print("\n✅ Banco de dados restaurado com sucesso!")
            return True
        else:
            print("\n❌ Erro na restauração:")
            print(resultado.stderr)
            return False
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return False

if __name__ == "__main__":
    backups = listar_backups()
    
    if backups:
        try:
            opcao = int(input("\nEscolha o número do backup para restaurar (0 para cancelar): "))
            if opcao == 0:
                print("Operação cancelada.")
            elif 1 <= opcao <= len(backups):
                restaurar_backup(backups[opcao-1])
            else:
                print("Opção inválida!")
        except ValueError:
            print("Digite um número válido!")