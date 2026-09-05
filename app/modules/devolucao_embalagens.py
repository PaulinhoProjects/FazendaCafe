"""
Módulo para gestão de devolução de embalagens - VERSÃO SIMPLIFICADA
Apenas registro da devolução, sem vínculo com produtos específicos
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

# =====================================================
# FUNÇÕES PARA DEVOLUÇÃO DE EMBALAGENS (SIMPLIFICADO)
# =====================================================

def listar_devolucoes(data_inicio=None, data_fim=None):
    """
    Lista todas as devoluções de embalagens
    Com opção de filtrar por período
    """
    query = """
    SELECT id, data_devolucao, local_devolucao, quantidade_embalagens,
           nome_responsavel, numero_comprovante, arquivo_pdf, observacoes,
           data_cadastro
    FROM devolucao_embalagens
    WHERE ativo = TRUE
    """
    params = []
    
    if data_inicio and data_fim:
        query += " AND data_devolucao BETWEEN %s AND %s"
        params.extend([data_inicio, data_fim])
    
    query += " ORDER BY data_devolucao DESC, id DESC"
    
    try:
        resultado = executar_query(query, params if params else None, fetch_all=True)
        devolucoes = []
        for r in resultado:
            devolucoes.append({
                'id': r[0],
                'data_devolucao': r[1],
                'local_devolucao': r[2],
                'quantidade_embalagens': r[3],
                'nome_responsavel': r[4],
                'numero_comprovante': r[5],
                'arquivo_pdf': r[6],
                'observacoes': r[7],
                'data_cadastro': r[8]
            })
        return devolucoes
    except Exception as e:
        print(f"Erro ao listar devoluções: {e}")
        return []

def buscar_devolucao_por_id(id):
    """Busca uma devolução específica pelo ID"""
    query = """
    SELECT id, data_devolucao, local_devolucao, quantidade_embalagens,
           nome_responsavel, numero_comprovante, arquivo_pdf, observacoes,
           data_cadastro
    FROM devolucao_embalagens
    WHERE id = %s AND ativo = TRUE
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'data_devolucao': r[1],
                'local_devolucao': r[2],
                'quantidade_embalagens': r[3],
                'nome_responsavel': r[4],
                'numero_comprovante': r[5],
                'arquivo_pdf': r[6],
                'observacoes': r[7],
                'data_cadastro': r[8]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar devolução: {e}")
        return None

def inserir_devolucao(dados, arquivo_pdf=None):
    """
    Insere um novo registro de devolução simplificado
    """
    query = """
    INSERT INTO devolucao_embalagens 
        (data_devolucao, local_devolucao, quantidade_embalagens,
         nome_responsavel, numero_comprovante, arquivo_pdf, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['data_devolucao'], dados['local_devolucao'], 
             dados['quantidade_embalagens'], dados.get('nome_responsavel'),
             dados.get('numero_comprovante'), arquivo_pdf, 
             dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir devolução: {e}")
        return None

def excluir_devolucao(id):
    """Exclusão lógica de uma devolução"""
    try:
        executar_query(
            "UPDATE devolucao_embalagens SET ativo = FALSE WHERE id = %s",
            (id,)
        )
        return True, "Devolução excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir devolução: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def get_resumo_devolucoes():
    """Retorna resumo estatístico das devoluções"""
    try:
        # Total de devoluções
        total = executar_query(
            "SELECT COUNT(*) FROM devolucao_embalagens WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Total de embalagens devolvidas
        total_embalagens = executar_query(
            "SELECT COALESCE(SUM(quantidade_embalagens), 0) FROM devolucao_embalagens WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Locais de coleta (distintos)
        locais = executar_query(
            "SELECT COUNT(DISTINCT local_devolucao) FROM devolucao_embalagens WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Devoluções no mês atual
        dev_mes = executar_query("""
            SELECT COUNT(*) FROM devolucao_embalagens 
            WHERE ativo = TRUE 
            AND EXTRACT(MONTH FROM data_devolucao) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM data_devolucao) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, fetch_one=True)[0]
        
        return {
            'total_devolucoes': total or 0,
            'total_embalagens': int(total_embalagens) if total_embalagens else 0,
            'locais_distintos': locais or 0,
            'devolucoes_mes': dev_mes or 0
        }
    except Exception as e:
        print(f"Erro ao obter resumo: {e}")
        return {
            'total_devolucoes': 0,
            'total_embalagens': 0,
            'locais_distintos': 0,
            'devolucoes_mes': 0
        }