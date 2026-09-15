"""
Módulo de conexão com o banco de dados PostgreSQL
CORRIGIDO - Versão estável com cálculo de pés de café
"""

import psycopg2
from psycopg2 import pool
import os
from datetime import datetime
import time
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

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
                    1,
                    10,
                    host=os.getenv("DB_HOST", "localhost"),
                    port=os.getenv("DB_PORT", "5432"),
                    database=os.getenv("DB_NAME", "fazenda_cafe"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD"),
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

def executar_query(query, parametros=None, fetch_one=False, fetch_all=False, dict_cursor=False):
    """
    Função genérica para executar queries SQL.
    dict_cursor=True  -> retorna dicts (linha['campo']) em vez de tuplas (r[0], r[1]...)
    dict_cursor=False -> comportamento idêntico ao original (nada quebra)
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

            if dict_cursor:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
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

def executar_transacao(funcao):
    """
    Executa `funcao(cursor)` dentro de UMA ÚNICA transação atômica.
    A função recebe um cursor pronto e pode rodar quantos comandos quiser.
    No fim: commit de tudo. Se QUALQUER exceção ocorrer: rollback de tudo.
    Atende a regra 6 do AGENTS.md (alteração de saldo = uma transação com rollback).
    Retorna o valor devolvido pela função.
    """
    conn = None
    cursor = None
    try:
        conn = ConexaoBanco.get_conexao()
        if not conn:
            raise Exception("Não foi possível obter conexão com o banco")

        # Garante que a conexão do pool comece sem transação pendente
        conn.rollback()

        cursor = conn.cursor()
        retorno = funcao(cursor)
        conn.commit()
        return retorno

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"Erro na transação (ROLLBACK aplicado): {e}")
        raise e

    finally:
        if cursor:
            cursor.close()
        if conn:
            ConexaoBanco.liberar_conexao(conn)

# =====================================================
# CONFIGURAÇÕES DO SISTEMA
# =====================================================

def criar_tabela_configuracoes():
    """Cria tabela de configurações do sistema."""
    query = """
    CREATE TABLE IF NOT EXISTS configuracoes_sistema (
        id SERIAL PRIMARY KEY,
        chave VARCHAR(100) UNIQUE NOT NULL,
        valor TEXT,
        descricao VARCHAR(255),
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    try:
        executar_query(query)
        # Inserir configurações padrão se não existirem
        configs_padrao = [
            ('nome_sistema', 'AgroCafé', 'Nome do sistema'),
            ('slogan', 'Tecnologia que Colhe Resultados', 'Slogan do sistema'),
            ('cidade', 'Campos Gerais', 'Cidade para clima'),
            ('estado', 'MG', 'Estado para clima'),
            ('api_clima_key', '', 'Chave da API OpenWeather'),
            ('itens_por_pagina', '20', 'Itens por página nas listagens'),
        ]
        for chave, valor, desc in configs_padrao:
            verificar = executar_query("SELECT id FROM configuracoes_sistema WHERE chave = %s", (chave,), fetch_one=True)
            if not verificar:
                executar_query(
                    "INSERT INTO configuracoes_sistema (chave, valor, descricao) VALUES (%s, %s, %s)",
                    (chave, valor, desc)
                )
        print("Tabela 'configuracoes_sistema' verificada/criada com sucesso!")
        return True
    except Exception as e:
        print(f"Erro ao criar tabela de configurações: {e}")
        return False

def get_config(chave, padrão=None):
    """Busca uma configuração do banco."""
    try:
        resultado = executar_query("SELECT valor FROM configuracoes_sistema WHERE chave = %s", (chave,), fetch_one=True)
        return resultado[0] if resultado else padrão
    except Exception:
        return padrão

def set_config(chave, valor):
    """Atualiza ou insere uma configuração."""
    try:
        existente = executar_query("SELECT id FROM configuracoes_sistema WHERE chave = %s", (chave,), fetch_one=True)
        if existente:
            executar_query("UPDATE configuracoes_sistema SET valor = %s, data_atualizacao = CURRENT_TIMESTAMP WHERE chave = %s", (valor, chave))
        else:
            executar_query("INSERT INTO configuracoes_sistema (chave, valor) VALUES (%s, %s)", (chave, valor))
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")
        return False

def corrigir_tabela_talhoes():
    """Adiciona colunas que possam estar faltando na tabela talhoes."""
    alteracoes = [
        "ALTER TABLE talhoes ADD COLUMN IF NOT EXISTS produtor_id INTEGER",
        "ALTER TABLE talhoes ADD COLUMN IF NOT EXISTS latitude NUMERIC(10,7)",
        "ALTER TABLE talhoes ADD COLUMN IF NOT EXISTS longitude NUMERIC(10,7)",
        "ALTER TABLE talhoes ADD COLUMN IF NOT EXISTS foto_url TEXT",
        "ALTER TABLE talhoes ADD COLUMN IF NOT EXISTS area_hectares NUMERIC(10,2)",
    ]
    for sql in alteracoes:
        try:
            executar_query(sql)
        except Exception as e:
            print(f"Aviso ao alterar tabela: {e}")
    print("Tabela talhoes verificada/atualizada!")

def criar_tabela_categorias_estoque():
    """Cria tabela de categorias e insere categorias padrao."""
    query = """
    CREATE TABLE IF NOT EXISTS categorias_estoque (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(50) UNIQUE NOT NULL,
        descricao VARCHAR(255),
        cor VARCHAR(20) DEFAULT 'secondary',
        ativo BOOLEAN DEFAULT TRUE
    )
    """
    executar_query(query)
    
    categorias = [
        ('Fungicida', 'Produtos para controle de fungos', 'danger'),
        ('Inseticida', 'Produtos para controle de insetos', 'warning'),
        ('Herbicida', 'Produtos para controle de plantas invasoras', 'success'),
        ('Acaricida', 'Produtos para controle de acaros', 'info'),
        ('Fertilizante', 'Fertilizantes quimicos e organicos', 'primary'),
        ('Adubo', 'Adubos compostos e simples', 'success'),
        ('Bioestimulante', 'Bioestimulantes e promotores de crescimento', 'info'),
        ('Spreader/Oleo', 'Spreader, oleos adesivos e espalhantes', 'secondary'),
        ('Outros', 'Produtos diversos', 'secondary'),
    ]
    for nome, desc, cor in categorias:
        existe = executar_query("SELECT id FROM categorias_estoque WHERE nome = %s", (nome,), fetch_one=True)
        if not existe:
            executar_query(
                "INSERT INTO categorias_estoque (nome, descricao, cor) VALUES (%s, %s, %s)",
                (nome, desc, cor)
            )
    print("Tabela categorias_estoque criada/verificada!")

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


# =====================================================
# TRANSAÇÕES ATÔMICAS
# =====================================================

@contextmanager
def transacao():
    """
    Executa várias queries em UMA única transação atômica.
    Só comita no final; se qualquer passo falhar, desfaz TUDO.

    Uso:
        with transacao() as cur:
            cur.execute("INSERT ... RETURNING id", (...,))
            mov_id = cur.fetchone()[0]
            cur.execute("UPDATE ...", (...,))
    """
    conn = ConexaoBanco.get_conexao()
    if not conn:
        raise Exception("Não foi possível obter conexão com o banco")
    cursor = None
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except:
            pass
        raise
    finally:
        if cursor:
            cursor.close()
        ConexaoBanco.liberar_conexao(conn)

def executar_query_dict(query, parametros=None, fetch_one=False, fetch_all=False):
    """Atalho: executar_query com dict_cursor=True (nomes de campo em vez de índices)."""
    return executar_query(query, parametros, fetch_one=fetch_one, fetch_all=fetch_all, dict_cursor=True)