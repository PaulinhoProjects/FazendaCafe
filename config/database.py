"""
Módulo de conexão com o banco de dados PostgreSQL
CORRIGIDO - Versão estável com cálculo de pés de café
"""

import psycopg2
from psycopg2 import pool
import os
from datetime import datetime
import time

class ConexaoBanco:
    """
    Gerencia a conexão com o banco de dados usando pool de conexões
    """
    _pool = None
    _inicializado = False
    
    @classmethod
    def inicializar_pool(cls):
        """Inicializa o pool de conexões (apenas uma vez)"""
        if cls._pool is None:
            try:
                print(f"[{datetime.now()}] Inicializando pool de conexões...")
                cls._pool = psycopg2.pool.SimpleConnectionPool(
                    1, 10,
                    host="localhost",
                    port="5432",
                    database="fazenda_cafe",
                    user="postgres",
                    password="Pcaf123."
                )
                cls._inicializado = True
                print(f"[{datetime.now()}] Pool de conexões inicializado com sucesso!")
                return True
            except Exception as e:
                print(f"[{datetime.now()}] ERRO ao inicializar pool: {e}")
                cls._pool = None
                cls._inicializado = False
                return False
        return True
    
    @classmethod
    def get_conexao(cls):
        """Pega uma conexão do pool"""
        if not cls._inicializado or cls._pool is None:
            print("Pool não inicializado. Inicializando agora...")
            if not cls.inicializar_pool():
                return None
        
        try:
            conn = cls._pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return conn
        except Exception as e:
            print(f"Erro ao pegar conexão: {e}")
            cls._pool = None
            cls._inicializado = False
            return None
    
    @classmethod
    def liberar_conexao(cls, conn):
        """Devolve a conexão para o pool"""
        try:
            if cls._pool and conn:
                cls._pool.putconn(conn)
        except Exception as e:
            print(f"Erro ao liberar conexão: {e}")
    
    @classmethod
    def fechar_pool(cls):
        """Fecha todas as conexões"""
        try:
            if cls._pool:
                print(f"[{datetime.now()}] Fechando pool de conexões...")
                cls._pool.closeall()
                cls._pool = None
                cls._inicializado = False
                print("Pool de conexões fechado.")
        except Exception as e:
            print(f"Erro ao fechar pool: {e}")

# =====================================================
# FUNÇÕES AUXILIARES DE QUERY
# =====================================================

def executar_query(query, parametros=None, fetch_one=False, fetch_all=False):
    """
    Função genérica para executar queries SQL
    """
    conn = None
    cursor = None
    resultado = None
    tentativas = 0
    max_tentativas = 3
    
    while tentativas < max_tentativas:
        try:
            conn = ConexaoBanco.get_conexao()
            if not conn:
                raise Exception("Não foi possível obter conexão com o banco")
            
            cursor = conn.cursor()
            cursor.execute(query, parametros or ())
            
            if fetch_one:
                resultado = cursor.fetchone()
            elif fetch_all:
                resultado = cursor.fetchall()
            
            conn.commit()
            return resultado
            
        except Exception as e:
            print(f"Erro na query (tentativa {tentativas + 1}): {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            tentativas += 1
            if tentativas < max_tentativas:
                time.sleep(1)
            else:
                raise e
                
        finally:
            if cursor:
                cursor.close()
            if conn:
                ConexaoBanco.liberar_conexao(conn)

# =====================================================
# TESTE
# =====================================================
if __name__ == "__main__":
    print("Testando conexão com o banco de dados...")
    
    if ConexaoBanco.inicializar_pool():
        print("Conexão com o banco de dados OK!")
        ConexaoBanco.fechar_pool()
    else:
        print("Falha ao inicializar pool de conexões")