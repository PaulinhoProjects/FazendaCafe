"""
Script de Backup Automático do Banco de Dados
Faz backup local e envia para a nuvem (Google Drive)
CORRIGIDO - Com caminho absoluto do pg_dump
"""

import os
import sys
import subprocess
import datetime
import shutil
from pathlib import Path

# CONFIGURAÇÕES - ALTERE AQUI CONFORME SUA INSTALAÇÃO
# ---------------------------------------------------
DB_NAME = "fazenda_cafe"
DB_USER = "postgres"
DB_PASSWORD = "Pcaf123."  # ALTERE PARA SUA SENHA
DB_HOST = "localhost"
DB_PORT = "5432"

# CAMINHO DO POSTGRESQL - VERIFIQUE QUAL É O SEU!
# Opções comuns:
# PG_PATH = r"C:\Program Files\PostgreSQL\16\bin"  # Versão 16
# PG_PATH = r"C:\Program Files\PostgreSQL\15\bin"  # Versão 15
PG_PATH = r"C:\Program Files\PostgreSQL\18\bin"  # <-- ALTERE SE NECESSÁRIO
# ---------------------------------------------------

# Pastas
BASE_DIR = Path(__file__).parent.parent
BACKUP_DIR = BASE_DIR / "database" / "backups"
LOG_FILE = BASE_DIR / "logs" / "backup.log"

def log(mensagem, tipo="INFO"):
    """Registra mensagem no arquivo de log"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{tipo}] {mensagem}\n"
    
    # Criar pasta de logs se não existir
    LOG_FILE.parent.mkdir(exist_ok=True)
    
    # Escrever no arquivo
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha)
    
    # Mostrar no console também
    print(linha.strip())

def criar_backup_local():
    """Cria um backup do banco de dados PostgreSQL"""
    try:
        # Criar pasta de backup se não existir
        BACKUP_DIR.mkdir(exist_ok=True)
        
        # Verificar se o pg_dump existe
        pg_dump_path = os.path.join(PG_PATH, "pg_dump.exe")
        if not os.path.exists(pg_dump_path):
            log(f"❌ pg_dump não encontrado em: {pg_dump_path}", "ERRO")
            log("Verifique se o caminho do PostgreSQL está correto no script", "ERRO")
            return None
        
        # Nome do arquivo com data e hora
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo_backup = BACKUP_DIR / f"backup_{timestamp}.sql"
        
        # Comando pg_dump com caminho completo
        comando = [
            pg_dump_path,
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-F", "c",  # Formato custom (comprimido)
            "-f", str(arquivo_backup),
            DB_NAME
        ]
        
        log(f"Iniciando backup local: {arquivo_backup.name}")
        log(f"Comando: {' '.join(comando)}")
        
        # Configurar variável de ambiente PGPASSWORD
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASSWORD
        
        # Executar comando
        resultado = subprocess.run(
            comando,
            env=env,
            capture_output=True,
            text=True
        )
        
        if resultado.returncode == 0:
            # Verificar se o arquivo foi criado
            if arquivo_backup.exists():
                tamanho = arquivo_backup.stat().st_size
                log(f"✅ Backup criado com sucesso! Tamanho: {tamanho/1024:.2f} KB")
                
                # Manter apenas os últimos 7 backups locais
                limpar_backups_antigos(7)
                
                return str(arquivo_backup)
            else:
                log("❌ Arquivo de backup não foi criado", "ERRO")
                return None
        else:
            log(f"❌ Erro no pg_dump: {resultado.stderr}", "ERRO")
            return None
            
    except Exception as e:
        log(f"❌ Erro ao criar backup: {e}", "ERRO")
        return None

def limpar_backups_antigos(manter=7):
    """Mantém apenas os últimos 'manter' backups locais"""
    try:
        backups = sorted(BACKUP_DIR.glob("backup_*.sql"), key=os.path.getmtime)
        
        # Se tiver mais que o limite, apagar os mais antigos
        if len(backups) > manter:
            for backup in backups[:-manter]:
                backup.unlink()
                log(f"Backup antigo removido: {backup.name}")
    except Exception as e:
        log(f"Erro ao limpar backups antigos: {e}", "ERRO")

def sincronizar_com_nuvem():
    """Copia o último backup para a pasta da nuvem"""
    try:
        # Encontrar o backup mais recente
        backups = sorted(BACKUP_DIR.glob("backup_*.sql"), key=os.path.getmtime)
        if not backups:
            log("Nenhum backup local encontrado para sincronizar", "AVISO")
            return False
        
        ultimo_backup = backups[-1]
        
        # Verificar se existe pasta do Google Drive
        possiveis_pastas = [
            Path("C:/Users/paulo/Google Drive"),
            Path("C:/Users/paulo/Google Drive/Meu Drive"),
            Path("C:/Users/paulo/Dropbox"),
            Path("C:/Users/paulo/Dropbox (Pessoal)"),
            Path("G:\Meu Drive"),
        ]
        
        pasta_nuvem = None
        for pasta in possiveis_pastas:
            if pasta.exists():
                pasta_nuvem = pasta / "FazendaCafe_Backup"
                break
        
        if not pasta_nuvem:
            log("⚠️ Pasta da nuvem não encontrada. Verifique se Google Drive/Dropbox está instalado", "AVISO")
            return False
        
        # Criar pasta de backup na nuvem
        pasta_nuvem.mkdir(exist_ok=True)
        
        # Copiar backup para a nuvem
        destino = pasta_nuvem / ultimo_backup.name
        shutil.copy2(ultimo_backup, destino)
        
        log(f"✅ Backup copiado para a nuvem: {destino}")
        
        # Manter apenas os últimos 30 backups na nuvem
        backups_nuvem = sorted(pasta_nuvem.glob("backup_*.sql"), key=os.path.getmtime)
        if len(backups_nuvem) > 30:
            for backup in backups_nuvem[:-30]:
                backup.unlink()
                log(f"Backup antigo removido da nuvem: {backup.name}")
        
        return True
        
    except Exception as e:
        log(f"❌ Erro ao sincronizar com nuvem: {e}", "ERRO")
        return False

def verificar_backup(arquivo_backup):
    """Verifica se o backup está íntegro"""
    try:
        # Caminho do pg_restore
        pg_restore_path = os.path.join(PG_PATH, "pg_restore.exe")
        
        # Comando para testar o backup
        comando = [
            pg_restore_path,
            "-l",  # Listar conteúdo (não restaura)
            str(arquivo_backup)
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASSWORD
        
        resultado = subprocess.run(
            comando,
            env=env,
            capture_output=True,
            text=True
        )
        
        if resultado.returncode == 0:
            log("✅ Backup verificado e íntegro")
            return True
        else:
            log(f"⚠️ Backup pode estar corrompido: {resultado.stderr}", "AVISO")
            return False
            
    except Exception as e:
        log(f"Erro ao verificar backup: {e}", "ERRO")
        return False

def criar_backup_completo():
    """Executa o processo completo de backup"""
    log("="*50)
    log("INICIANDO PROCESSO DE BACKUP")
    log("="*50)
    
    # 1. Backup local
    arquivo_backup = criar_backup_local()
    
    if arquivo_backup:
        # 2. Sincronizar com nuvem
        sincronizar_com_nuvem()
        
        # 3. Verificar integridade
        verificar_backup(arquivo_backup)
        
        log("✅ Processo de backup concluído com sucesso!")
    else:
        log("❌ Falha no processo de backup", "ERRO")
    
    log("="*50 + "\n")

if __name__ == "__main__":
    criar_backup_completo()