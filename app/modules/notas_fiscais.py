"""
Módulo para gestão de Notas Fiscais de entrada de produtos
Permite upload de PDF e vinculação com movimentações
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

# =====================================================
# FUNÇÕES PARA NOTAS FISCAIS
# =====================================================

def listar_notas(data_inicio=None, data_fim=None, fornecedor=None):
    """
    Lista todas as notas fiscais com opção de filtros
    """
    query = """
    SELECT n.id, n.numero_nota, n.serie, n.data_emissao, n.data_recebimento,
           n.fornecedor, n.cnpj_fornecedor, n.valor_total, n.arquivo_pdf,
           n.observacoes, n.data_cadastro,
           COUNT(m.id) as total_produtos
    FROM notas_fiscais n
    LEFT JOIN movimentacoes_estoque m ON m.nota_fiscal_id = n.id AND m.tipo = 'entrada'
    WHERE n.ativo = TRUE
    """
    params = []
    
    if data_inicio and data_fim:
        query += " AND n.data_recebimento BETWEEN %s AND %s"
        params.extend([data_inicio, data_fim])
    
    if fornecedor:
        query += " AND n.fornecedor ILIKE %s"
        params.append(f"%{fornecedor}%")
    
    query += " GROUP BY n.id ORDER BY n.data_recebimento DESC, n.id DESC"
    
    try:
        resultado = executar_query(query, params if params else None, fetch_all=True)
        notas = []
        for r in resultado:
            notas.append({
                'id': r[0],
                'numero_nota': r[1],
                'serie': r[2],
                'data_emissao': r[3],
                'data_recebimento': r[4],
                'fornecedor': r[5],
                'cnpj_fornecedor': r[6],
                'valor_total': float(r[7]) if r[7] else None,
                'arquivo_pdf': r[8],
                'observacoes': r[9],
                'data_cadastro': r[10],
                'total_produtos': r[11]
            })
        return notas
    except Exception as e:
        print(f"Erro ao listar notas fiscais: {e}")
        return []

def buscar_nota_por_id(id):
    """Busca uma nota fiscal específica pelo ID"""
    query = """
    SELECT n.id, n.numero_nota, n.serie, n.data_emissao, n.data_recebimento,
           n.fornecedor, n.cnpj_fornecedor, n.valor_total, n.arquivo_pdf,
           n.observacoes, n.data_cadastro
    FROM notas_fiscais n
    WHERE n.id = %s AND n.ativo = TRUE
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'numero_nota': r[1],
                'serie': r[2],
                'data_emissao': r[3],
                'data_recebimento': r[4],
                'fornecedor': r[5],
                'cnpj_fornecedor': r[6],
                'valor_total': float(r[7]) if r[7] else None,
                'arquivo_pdf': r[8],
                'observacoes': r[9],
                'data_cadastro': r[10]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar nota fiscal: {e}")
        return None

def inserir_nota_fiscal(dados, arquivo_pdf=None):
    """
    Insere uma nova nota fiscal
    Retorna o ID da nota criada
    """
    query = """
    INSERT INTO notas_fiscais 
        (numero_nota, serie, data_emissao, data_recebimento, fornecedor,
         cnpj_fornecedor, valor_total, arquivo_pdf, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['numero_nota'], dados.get('serie'), dados['data_emissao'],
             dados['data_recebimento'], dados['fornecedor'], dados.get('cnpj_fornecedor'),
             dados.get('valor_total'), arquivo_pdf, dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir nota fiscal: {e}")
        return None

def vincular_movimentacao_nota(movimentacao_id, nota_id):
    """Vincula uma movimentação a uma nota fiscal"""
    try:
        executar_query(
            "UPDATE movimentacoes_estoque SET nota_fiscal_id = %s WHERE id = %s",
            (nota_id, movimentacao_id)
        )
        return True
    except Exception as e:
        print(f"Erro ao vincular movimentação: {e}")
        return False

def listar_movimentacoes_por_nota(nota_id):
    """Lista todas as movimentações (produtos) de uma nota fiscal"""
    query = """
    SELECT m.id, p.nome as produto_nome, m.quantidade, m.unidade,
           m.valor_unitario, m.observacoes
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.nota_fiscal_id = %s AND m.tipo = 'entrada'
    ORDER BY m.id
    """
    try:
        resultado = executar_query(query, (nota_id,), fetch_all=True)
        movs = []
        for r in resultado:
            movs.append({
                'id': r[0],
                'produto_nome': r[1],
                'quantidade': float(r[2]) if r[2] else 0,
                'unidade': r[3],
                'valor_unitario': float(r[4]) if r[4] else None,
                'observacoes': r[5]
            })
        return movs
    except Exception as e:
        print(f"Erro ao listar movimentações da nota: {e}")
        return []

def excluir_nota_fiscal(id):
    """
    Exclui uma nota fiscal e desvincula os produtos
    (mantém as movimentações no estoque, apenas remove o vínculo com a nota)
    """
    try:
        # Primeiro, desvincula os produtos da nota
        executar_query(
            "UPDATE movimentacoes_estoque SET nota_fiscal_id = NULL WHERE nota_fiscal_id = %s",
            (id,)
        )
        
        # Depois, exclui logicamente a nota
        executar_query(
            "UPDATE notas_fiscais SET ativo = FALSE WHERE id = %s",
            (id,)
        )
        
        return True, "Nota fiscal excluída com sucesso. Os produtos foram mantidos no estoque."
    except Exception as e:
        print(f"Erro ao excluir nota fiscal: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def get_resumo_notas():
    """Retorna resumo estatístico das notas fiscais"""
    try:
        # Total de notas
        total = executar_query(
            "SELECT COUNT(*) FROM notas_fiscais WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Total de fornecedores distintos
        fornecedores = executar_query(
            "SELECT COUNT(DISTINCT fornecedor) FROM notas_fiscais WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Valor total em notas
        valor_total = executar_query(
            "SELECT COALESCE(SUM(valor_total), 0) FROM notas_fiscais WHERE ativo = TRUE",
            fetch_one=True
        )[0]
        
        # Notas no mês atual
        notas_mes = executar_query("""
            SELECT COUNT(*) FROM notas_fiscais 
            WHERE ativo = TRUE 
            AND EXTRACT(MONTH FROM data_recebimento) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM data_recebimento) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, fetch_one=True)[0]
        
        return {
            'total_notas': total or 0,
            'total_fornecedores': fornecedores or 0,
            'valor_total': float(valor_total) if valor_total else 0,
            'notas_mes': notas_mes or 0
        }
    except Exception as e:
        print(f"Erro ao obter resumo: {e}")
        return {
            'total_notas': 0,
            'total_fornecedores': 0,
            'valor_total': 0,
            'notas_mes': 0
        }