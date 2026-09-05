"""
Módulo de Controle de Pulverizações Foliares
Gerencia aplicações de produtos, receitas e ocorrências de pragas/doenças
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime

# =====================================================
# FUNÇÕES PARA PERÍODOS DA LAVOURA
# =====================================================

def listar_periodos():
    query = "SELECT id, nome, descricao FROM periodos_lavoura WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True)
        if not resultado:
            return []
        return [{'id': r[0], 'nome': r[1], 'descricao': r[2]} for r in resultado]
    except Exception as e:
        print(f"Erro ao listar períodos: {e}")
        return []
# =====================================================
# FUNÇÕES PARA RECEITAS
# =====================================================

def listar_receitas(periodo_id=None):
    """Lista receitas de pulverização"""
    if periodo_id:
        query = "SELECT id, nome, periodo_id, descricao, formula_completa FROM receitas WHERE ativo = TRUE AND periodo_id = %s ORDER BY nome"
        params = (periodo_id,)
    else:
        query = "SELECT id, nome, periodo_id, descricao, formula_completa FROM receitas WHERE ativo = TRUE ORDER BY nome"
        params = None
    
    try:
        resultado = executar_query(query, params, fetch_all=True)
        if not resultado:
            return []
        return [{'id': r[0], 'nome': r[1], 'periodo_id': r[2], 'descricao': r[3], 'formula': r[4]} for r in resultado]
    except Exception as e:
        print(f"Erro ao listar receitas: {e}")
        return []

def inserir_receita(dados):
    """Insere uma nova receita"""
    query = """
    INSERT INTO receitas (nome, periodo_id, descricao, formula_completa, produtos, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query, 
            (dados['nome'], dados['periodo_id'], dados['descricao'], 
             dados['formula'], dados['produtos'], dados['observacoes']),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir receita: {e}")
        return None

def buscar_receita_por_id(id):
    """Busca uma receita específica"""
    query = "SELECT id, nome, periodo_id, descricao, formula_completa, produtos, observacoes FROM receitas WHERE id = %s"
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'nome': r[1],
                'periodo_id': r[2],
                'descricao': r[3],
                'formula': r[4],
                'produtos': r[5],
                'observacoes': r[6]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar receita: {e}")
        return None

# =====================================================
# FUNÇÕES PARA APLICAÇÕES (Pulverizações)
# =====================================================

def listar_aplicacoes(talhao_id=None):
    if talhao_id:
        query = """
        SELECT ap.id, ap.talhao_id, t.nome as talhao_nome, 
               ap.periodo_id, p.nome as periodo_nome,
               ap.receita_id, r.nome as receita_nome,
               ap.data_aplicacao, ap.data_prevista_retorno,
               ap.responsavel, ap.condicoes_climaticas, ap.observacoes,
               ap.tipo_aplicacao,
               ap.status_retorno, ap.observacoes_retorno, ap.data_retorno_realizado
        FROM aplicacoes_pulverizacao ap
        JOIN talhoes t ON t.id = ap.talhao_id
        JOIN periodos_lavoura p ON p.id = ap.periodo_id
        LEFT JOIN receitas r ON r.id = ap.receita_id
        WHERE ap.talhao_id = %s
        ORDER BY ap.data_aplicacao DESC
        """
        params = (talhao_id,)
    else:
        query = """
        SELECT ap.id, ap.talhao_id, t.nome as talhao_nome, 
               ap.periodo_id, p.nome as periodo_nome,
               ap.receita_id, r.nome as receita_nome,
               ap.data_aplicacao, ap.data_prevista_retorno,
               ap.responsavel, ap.condicoes_climaticas, ap.observacoes,
               ap.tipo_aplicacao,
               ap.status_retorno, ap.observacoes_retorno, ap.data_retorno_realizado
        FROM aplicacoes_pulverizacao ap
        JOIN talhoes t ON t.id = ap.talhao_id
        JOIN periodos_lavoura p ON p.id = ap.periodo_id
        LEFT JOIN receitas r ON r.id = ap.receita_id
        ORDER BY ap.data_aplicacao DESC
        LIMIT 100
        """
        params = None
    
    try:
        resultado = executar_query(query, params, fetch_all=True)
        aplicacoes = []
        for r in resultado:
            aplicacoes.append({
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'periodo_id': r[3],
                'periodo_nome': r[4],
                'receita_id': r[5],
                'receita_nome': r[6] if r[6] else 'Receita não informada',
                'data_aplicacao': r[7],
                'data_prevista_retorno': r[8],  # ← NOME CORRETO
                'responsavel': r[9],
                'condicoes': r[10],
                'observacoes': r[11],
                'tipo_aplicacao': r[12],
                'status_retorno': r[13],        # ← NOVO
                'observacoes_retorno': r[14],    # ← NOVO
                'data_retorno_realizado': r[15]  # ← NOVO
            })
        return aplicacoes
    except Exception as e:
        print(f"Erro ao listar aplicações: {e}")
        return []

def inserir_aplicacao(dados):
    query = """
    INSERT INTO aplicacoes_pulverizacao 
        (talhao_id, periodo_id, receita_id, data_aplicacao, 
         data_prevista_retorno, responsavel, condicoes_climaticas, observacoes,
         tipo_aplicacao)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['periodo_id'], dados.get('receita_id'),
             dados['data_aplicacao'], dados.get('data_retorno'), dados['responsavel'],
             dados['condicoes'], dados['observacoes'],
             dados.get('tipo_aplicacao', 'Foliar')),  # <-- novo campo
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir aplicação: {e}")
        return None
    
def buscar_aplicacao_por_id(id):
    query = """
    SELECT ap.id, ap.talhao_id, t.nome as talhao_nome,
           ap.periodo_id, p.nome as periodo_nome,
           ap.receita_id, r.nome as receita_nome, r.formula_completa,
           ap.data_aplicacao, ap.data_prevista_retorno,
           ap.responsavel, ap.condicoes_climaticas, ap.observacoes,
           ap.tipo_aplicacao,
           ap.status_retorno, ap.observacoes_retorno, ap.data_retorno_realizado
    FROM aplicacoes_pulverizacao ap
    JOIN talhoes t ON t.id = ap.talhao_id
    JOIN periodos_lavoura p ON p.id = ap.periodo_id
    LEFT JOIN receitas r ON r.id = ap.receita_id
    WHERE ap.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'periodo_id': r[3],
                'periodo_nome': r[4],
                'receita_id': r[5],
                'receita_nome': r[6],
                'receita_formula': r[7],
                'data_aplicacao': r[8],
                'data_prevista_retorno': r[9],  # ← NOME CORRETO
                'responsavel': r[10],
                'condicoes': r[11],
                'observacoes': r[12],
                'tipo_aplicacao': r[13],
                'status_retorno': r[14],        # ← NOVO
                'observacoes_retorno': r[15],    # ← NOVO
                'data_retorno_realizado': r[16]  # ← NOVO
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar aplicação: {e}")
        return None
# =====================================================
# FUNÇÕES PARA PRAGAS E DOENÇAS
# =====================================================

def listar_pragas_doencas(tipo=None):
    """Lista pragas/doenças cadastradas"""
    if tipo:
        query = "SELECT id, nome, tipo, nome_cientifico, sintomas FROM pragas_doencas WHERE ativo = TRUE AND tipo = %s ORDER BY nome"
        params = (tipo,)
    else:
        query = "SELECT id, nome, tipo, nome_cientifico, sintomas FROM pragas_doencas WHERE ativo = TRUE ORDER BY nome"
        params = None
    
    try:
        resultado = executar_query(query, params, fetch_all=True)
        if not resultado:
            return []
        
        pragas = []
        for r in resultado:
            pragas.append({
                'id': r[0],
                'nome': r[1],
                'tipo': r[2],
                'cientifico': r[3],
                'sintomas': r[4]
            })
        return pragas
    except Exception as e:
        print(f"Erro ao listar pragas/doenças: {e}")
        return []

def registrar_ocorrencia(dados):
    """Registra uma ocorrência de praga/doença"""
    query = """
    INSERT INTO ocorrencias_pragas 
        (talhao_id, praga_doenca_id, aplicacao_id, data_deteccao, 
         nivel_infestacao, tratado_na_aplicacao, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['praga_id'], dados.get('aplicacao_id'),
             dados['data_deteccao'], dados['nivel'], 
             dados.get('tratado', False), dados['observacoes']),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao registrar ocorrência: {e}")
        return None

def listar_ocorrencias_por_talhao(talhao_id):
    """Lista ocorrências de um talhão"""
    query = """
    SELECT op.id, pd.nome as praga_nome, pd.tipo,
           op.data_deteccao, op.nivel_infestacao,
           op.tratado_na_aplicacao, ap.data_aplicacao as data_tratamento,
           op.observacoes
    FROM ocorrencias_pragas op
    JOIN pragas_doencas pd ON pd.id = op.praga_doenca_id
    LEFT JOIN aplicacoes_pulverizacao ap ON ap.id = op.aplicacao_id
    WHERE op.talhao_id = %s
    ORDER BY op.data_deteccao DESC
    """
    try:
        resultado = executar_query(query, (talhao_id,), fetch_all=True)
        if not resultado:
            return []
        
        ocorrencias = []
        for r in resultado:
            ocorrencias.append({
                'id': r[0],
                'praga': r[1],
                'tipo': r[2],
                'data_deteccao': r[3],
                'nivel': r[4],
                'tratado': r[5],
                'data_tratamento': r[6],
                'observacoes': r[7]
            })
        return ocorrencias
    except Exception as e:
        print(f"Erro ao listar ocorrências: {e}")
        return []

def listar_ocorrencias_por_aplicacao(aplicacao_id):
    """Lista pragas detectadas em uma aplicação"""
    query = """
    SELECT op.id, pd.nome, pd.tipo, op.nivel_infestacao, op.observacoes
    FROM ocorrencias_pragas op
    JOIN pragas_doencas pd ON pd.id = op.praga_doenca_id
    WHERE op.aplicacao_id = %s
    """
    try:
        resultado = executar_query(query, (aplicacao_id,), fetch_all=True)
        if not resultado:
            return []
        
        ocorrencias = []
        for r in resultado:
            ocorrencias.append({
                'id': r[0],
                'nome': r[1],
                'tipo': r[2],
                'nivel': r[3],
                'observacoes': r[4]
            })
        return ocorrencias
    except Exception as e:
        print(f"Erro ao listar ocorrências da aplicação: {e}")
        return []
    
def atualizar_aplicacao(id, dados):
    """Atualiza uma aplicação existente"""
    query = """
    UPDATE aplicacoes_pulverizacao
    SET talhao_id=%s, periodo_id=%s, receita_id=%s,
        data_aplicacao=%s, data_prevista_retorno=%s,
        responsavel=%s, condicoes_climaticas=%s, observacoes=%s,
        tipo_aplicacao=%s
    WHERE id=%s
    """
    try:
        executar_query(query, 
            (dados['talhao_id'], dados['periodo_id'], dados.get('receita_id'),
             dados['data_aplicacao'], dados.get('data_prevista_retorno'),  # ← NOME CORRETO
             dados['responsavel'], dados['condicoes'], dados['observacoes'],
             dados.get('tipo_aplicacao', 'Foliar'),
             id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar aplicação: {e}")
        return False

def atualizar_receita(id, dados):
    """Atualiza uma receita existente"""
    query = """
    UPDATE receitas
    SET nome=%s, periodo_id=%s, descricao=%s, formula_completa=%s, produtos=%s, observacoes=%s
    WHERE id=%s
    """
    try:
        executar_query(query, 
            (dados['nome'], dados['periodo_id'], dados['descricao'],
             dados['formula'], dados['produtos'], dados['observacoes'],
             id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar receita: {e}")
        return False

def excluir_receita(id):
    """Exclui uma receita (verifica se não está em uso)"""
    try:
        # Verificar se há aplicações vinculadas
        count = executar_query("SELECT COUNT(*) FROM aplicacoes_pulverizacao WHERE receita_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: receita usada em {count} aplicação(ões)"
        
        executar_query("DELETE FROM receitas WHERE id = %s", (id,))
        return True, "Receita excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir receita: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_periodo(id):
    """Exclui um período da lavoura (verifica se não está em uso)"""
    try:
        # Verificar se há aplicações vinculadas
        count = executar_query("SELECT COUNT(*) FROM aplicacoes_pulverizacao WHERE periodo_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: período usado em {count} aplicação(ões)"
        
        executar_query("UPDATE periodos_lavoura SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Período excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir período: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_praga(id):
    """Exclui uma praga/doença (verifica se não está em uso)"""
    try:
        # Verificar se há ocorrências vinculadas
        count = executar_query("SELECT COUNT(*) FROM ocorrencias_pragas WHERE praga_doenca_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: praga registrada em {count} ocorrência(s)"
        
        executar_query("UPDATE pragas_doencas SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Praga/doença excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir praga: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_aplicacao(id):
    """Exclui uma aplicação (ocorrências serão excluídas por CASCADE)"""
    try:
        executar_query("DELETE FROM aplicacoes_pulverizacao WHERE id = %s", (id,))
        return True, "Aplicação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir aplicação: {e}")
        return False, f"Erro ao excluir: {str(e)}"
    
# =====================================================
# FUNÇÕES PARA EXPORTAÇÃO DE PDF
# =====================================================

def gerar_pdf_pulverizacoes(aplicacoes, data_inicio=None, data_fim=None):
    """Gera arquivo PDF com a lista de pulverizações - VERSÃO PREMIUM"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from datetime import datetime
    import io
    
    buffer = io.BytesIO()
    
    # Configurar documento em paisagem
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    style_normal = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT
    )
    
    style_center = ParagraphStyle(
        'Center',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER
    )
    
    # Título
    titulo_style = styles['Title']
    if data_inicio and data_fim:
        titulo = Paragraph(f"Relatório de Pulverizações", titulo_style)
        subtitulo = Paragraph(f"Período: {data_inicio} a {data_fim}", styles['Normal'])
    else:
        titulo = Paragraph(f"Relatório de Pulverizações", titulo_style)
        subtitulo = Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y')}", styles['Normal'])
    
    elements.append(titulo)
    elements.append(Spacer(1, 0.2*cm))
    elements.append(subtitulo)
    elements.append(Spacer(1, 0.5*cm))
    
    # Preparar dados para tabela
    data = []
    
    # Cabeçalho
    data.append([
        Paragraph('<b>Data</b>', style_center),
        Paragraph('<b>Talhão</b>', style_center),
        Paragraph('<b>Período</b>', style_center),
        Paragraph('<b>Tipo</b>', style_center),
        Paragraph('<b>Receita</b>', style_center),
        Paragraph('<b>Responsável</b>', style_center),
        Paragraph('<b>Retorno</b>', style_center)
    ])
    
    # Dados
    for app in aplicacoes:
        # Data
        if hasattr(app['data_aplicacao'], 'strftime'):
            data_str = app['data_aplicacao'].strftime('%d/%m/%Y')
        else:
            data_str = app['data_aplicacao']
        data_para = Paragraph(data_str, style_center)
        
        # Talhão
        talhao_para = Paragraph(app['talhao_nome'], style_normal)
        
        # Período
        periodo_para = Paragraph(app['periodo_nome'], style_normal)
        
        # Tipo
        tipo = app.get('tipo_aplicacao', 'Foliar')
        if tipo == 'solo':
            tipo_texto = 'Solo'
        else:
            tipo_texto = 'Foliar'
        tipo_para = Paragraph(tipo_texto, style_center)
        
        # Receita
        receita = app['receita_nome'] if app['receita_nome'] != 'Receita não informada' else '-'
        receita_para = Paragraph(receita, style_normal)
        
        # Responsável
        resp = app.get('responsavel', '-') or '-'
        resp_para = Paragraph(resp, style_normal)
        
        # Retorno
        retorno = app.get('data_retorno', '-') or '-'
        retorno_para = Paragraph(str(retorno), style_center)
        
        data.append([data_para, talhao_para, periodo_para, tipo_para, receita_para, resp_para, retorno_para])
    
    # Criar tabela com larguras adequadas
    table = Table(data, colWidths=[2.5*cm, 4*cm, 3*cm, 2.5*cm, 4*cm, 3*cm, 3*cm])
    
