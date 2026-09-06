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
    """Retorna resumo das notas fiscais."""
    try:
        total_notas = executar_query("SELECT COUNT(*) FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True)
        total_notas = total_notas[0] if total_notas else 0
    except Exception:
        total_notas = 0
    try:
        valor_total = executar_query("SELECT COALESCE(SUM(valor_total), 0) FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True)
        valor_total = float(valor_total[0]) if valor_total and valor_total[0] else 0
    except Exception:
        valor_total = 0
    try:
        notas_mes = executar_query("""
            SELECT COUNT(*) FROM notas_fiscais
            WHERE ativo = TRUE AND EXTRACT(MONTH FROM data_recebimento) = EXTRACT(MONTH FROM CURRENT_DATE)
        """, fetch_one=True)
        notas_mes = notas_mes[0] if notas_mes else 0
    except Exception:
        notas_mes = 0
    try:
        total_itens = executar_query("""
            SELECT COUNT(*) FROM movimentacoes_estoque
            WHERE tipo = 'entrada' AND nota_fiscal_id IS NOT NULL
        """, fetch_one=True)
        total_itens = total_itens[0] if total_itens else 0
    except Exception:
        total_itens = 0
    try:
        total_fornecedores = executar_query("SELECT COUNT(DISTINCT fornecedor) FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True)
        total_fornecedores = total_fornecedores[0] if total_fornecedores else 0
    except Exception:
        total_fornecedores = 0
    return {
        'total_notas': total_notas,
        'valor_total': valor_total,
        'notas_mes': notas_mes,
        'total_itens': total_itens,
        'total_fornecedores': total_fornecedores
    }

def buscar_ou_criar_produto(nome, unidade='L', categoria='Outros'):
    """Busca um produto pelo nome. Se nao existir, cria automaticamente."""
    if not nome or not nome.strip():
        return None
    nome = nome.strip()
    # Buscar produto existente (case insensitive)
    query_busca = "SELECT id FROM produtos_estoque WHERE LOWER(nome) = LOWER(%s) AND ativo = TRUE"
    try:
        resultado = executar_query(query_busca, (nome,), fetch_one=True)
        if resultado:
            return resultado[0]
    except Exception:
        pass
    # Se nao existe, criar
    query_insert = """
    INSERT INTO produtos_estoque (nome, unidade, categoria, estoque_minimo, quantidade_atual, ativo)
    VALUES (%s, %s, %s, 0, 0, TRUE) RETURNING id
    """
    try:
        resultado = executar_query(query_insert, (nome, unidade, categoria), fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao criar produto automatico: {e}")
        return None

def adicionar_item_nota(nota_id, dados):
    """Adiciona um item a uma nota fiscal e registra entrada automatica no estoque."""
    nome_produto = dados.get('nome_produto')
    quantidade = dados.get('quantidade')
    valor_unitario = dados.get('valor_unitario')
    unidade = dados.get('unidade', 'L')
    categoria = dados.get('categoria', 'Outros')

    if not nome_produto or not quantidade:
        return None, "Nome do produto e quantidade sao obrigatorios"

    try:
        quantidade = float(quantidade)
        if valor_unitario:
            valor_unitario = float(valor_unitario)
    except (ValueError, TypeError):
        return None, "Quantidade e valor devem ser numeros validos"

    # 1. Buscar ou criar o produto
    produto_id = buscar_ou_criar_produto(nome_produto, unidade, categoria)
    if not produto_id:
        return None, "Erro ao buscar/criar produto"

    # 2. Registrar movimentacao de entrada vinculada a NF
    query_mov = """
    INSERT INTO movimentacoes_estoque
    (produto_id, tipo, quantidade, unidade, data_movimento, valor_unitario, observacoes, nota_fiscal_id)
    VALUES (%s, 'entrada', %s, %s, CURRENT_DATE, %s, %s, %s)
    RETURNING id
    """
    obs = f"Entrada via NF - {dados.get('observacoes', '')}"
    try:
        mov_result = executar_query(query_mov, (produto_id, quantidade, unidade, valor_unitario, obs, nota_id), fetch_one=True)
        mov_id = mov_result[0] if mov_result else None
    except Exception as e:
        return None, f"Erro ao registrar entrada: {e}"

    # 3. Atualizar saldo do produto
    try:
        executar_query(
            "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
            (quantidade, produto_id)
        )
    except Exception as e:
        print(f"Erro ao atualizar saldo: {e}")

    # 4. Atualizar valor total da NF
    try:
        if valor_unitario:
            executar_query(
                "UPDATE notas_fiscais SET valor_total = COALESCE(valor_total, 0) + (%s * %s) WHERE id = %s",
                (quantidade, valor_unitario, nota_id)
            )
    except Exception:
        pass

    return mov_id, "Item adicionado e entrada registrada no estoque!"

def remover_item_nota(movimentacao_id):
    """Remove um item da nota fiscal e reverte a entrada no estoque."""
    try:
        # Buscar a movimentacao
        query_busca = """
        SELECT m.produto_id, m.quantidade, m.nota_fiscal_id, m.valor_unitario
        FROM movimentacoes_estoque m WHERE m.id = %s AND m.tipo = 'entrada'
        """
        r = executar_query(query_busca, (movimentacao_id,), fetch_one=True)
        if not r:
            return False, "Item nao encontrado"

        produto_id = r[0]
        quantidade = float(r[1]) if r[1] else 0
        nota_id = r[2]
        valor_unit = float(r[3]) if r[3] else 0

        # Reverter o saldo do produto
        executar_query(
            "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual - %s WHERE id = %s",
            (quantidade, produto_id)
        )

        # Reverter valor total da NF
        if valor_unit:
            executar_query(
                "UPDATE notas_fiscais SET valor_total = GREATEST(COALESCE(valor_total, 0) - (%s * %s), 0) WHERE id = %s",
                (quantidade, valor_unit, nota_id)
            )

        # Excluir a movimentacao
        executar_query("DELETE FROM movimentacoes_estoque WHERE id = %s", (movimentacao_id,))

        return True, "Item removido e entrada estornada no estoque!"
    except Exception as e:
        print(f"Erro ao remover item: {e}")
        return False, f"Erro: {e}"