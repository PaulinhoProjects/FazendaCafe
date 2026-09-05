"""
Módulo de Adubação baseado em Análises de Solo
Gerencia recomendações e aplicações de adubos
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime

# =====================================================
# FUNÇÕES PARA TIPOS DE ADUBAÇÃO
# =====================================================

def listar_tipos_adubacao():
    query = "SELECT id, nome, descricao FROM tipos_adubacao WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True)
        return [{'id': r[0], 'nome': r[1], 'descricao': r[2]} for r in resultado] if resultado else []
    except Exception as e:
        print(f"Erro ao listar tipos: {e}")
        return []

# =====================================================
# FUNÇÕES PARA RECOMENDAÇÕES
# =====================================================

def gerar_recomendacao_automatica(analise_id):
    """
    Gera recomendação automática baseada nos resultados da análise de solo
    Retorna dicionário com recomendações de nutrientes
    """
    try:
        # Buscar resultados da análise
        query_resultados = """
        SELECT p.nome, r.valor
        FROM resultados_analise r
        JOIN parametros_analise p ON p.id = r.parametro_id
        WHERE r.analise_id = %s
        """
        resultados = executar_query(query_resultados, (analise_id,), fetch_all=True)
        
        if not resultados:
            return None, "Análise sem resultados"
        
        # Converter para dicionário
        valores = {}
        for r in resultados:
            valores[r[0]] = float(r[1]) if r[1] else 0
        
        # Regras básicas de recomendação (exemplo simplificado)
        recomendacoes = []
        
        # Fósforo (P)
        p_valor = valores.get('Fósforo (P)', 0)
        if p_valor < 10:
            recomendacoes.append({
                'nutriente': 'P2O5',
                'quantidade': 120,
                'unidade': 'kg/ha',
                'fonte': 'Superfosfato Simples',
                'observacoes': 'Teor baixo de fósforo'
            })
        elif p_valor < 20:
            recomendacoes.append({
                'nutriente': 'P2O5',
                'quantidade': 80,
                'unidade': 'kg/ha',
                'fonte': 'Superfosfato Simples',
                'observacoes': 'Teor médio de fósforo'
            })
        
        # Potássio (K)
        k_valor = valores.get('Potássio (K)', 0)
        if k_valor < 0.15:
            recomendacoes.append({
                'nutriente': 'K2O',
                'quantidade': 100,
                'unidade': 'kg/ha',
                'fonte': 'Cloreto de Potássio',
                'observacoes': 'Teor baixo de potássio'
            })
        elif k_valor < 0.3:
            recomendacoes.append({
                'nutriente': 'K2O',
                'quantidade': 60,
                'unidade': 'kg/ha',
                'fonte': 'Cloreto de Potássio',
                'observacoes': 'Teor médio de potássio'
            })
        
        # pH e necessidade de calcário
        ph_valor = valores.get('pH (CaCl2)', 0) or valores.get('pH (H2O)', 0)
        if ph_valor < 5.5:
            recomendacoes.append({
                'nutriente': 'Calcário',
                'quantidade': 2,
                'unidade': 't/ha',
                'fonte': 'Calcário Dolomítico',
                'observacoes': 'Acidez alta - necessidade de calagem'
            })
        elif ph_valor < 6.0:
            recomendacoes.append({
                'nutriente': 'Calcário',
                'quantidade': 1,
                'unidade': 't/ha',
                'fonte': 'Calcário Dolomítico',
                'observacoes': 'Acidez média - calagem de manutenção'
            })
        
        return recomendacoes, None
        
    except Exception as e:
        print(f"Erro ao gerar recomendação: {e}")
        return None, str(e)

def inserir_recomendacao(dados):
    """Insere uma nova recomendação de adubação"""
    query = """
    INSERT INTO recomendacoes_adubacao 
        (talhao_id, analise_id, data_recomendacao, data_validade, responsavel, observacoes, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados.get('analise_id'), dados['data_recomendacao'],
             dados.get('data_validade'), dados.get('responsavel'), dados.get('observacoes'),
             dados.get('status', 'Pendente')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir recomendação: {e}")
        return None

def inserir_item_recomendacao(dados):
    """Insere um item na recomendação"""
    query = """
    INSERT INTO itens_recomendacao 
        (recomendacao_id, nutriente, quantidade_recomendada, unidade, fonte_recomendada, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['recomendacao_id'], dados['nutriente'], dados['quantidade'],
             dados['unidade'], dados.get('fonte'), dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir item: {e}")
        return None

def listar_recomendacoes(talhao_id=None):
    """Lista recomendações de adubação"""
    if talhao_id:
        query = """
        SELECT r.id, r.talhao_id, t.nome as talhao_nome,
               r.analise_id, a.data_coleta as analise_data,
               r.data_recomendacao, r.data_validade, r.responsavel,
               r.observacoes, r.status
        FROM recomendacoes_adubacao r
        JOIN talhoes t ON t.id = r.talhao_id
        LEFT JOIN analises a ON a.id = r.analise_id
        WHERE r.talhao_id = %s
        ORDER BY r.data_recomendacao DESC
        """
        params = (talhao_id,)
    else:
        query = """
        SELECT r.id, r.talhao_id, t.nome as talhao_nome,
               r.analise_id, a.data_coleta as analise_data,
               r.data_recomendacao, r.data_validade, r.responsavel,
               r.observacoes, r.status
        FROM recomendacoes_adubacao r
        JOIN talhoes t ON t.id = r.talhao_id
        LEFT JOIN analises a ON a.id = r.analise_id
        ORDER BY r.data_recomendacao DESC
        LIMIT 100
        """
        params = None
    
    try:
        resultado = executar_query(query, params, fetch_all=True)
        recomendacoes = []
        for r in resultado:
            recomendacoes.append({
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'analise_id': r[3],
                'analise_data': r[4],
                'data_recomendacao': r[5],
                'data_validade': r[6],
                'responsavel': r[7],
                'observacoes': r[8],
                'status': r[9]
            })
        return recomendacoes
    except Exception as e:
        print(f"Erro ao listar recomendações: {e}")
        return []

def buscar_recomendacao_por_id(id):
    """Busca uma recomendação específica"""
    query = """
    SELECT r.id, r.talhao_id, t.nome as talhao_nome,
           r.analise_id, a.data_coleta as analise_data,
           r.data_recomendacao, r.data_validade, r.responsavel,
           r.observacoes, r.status
    FROM recomendacoes_adubacao r
    JOIN talhoes t ON t.id = r.talhao_id
    LEFT JOIN analises a ON a.id = r.analise_id
    WHERE r.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'analise_id': r[3],
                'analise_data': r[4],
                'data_recomendacao': r[5],
                'data_validade': r[6],
                'responsavel': r[7],
                'observacoes': r[8],
                'status': r[9]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar recomendação: {e}")
        return None

def listar_itens_recomendacao(recomendacao_id):
    """Lista os itens de uma recomendação"""
    query = """
    SELECT id, nutriente, quantidade_recomendada, unidade, fonte_recomendada, observacoes
    FROM itens_recomendacao
    WHERE recomendacao_id = %s
    ORDER BY nutriente
    """
    try:
        resultado = executar_query(query, (recomendacao_id,), fetch_all=True)
        itens = []
        for r in resultado:
            itens.append({
                'id': r[0],
                'nutriente': r[1],
                'quantidade': float(r[2]) if r[2] else 0,
                'unidade': r[3],
                'fonte': r[4],
                'observacoes': r[5]
            })
        return itens
    except Exception as e:
        print(f"Erro ao listar itens: {e}")
        return []

def atualizar_status_recomendacao(id, novo_status):
    """Atualiza o status de uma recomendação"""
    query = "UPDATE recomendacoes_adubacao SET status = %s WHERE id = %s"
    try:
        executar_query(query, (novo_status, id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar status: {e}")
        return False
    
def inserir_adubacao(dados):
    """Registra uma adubação realizada"""
    query = """
    INSERT INTO adubacoes 
        (talhao_id, recomendacao_id, tipo_adubacao_id, data_aplicacao, responsavel, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['recomendacao_id'], dados['tipo_adubacao_id'],
             dados['data_aplicacao'], dados.get('responsavel'), dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir adubação: {e}")
        return None

def inserir_produto_adubacao(dados):
    """Registra produto usado na adubação"""
    query = """
    INSERT INTO produtos_adubacao 
        (adubacao_id, produto_nome, quantidade, unidade, custo_unitario, fornecedor, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['adubacao_id'], dados['produto_nome'], dados['quantidade'],
             dados['unidade'], dados.get('custo_unitario'), dados.get('fornecedor'),
             dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir produto: {e}")
        return None

def inserir_nutriente_aplicado(dados):
    """Registra nutriente aplicado"""
    query = """
    INSERT INTO nutrientes_aplicados (adubacao_id, nutriente, quantidade_aplicada, unidade)
    VALUES (%s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['adubacao_id'], dados['nutriente'], dados['quantidade_aplicada'], dados['unidade']),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir nutriente: {e}")
        return None

def buscar_adubacao_por_id(id):
    """Busca uma adubação específica"""
    query = """
    SELECT a.id, a.talhao_id, t.nome as talhao_nome,
           a.recomendacao_id, r.data_recomendacao,
           a.tipo_adubacao_id, ta.nome as tipo_nome,
           a.data_aplicacao, a.responsavel, a.observacoes
    FROM adubacoes a
    JOIN talhoes t ON t.id = a.talhao_id
    LEFT JOIN recomendacoes_adubacao r ON r.id = a.recomendacao_id
    LEFT JOIN tipos_adubacao ta ON ta.id = a.tipo_adubacao_id
    WHERE a.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'recomendacao_id': r[3],
                'recomendacao_data': r[4],
                'tipo_id': r[5],
                'tipo_nome': r[6],
                'data_aplicacao': r[7],
                'responsavel': r[8],
                'observacoes': r[9]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar adubação: {e}")
        return None

def listar_produtos_adubacao(adubacao_id):
    """Lista produtos usados em uma adubação"""
    query = """
    SELECT id, produto_nome, quantidade, unidade, custo_unitario, fornecedor, observacoes
    FROM produtos_adubacao
    WHERE adubacao_id = %s
    """
    try:
        resultado = executar_query(query, (adubacao_id,), fetch_all=True)
        produtos = []
        for r in resultado:
            produtos.append({
                'id': r[0],
                'nome': r[1],
                'quantidade': float(r[2]) if r[2] else 0,
                'unidade': r[3],
                'custo': float(r[4]) if r[4] else None,
                'fornecedor': r[5],
                'observacoes': r[6]
            })
        return produtos
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return []

def listar_nutrientes_aplicados(adubacao_id):
    """Lista nutrientes aplicados"""
    query = """
    SELECT id, nutriente, quantidade_aplicada, unidade
    FROM nutrientes_aplicados
    WHERE adubacao_id = %s
    """
    try:
        resultado = executar_query(query, (adubacao_id,), fetch_all=True)
        nutrientes = []
        for r in resultado:
            nutrientes.append({
                'id': r[0],
                'nutriente': r[1],
                'quantidade': float(r[2]) if r[2] else 0,
                'unidade': r[3]
            })
        return nutrientes
    except Exception as e:
        print(f"Erro ao listar nutrientes: {e}")
        return []
    
def listar_adubacoes(limite=100):
    """Lista todas as adubações realizadas"""
    query = """
    SELECT a.id, a.talhao_id, t.nome as talhao_nome,
           a.recomendacao_id, r.data_recomendacao,
           a.tipo_adubacao_id, ta.nome as tipo_nome,
           a.data_aplicacao, a.responsavel
    FROM adubacoes a
    JOIN talhoes t ON t.id = a.talhao_id
    LEFT JOIN recomendacoes_adubacao r ON r.id = a.recomendacao_id
    LEFT JOIN tipos_adubacao ta ON ta.id = a.tipo_adubacao_id
    ORDER BY a.data_aplicacao DESC
    LIMIT %s
    """
    try:
        resultado = executar_query(query, (limite,), fetch_all=True)
        adubacoes = []
        for r in resultado:
            adubacoes.append({
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'recomendacao_id': r[3],
                'recomendacao_data': r[4],
                'tipo_id': r[5],
                'tipo_nome': r[6],
                'data_aplicacao': r[7],
                'responsavel': r[8]
            })
        return adubacoes
    except Exception as e:
        print(f"Erro ao listar adubações: {e}")
        return []

def excluir_recomendacao(id):
    """Exclui uma recomendação (itens serão excluídos automaticamente por CASCADE)"""
    try:
        # Verificar se há adubações vinculadas
        count = executar_query("SELECT COUNT(*) FROM adubacoes WHERE recomendacao_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            print(f"Recomendação {id} já foi aplicada em {count} adubação(ões)")
            return False, "Esta recomendação já foi aplicada e não pode ser excluída"
        
        # Excluir a recomendação (CASCADE cuida dos itens)
        executar_query("DELETE FROM recomendacoes_adubacao WHERE id = %s", (id,))
        return True, "Recomendação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir recomendação: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_adubacao(id):
    """Exclui uma adubação (produtos e nutrientes serão excluídos por CASCADE)"""
    try:
        # CASCADE cuida dos filhos
        executar_query("DELETE FROM adubacoes WHERE id = %s", (id,))
        return True, "Adubação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir adubação: {e}")
        return False, f"Erro ao excluir: {str(e)}"