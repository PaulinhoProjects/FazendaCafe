"""
Módulo de Controle de Estoque de Insumos
Versão completa com categorias e relatórios
"""

import sys
import os
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def get_ultimo_valor_produto(produto_id):
    """Retorna o último valor unitário registrado para o produto"""
    query = """
    SELECT valor_unitario FROM movimentacoes_estoque
    WHERE produto_id = %s AND valor_unitario IS NOT NULL
    ORDER BY data_movimento DESC
    LIMIT 1
    """
    try:
        resultado = executar_query(query, (produto_id,), fetch_one=True)
        return float(resultado[0]) if resultado and resultado[0] else None
    except Exception as e:
        print(f"Erro ao buscar último valor: {e}")
        return None

# =====================================================
# FUNÇÕES DE PRODUTOS
# =====================================================

def listar_produtos(ativos=True):
    """Retorna lista de produtos com categoria e último valor"""
    query = """
    SELECT id, nome, unidade, estoque_minimo, quantidade_atual, observacoes, ativo, categoria
    FROM produtos_estoque
    WHERE ativo = %s
    ORDER BY nome
    """
    try:
        resultado = executar_query(query, (ativos,), fetch_all=True)
        produtos = []
        for r in resultado:
            estoque_minimo = r[3] if r[3] is not None else 0
            quantidade_atual = float(r[4]) if r[4] is not None else 0
            ultimo_valor = get_ultimo_valor_produto(r[0])
            
            produtos.append({
                'id': r[0],
                'nome': r[1],
                'unidade': r[2],
                'estoque_minimo': estoque_minimo,
                'quantidade_atual': quantidade_atual,
                'observacoes': r[5],
                'ativo': r[6],
                'categoria': r[7],
                'ultimo_valor': ultimo_valor,
                'valor_total': quantidade_atual * (ultimo_valor or 0),
                'estoque_baixo': quantidade_atual <= estoque_minimo if estoque_minimo > 0 else False
            })
        return produtos
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return []

def buscar_produto_por_id(id):
    """Busca um produto pelo ID"""
    query = """
    SELECT id, nome, unidade, estoque_minimo, quantidade_atual, observacoes, ativo, categoria
    FROM produtos_estoque
    WHERE id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'nome': r[1],
                'unidade': r[2],
                'estoque_minimo': r[3],
                'quantidade_atual': float(r[4]) if r[4] else 0,
                'observacoes': r[5],
                'ativo': r[6],
                'categoria': r[7]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar produto: {e}")
        return None

def inserir_produto(dados):
    """Insere um novo produto"""
    query = """
    INSERT INTO produtos_estoque (nome, unidade, estoque_minimo, quantidade_atual, observacoes, categoria)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['nome'], dados['unidade'], dados.get('estoque_minimo'),
             dados.get('quantidade_atual', 0), dados.get('observacoes'),
             dados.get('categoria')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir produto: {e}")
        return None