# Estilo da tabela
    style = TableStyle([
    # Cabeçalho - Azul petróleo escuro (mais suave que azul forte)
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A6FA5')),  # Azul mais suave
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('TOPPADDING', (0, 0), (-1, 0), 8),
    
    # Corpo da tabela
    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ('TOPPADDING', (0, 1), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ])
    
    # Linhas alternadas
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightblue)
    
    table.setStyle(style)
    elements.append(table)
    
    # Rodapé com estatísticas
    elements.append(Spacer(1, 0.5*cm))
    
    total = len(aplicacoes)
    foliares = sum(1 for app in aplicacoes if app.get('tipo_aplicacao') != 'solo')
    solo = sum(1 for app in aplicacoes if app.get('tipo_aplicacao') == 'solo')
    
    rodape_style = ParagraphStyle(
        'Rodape',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER
    )
    
    rodape = Paragraph(
        f"Total de pulverizações: {total} | Foliares: {foliares} | Solo: {solo}",
        rodape_style
    )
    elements.append(rodape)
    
    # Gerar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# =====================================================
# FUNÇÕES PARA EXPORTAÇÃO DE PDF - RECEITAS
# =====================================================

def gerar_pdf_receitas(receitas, periodo_filtro=None, mes=None, ano=None, termo_busca=None):
    """Gera arquivo PDF com a lista de receitas - VERSÃO COM FILTROS"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from datetime import datetime
    import io
    
    buffer = io.BytesIO()
    
    # Configurar documento em paisagem
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    style_normal = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_LEFT
    )
    
    style_center = ParagraphStyle(
        'Center',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER
    )
    
    # Título
    titulo_style = styles['Title']
    titulo = Paragraph(f"Relatório de Receitas de Pulverização", titulo_style)
    elements.append(titulo)
    elements.append(Spacer(1, 0.2*cm))
    
    # Subtítulo com filtros
    subtitulo_texto = f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    filtros_aplicados = []
    
    if periodo_filtro:
        filtros_aplicados.append(f"Período ID {periodo_filtro}")
    if mes and ano:
        filtros_aplicados.append(f"Mês {mes}/{ano}")
    elif ano:
        filtros_aplicados.append(f"Ano {ano}")
    if termo_busca:
        filtros_aplicados.append(f"Busca: '{termo_busca}'")
    
    if filtros_aplicados:
        subtitulo_texto += " | Filtros: " + ", ".join(filtros_aplicados)
    
    subtitulo = Paragraph(subtitulo_texto, styles['Normal'])
    elements.append(subtitulo)
    elements.append(Spacer(1, 0.5*cm))
    
    # Cabeçalho da tabela
    data = [[
        Paragraph('<b>Nome</b>', style_center),
        Paragraph('<b>Período</b>', style_center),
        Paragraph('<b>Descrição</b>', style_center),
        Paragraph('<b>Fórmula</b>', style_center)
    ]]
    
    # Dados
    for r in receitas:
        nome = Paragraph(r['nome'], style_normal)
        periodo = Paragraph(r.get('periodo_nome', 'Não informado'), style_normal)
        
        descricao = r.get('descricao', '-')
        if descricao and len(descricao) > 150:
            descricao = descricao[:150] + '...'
        desc_para = Paragraph(descricao.replace('\n', '<br/>'), style_normal)
        
        formula = r.get('formula', '-')
        if formula and len(formula) > 200:
            formula = formula[:200] + '...'
        formula_para = Paragraph(formula.replace('\n', '<br/>'), style_normal)
        
        data.append([nome, periodo, desc_para, formula_para])
    
    # Criar tabela
    table = Table(data, colWidths=[5*cm, 3.5*cm, 5.5*cm, 7*cm])
    
    # Estilo da tabela
    style = TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B7A57')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Corpo da tabela
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])
    
    # Linhas alternadas
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
    
    table.setStyle(style)
    elements.append(table)
    
    # Rodapé com total
    elements.append(Spacer(1, 0.5*cm))
    total = len(receitas)
    
    rodape_style = ParagraphStyle(
        'Rodape',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER
    )
    
    rodape = Paragraph(
        f"Total de receitas: {total} | Documento gerado pelo Sistema de Gestão da Fazenda",
        rodape_style
    )
    elements.append(rodape)
    
    # Gerar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def atualizar_retorno(id, dados):
    """Atualiza os dados de retorno de uma aplicação"""
    query = """
    UPDATE aplicacoes_pulverizacao
    SET status_retorno = %s,
        observacoes_retorno = %s,
        data_retorno_realizado = %s
    WHERE id = %s
    """
    try:
        executar_query(query,
            (dados.get('status_retorno'), 
             dados.get('observacoes_retorno'),
             dados.get('data_retorno_realizado'),
             id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar retorno: {e}")
        return False
    
def buscar_retorno_por_aplicacao(id):
    """Busca os dados de retorno de uma aplicação específica"""
    query = """
    SELECT status_retorno, observacoes_retorno, data_retorno_realizado
    FROM aplicacoes_pulverizacao
    WHERE id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'status_retorno': r[0],
                'observacoes_retorno': r[1],
                'data_retorno_realizado': r[2]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar retorno: {e}")
        return None
    
def limpar_retorno(id):
    """Remove os dados de retorno de uma aplicação (volta ao estado pendente)"""
    query = """
    UPDATE aplicacoes_pulverizacao
    SET status_retorno = NULL,
        observacoes_retorno = NULL,
        data_retorno_realizado = NULL
    WHERE id = %s
    """
    try:
        executar_query(query, (id,))
        return True, "Retorno removido com sucesso"
    except Exception as e:
        print(f"Erro ao limpar retorno: {e}")
        return False, f"Erro ao remover: {str(e)}"