def atualizar_produto(id, dados):
    """Atualiza um produto"""
    query = """
    UPDATE produtos_estoque
    SET nome=%s, unidade=%s, estoque_minimo=%s, quantidade_atual=%s, observacoes=%s, categoria=%s
    WHERE id=%s
    """
    try:
        executar_query(query,
            (dados['nome'], dados['unidade'], dados.get('estoque_minimo'),
             dados.get('quantidade_atual', 0), dados.get('observacoes'),
             dados.get('categoria'), id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar produto: {e}")
        return False

def excluir_produto(id):
    """Exclui um produto (verifica se não há movimentações)"""
    try:
        # Verificar se há movimentações vinculadas
        count = executar_query("SELECT COUNT(*) FROM movimentacoes_estoque WHERE produto_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: produto possui {count} movimentação(ões)"
        
        # Exclusão lógica
        executar_query("UPDATE produtos_estoque SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Produto excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir produto: {e}")
        return False, f"Erro ao excluir: {str(e)}"

# =====================================================
# FUNÇÕES DE MOVIMENTAÇÕES
# =====================================================

def registrar_movimentacao(dados):
    """Registra entrada/saída e atualiza o saldo do produto"""
    try:
        # Inserir movimentação
        query_mov = """
        INSERT INTO movimentacoes_estoque 
            (produto_id, tipo, quantidade, unidade, data_movimento, valor_unitario, observacoes)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """
        mov_id = executar_query(query_mov,
            (dados['produto_id'], dados['tipo'], dados['quantidade'],
             dados.get('unidade'), dados['data_movimento'],
             dados.get('valor_unitario'), dados.get('observacoes')),
            fetch_one=True)
        
        if not mov_id:
            return None
        
        # Atualizar quantidade atual do produto
        if dados['tipo'] == 'entrada':
            update_saldo = "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s"
        else:
            update_saldo = "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual - %s WHERE id = %s"
        
        executar_query(update_saldo, (dados['quantidade'], dados['produto_id']))
        
        return mov_id[0]
    except Exception as e:
        print(f"Erro ao registrar movimentação: {e}")
        return None

def listar_movimentacoes(produto_id=None):
    """Lista movimentações, mostrando produtos removidos como 'Produto removido'"""
    if produto_id:
        query = """
        SELECT m.id, 
               COALESCE(p.nome, '🚫 Produto removido') as produto_nome,
               m.tipo, m.quantidade,
               m.unidade, m.data_movimento, m.valor_unitario, m.observacoes,
               p.ativo, m.nota_fiscal_id  -- <-- ADICIONADO
        FROM movimentacoes_estoque m
        LEFT JOIN produtos_estoque p ON p.id = m.produto_id
        WHERE m.produto_id = %s
        ORDER BY m.data_movimento DESC
        """
        params = (produto_id,)
    else:
        query = """
        SELECT m.id, 
               COALESCE(p.nome, '🚫 Produto removido') as produto_nome,
               m.tipo, m.quantidade,
               m.unidade, m.data_movimento, m.valor_unitario, m.observacoes,
               p.ativo, m.nota_fiscal_id  -- <-- ADICIONADO
        FROM movimentacoes_estoque m
        LEFT JOIN produtos_estoque p ON p.id = m.produto_id
        ORDER BY m.data_movimento DESC
        LIMIT 100
        """
        params = None

    try:
        resultado = executar_query(query, params, fetch_all=True)
        movs = []
        for r in resultado:
            movs.append({
                'id': r[0],
                'produto_nome': r[1],
                'tipo': r[2],
                'quantidade': float(r[3]) if r[3] else 0,
                'unidade': r[4],
                'data_movimento': r[5],
                'valor_unitario': float(r[6]) if r[6] else None,
                'observacoes': r[7],
                'produto_ativo': r[8],
                'nota_fiscal_id': r[9] 
            })
        return movs
    except Exception as e:
        print(f"Erro ao listar movimentações: {e}")
        return []

def buscar_movimentacao_por_id(id):
    """Busca uma movimentação pelo ID, incluindo dados do produto (mesmo excluído)"""
    query = """
    SELECT m.id, m.produto_id, 
           COALESCE(p.nome, '🚫 Produto removido') as produto_nome,
           m.tipo, m.quantidade,
           m.unidade, m.data_movimento, m.valor_unitario, m.observacoes,
           p.ativo, m.nota_fiscal_id
    FROM movimentacoes_estoque m
    LEFT JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'produto_id': r[1],
                'produto_nome': r[2],
                'tipo': r[3],
                'quantidade': float(r[4]) if r[4] else 0,
                'unidade': r[5],
                'data_movimento': r[6],
                'valor_unitario': float(r[7]) if r[7] else None,
                'observacoes': r[8],
                'produto_ativo': r[9],
                'nota_fiscal_id': r[10]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar movimentação: {e}")
        return None

def atualizar_movimentacao(id, dados_novos):
    """Atualiza uma movimentação e ajusta o saldo do produto"""
    try:
        # Buscar movimentação antiga
        mov_antiga = buscar_movimentacao_por_id(id)
        if not mov_antiga:
            return False
        
        # Reverter o efeito da movimentação antiga
        if mov_antiga['tipo'] == 'entrada':
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual - %s WHERE id = %s",
                (mov_antiga['quantidade'], mov_antiga['produto_id'])
            )
        else:
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
                (mov_antiga['quantidade'], mov_antiga['produto_id'])
            )
        
        # Aplicar o efeito da nova movimentação
        if dados_novos['tipo'] == 'entrada':
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
                (dados_novos['quantidade'], dados_novos['produto_id'])
            )
        else:
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual - %s WHERE id = %s",
                (dados_novos['quantidade'], dados_novos['produto_id'])
            )
        
        # Atualizar a movimentação
        query = """
        UPDATE movimentacoes_estoque
        SET produto_id=%s, tipo=%s, quantidade=%s, unidade=%s,
            data_movimento=%s, valor_unitario=%s, observacoes=%s
        WHERE id=%s
        """
        executar_query(query,
            (dados_novos['produto_id'], dados_novos['tipo'], dados_novos['quantidade'],
             dados_novos.get('unidade'), dados_novos['data_movimento'],
             dados_novos.get('valor_unitario'), dados_novos.get('observacoes'), id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar movimentação: {e}")
        return False

def excluir_movimentacao(id):
    """Exclui uma movimentação e ajusta o saldo do produto"""
    try:
        # Buscar a movimentação para saber o produto e a quantidade
        mov = executar_query(
            "SELECT produto_id, tipo, quantidade FROM movimentacoes_estoque WHERE id = %s", 
            (id,), 
            fetch_one=True
        )
        if not mov:
            return False, "Movimentação não encontrada"
        
        produto_id, tipo, quantidade = mov
        
        # Reverter o efeito no saldo
        if tipo == 'entrada':
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual - %s WHERE id = %s",
                (quantidade, produto_id)
            )
        else:
            executar_query(
                "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
                (quantidade, produto_id)
            )
        
        # Excluir a movimentação
        executar_query("DELETE FROM movimentacoes_estoque WHERE id = %s", (id,))
        return True, "Movimentação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir movimentação: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def listar_movimentacoes_por_periodo(data_inicio, data_fim):
    """Lista movimentações em um período específico"""
    query = """
    SELECT m.id, p.nome as produto_nome, m.tipo, m.quantidade,
           m.unidade, m.data_movimento, m.valor_unitario, m.observacoes
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.data_movimento BETWEEN %s AND %s
    ORDER BY m.data_movimento DESC
    """
    try:
        resultado = executar_query(query, (data_inicio, data_fim), fetch_all=True)
        movs = []
        for r in resultado:
            movs.append({
                'id': r[0],
                'produto_nome': r[1],
                'tipo': r[2],
                'quantidade': float(r[3]) if r[3] else 0,
                'unidade': r[4],
                'data_movimento': r[5],
                'valor_unitario': float(r[6]) if r[6] else None,
                'observacoes': r[7]
            })
        return movs
    except Exception as e:
        print(f"Erro ao listar movimentações por período: {e}")
        return []

# =====================================================
# FUNÇÕES DE RESUMO
# =====================================================

def get_resumo_estoque():
    """Retorna resumo estatístico do estoque"""
    try:
        # Total de produtos
        total_produtos = executar_query("SELECT COUNT(*) FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True)[0]
        
        # Valor total em estoque
        query_valor = """
        SELECT COALESCE(SUM(p.quantidade_atual * COALESCE((
            SELECT valor_unitario FROM movimentacoes_estoque 
            WHERE produto_id = p.id AND valor_unitario IS NOT NULL 
            ORDER BY data_movimento DESC LIMIT 1
        ), 0)), 0)
        FROM produtos_estoque p
        WHERE p.ativo = TRUE
        """
        valor_total = executar_query(query_valor, fetch_one=True)[0]
        
        # Produtos com estoque baixo
        estoque_baixo = executar_query("""
            SELECT COUNT(*) FROM produtos_estoque 
            WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)
        """, fetch_one=True)[0]
        
        # Movimentações no mês
        mov_mes = executar_query("""
            SELECT COUNT(*) FROM movimentacoes_estoque 
            WHERE EXTRACT(MONTH FROM data_movimento) = EXTRACT(MONTH FROM CURRENT_DATE)
        """, fetch_one=True)[0]
        
        return {
            'total_produtos': total_produtos or 0,
            'valor_total': float(valor_total) if valor_total else 0,
            'estoque_baixo': estoque_baixo or 0,
            'movimentacoes_mes': mov_mes or 0
        }
    except Exception as e:
        print(f"Erro ao obter resumo: {e}")
        return {
            'total_produtos': 0,
            'valor_total': 0,
            'estoque_baixo': 0,
            'movimentacoes_mes': 0
        }

# =====================================================
# FUNÇÕES DE RELATÓRIOS (PDF/EXCEL)
# =====================================================

def gerar_excel_produtos(produtos):
    """Gera arquivo Excel com a lista de produtos"""
    data = []
    for p in produtos:
        data.append({
            'ID': p['id'],
            'Produto': p['nome'],
            'Categoria': p.get('categoria', ''),
            'Unidade': p['unidade'],
            'Quantidade': p['quantidade_atual'],
            'Estoque Mínimo': p['estoque_minimo'] if p['estoque_minimo'] else 0,
            'Status': 'Baixo' if p.get('estoque_baixo') else 'Normal',
            'Observações': p['observacoes'] or ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Produtos', index=False)
        worksheet = writer.sheets['Produtos']
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            col_idx = df.columns.get_loc(column)
            worksheet.column_dimensions[chr(65 + col_idx)].width = min(column_width, 30)
    
    output.seek(0)
    return output

def gerar_pdf_produtos(produtos):
    """Gera arquivo PDF com a lista de produtos"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    titulo = Paragraph(f"Relatório de Produtos - {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 0.5*cm))
    
    data = [['ID', 'Produto', 'Categoria', 'Unidade', 'Quantidade', 'Estoque Mínimo', 'Status']]
    
    for p in produtos:
        status = 'Baixo' if p.get('estoque_baixo') else 'Normal'
        data.append([
            str(p['id']),
            p['nome'],
            p.get('categoria', ''),
            p['unidade'],
            f"{p['quantidade_atual']:.2f}",
            f"{p['estoque_minimo']:.2f}" if p['estoque_minimo'] else '-',
            status
        ])
    
    table = Table(data, colWidths=[2*cm, 5*cm, 3*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    
    for i, p in enumerate(produtos, start=1):
        if p.get('estoque_baixo'):
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightcoral)
    
    table.setStyle(style)
    elements.append(table)
    
    elements.append(Spacer(1, 1*cm))
    total_produtos = len(produtos)
    total_baixo = sum(1 for p in produtos if p.get('estoque_baixo'))
    rodape = Paragraph(f"Total de produtos: {total_produtos} | Produtos com estoque baixo: {total_baixo}", styles['Normal'])
    elements.append(rodape)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def gerar_excel_movimentacoes(movimentacoes, data_inicio, data_fim):
    """Gera Excel com movimentações em um período"""
    data = []
    for m in movimentacoes:
        data.append({
            'Data': m['data_movimento'],
            'Produto': m['produto_nome'],
            'Tipo': 'Entrada' if m['tipo'] == 'entrada' else 'Saída',
            'Quantidade': m['quantidade'],
            'Unidade': m['unidade'] or '',
            'Valor Unitário': m['valor_unitario'] if m['valor_unitario'] else 0,
            'Valor Total': (m['quantidade'] * m['valor_unitario']) if m['valor_unitario'] else 0,
            'Observações': m['observacoes'] or ''
        })
    
    df = pd.DataFrame(data)
    total_entradas = df[df['Tipo'] == 'Entrada']['Valor Total'].sum()
    total_saidas = df[df['Tipo'] == 'Saída']['Valor Total'].sum()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Movimentações', index=False)
        
        resumo = pd.DataFrame({
            'Período': [f"{data_inicio} a {data_fim}"],
            'Total Entradas (R$)': [f"{total_entradas:.2f}"],
            'Total Saídas (R$)': [f"{total_saidas:.2f}"],
            'Saldo (R$)': [f"{total_entradas - total_saidas:.2f}"]
        })
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
    
    output.seek(0)
    return output

def gerar_pdf_movimentacoes(movimentacoes, data_inicio, data_fim):
    """Gera PDF com movimentações em um período"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.5*cm, leftMargin=1.5*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    titulo = Paragraph(f"Relatório de Movimentações - {data_inicio} a {data_fim}", styles['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 0.5*cm))
    
    data = [['Data', 'Produto', 'Tipo', 'Quantidade', 'Unidade', 'Valor Unit.', 'Valor Total']]
    
    total_entradas = 0
    total_saidas = 0
    
    for m in movimentacoes:
        tipo = 'Entrada' if m['tipo'] == 'entrada' else 'Saída'
        valor_unit = m['valor_unitario'] or 0
        valor_total = m['quantidade'] * valor_unit
        
        if m['tipo'] == 'entrada':
            total_entradas += valor_total
        else:
            total_saidas += valor_total
        
        data.append([
            m['data_movimento'],
            m['produto_nome'],
            tipo,
            f"{m['quantidade']:.2f}",
            m['unidade'] or '-',
            f"{valor_unit:.2f}" if valor_unit else '-',
            f"{valor_total:.2f}"
        ])
    
    data.append(['', '', '', '', '', 'TOTAL:', f"{total_entradas - total_saidas:.2f}"])
    
    table = Table(data, colWidths=[2.5*cm, 5*cm, 2.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2.5*cm])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ])
    
    for i, m in enumerate(movimentacoes, start=1):
        if m['tipo'] == 'entrada':
            style.add('BACKGROUND', (2, i), (2, i), colors.lightgreen)
        else:
            style.add('BACKGROUND', (2, i), (2, i), colors.lightcoral)
    
    table.setStyle(style)
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def listar_categorias():
    """Lista categorias ativas."""
    query = "SELECT id, nome, descricao, cor FROM categorias_estoque WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True)
        return [{'id': r[0], 'nome': r[1], 'descricao': r[2], 'cor': r[3]} for r in resultado] if resultado else []
    except Exception:
        return []

def get_valor_por_categoria():
    """Retorna valor total por categoria para grafico."""
    query = """
    SELECT 
        COALESCE(p.categoria, 'Sem categoria') as categoria,
        COUNT(*) as produtos,
        COALESCE(SUM(p.quantidade_atual * COALESCE((
            SELECT valor_unitario FROM movimentacoes_estoque 
            WHERE produto_id = p.id AND valor_unitario IS NOT NULL 
            ORDER BY data_movimento DESC LIMIT 1
        ), 0)), 0) as valor
    FROM produtos_estoque p
    WHERE p.ativo = TRUE
    GROUP BY p.categoria
    ORDER BY valor DESC
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        labels = []
        dados = []
        for r in resultado:
            labels.append(r[0])
            dados.append(float(r[2]) if r[2] else 0)
        return {'labels': labels, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}

def get_consumo_ultimos_6_meses():
    """Retorna consumo (saidas) dos ultimos 6 meses."""
    query = """
    SELECT TO_CHAR(data_movimento, 'YYYY-MM') as mes, SUM(quantidade) as total
    FROM movimentacoes_estoque
    WHERE tipo = 'saida' AND data_movimento >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY TO_CHAR(data_movimento, 'YYYY-MM')
    ORDER BY mes ASC
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        meses = []
        dados = []
        for r in resultado:
            ano, mes = r[0].split('-')
            meses.append(f"{mes}/{ano}")
            dados.append(float(r[1]) if r[1] else 0)
        return {'labels': meses, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}

def get_top_produtos_consumo(limite=10):
    """Retorna produtos mais consumidos (saida)."""
    query = """
    SELECT p.nome, SUM(m.quantidade) as total
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.tipo = 'saida'
    GROUP BY p.id, p.nome
    ORDER BY total DESC
    LIMIT %s
    """
    try:
        resultado = executar_query(query, (limite,), fetch_all=True)
        labels = [r[0] for r in resultado]
        dados = [float(r[1]) if r[1] else 0 for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}