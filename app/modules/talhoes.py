import io
from config.database import executar_query
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime

def criar_tabela_talhoes():
    query = """
    CREATE TABLE IF NOT EXISTS talhoes (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        area_hectares NUMERIC(10,2) NOT NULL,
        data_plantio DATE,
        variedade_cafe VARCHAR(100),
        altitude_media NUMERIC(10,2),
        observacoes TEXT,
        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo BOOLEAN DEFAULT TRUE,
        espacamento VARCHAR(50),
        produtor_id INTEGER
    )
    """
    executar_query(query)

def listar_talhoes(ativos=True):
    """Retorna a lista de talhões com aliases e cálculo de pés de café."""
    query = """
    SELECT 
        id, 
        nome, 
        area_hectares, 
        area_hectares AS area,
        data_plantio, 
        variedade_cafe, 
        variedade_cafe AS variedade,
        altitude_media, 
        altitude_media AS altitude,
        observacoes, 
        data_cadastro, 
        ativo, 
        espacamento, 
        produtor_id
    FROM talhoes 
    WHERE (%s IS NULL OR ativo = %s)
    ORDER BY id
    """
    rows = executar_query(query, (ativos, ativos), fetch_all=True)
    if not rows:
        return []
    
    lista = []
    for r in rows:
        d = dict(r)
        d['area'] = float(r['area_hectares']) if r['area_hectares'] is not None else 0.0
        d['variedade'] = r['variedade_cafe'] or ''
        d['altitude'] = float(r['altitude_media']) if r['altitude_media'] is not None else None
        
        pes_cafe = 0
        if r['espacamento']:
            try:
                esp = str(r['espacamento']).lower().replace(',', '.')
                partes = [p.strip() for p in esp.split('x')]
                if len(partes) >= 2:
                    el = float(partes[0])
                    ep = float(partes[1])
                    if el > 0 and ep > 0:
                        plantas_por_ha = 10000.0 / (el * ep)
                        pes_cafe = int(round(plantas_por_ha * d['area']))
            except Exception:
                pes_cafe = 0
        d['pes_cafe'] = pes_cafe
        lista.append(d)
    return lista

def buscar_talhao_por_id(talhao_id):
    """Busca um talhão pelo ID."""
    query = """
    SELECT 
        id, 
        nome, 
        area_hectares, 
        data_plantio, 
        variedade_cafe, 
        altitude_media, 
        observacoes, 
        data_cadastro, 
        ativo, 
        espacamento, 
        produtor_id
    FROM talhoes 
    WHERE id = %s
    """
    return executar_query(query, (talhao_id,), fetch_one=True)

def inserir_talhao(dados_ou_nome, area=None, numero_pes=None, variedade=None, 
                   espacamento_rua=None, espacamento_planta=None, data_plantio=None, 
                   altitude=None, observacoes=None, espacamento=None):
    """Insere um novo talhão no banco."""
    if isinstance(dados_ou_nome, dict):
        d = dados_ou_nome
        nome = d.get('nome')
        area = d.get('area') or d.get('area_hectares')
        data_plantio = d.get('data_plantio') or None
        variedade = d.get('variedade') or d.get('variedade_cafe') or ''
        altitude = d.get('altitude') or d.get('altitude_media') or None
        observacoes = d.get('observacoes') or ''
        espacamento = d.get('espacamento') or None
    else:
        nome = dados_ou_nome
        if espacamento is None and espacamento_rua and espacamento_planta:
            espacamento = f"{espacamento_rua} x {espacamento_planta}"

    query = """
    INSERT INTO talhoes (nome, area_hectares, data_plantio, variedade_cafe, altitude_media, observacoes, espacamento, ativo)
    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING id
    """
    result = executar_query(query, (nome, area, data_plantio, variedade, altitude, observacoes, espacamento), fetch_one=True)
    return result['id'] if result else None

def atualizar_talhao(talhao_id, dados_ou_nome, area=None, numero_pes=None, variedade=None, 
                      espacamento_rua=None, espacamento_planta=None, data_plantio=None, 
                      altitude=None, observacoes=None, espacamento=None):
    """Atualiza um talhão existente."""
    if isinstance(dados_ou_nome, dict):
        d = dados_ou_nome
        nome = d.get('nome')
        area = d.get('area') or d.get('area_hectares')
        data_plantio = d.get('data_plantio') or None
        variedade = d.get('variedade') or d.get('variedade_cafe') or ''
        altitude = d.get('altitude') or d.get('altitude_media') or None
        observacoes = d.get('observacoes') or ''
        espacamento = d.get('espacamento') or None
    else:
        nome = dados_ou_nome
        if espacamento is None and espacamento_rua and espacamento_planta:
            espacamento = f"{espacamento_rua} x {espacamento_planta}"

    query = """
    UPDATE talhoes SET 
        nome = %s, area_hectares = %s, data_plantio = %s, 
        variedade_cafe = %s, altitude_media = %s, observacoes = %s, 
        espacamento = %s
    WHERE id = %s
    """
    executar_query(query, (nome, area, data_plantio, variedade, altitude, observacoes, espacamento, talhao_id))
    return True

def excluir_talhao(talhao_id):
    """Desativa ou exclui o talhão."""
    query = "UPDATE talhoes SET ativo = FALSE WHERE id = %s"
    executar_query(query, (talhao_id,))
    return True

def gerar_pdf_talhoes(talhoes):
    """Gera um PDF com a lista de talhões."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2C5F2D')
    )
    
    elements = []
    elements.append(Paragraph("<b>Fazenda Café - Relatório de Talhões</b>", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    data = [["ID", "Nome", "Área (ha)", "Variedade", "Espaçamento", "Pés Est.", "Altitude (m)", "Data Plantio"]]
    for t in talhoes:
        dt_str = t['data_plantio'].strftime('%d/%m/%Y') if t.get('data_plantio') and hasattr(t['data_plantio'], 'strftime') else (str(t.get('data_plantio') or '—'))
        data.append([
            str(t.get('id', '')),
            str(t.get('nome', '')),
            f"{t.get('area', 0):.2f}",
            str(t.get('variedade', '') or '—'),
            str(t.get('espacamento', '') or '—'),
            f"{t.get('pes_cafe', 0):,}".replace(',', '.') if t.get('pes_cafe') else '—',
            f"{t.get('altitude', 0):.0f}" if t.get('altitude') else '—',
            dt_str
        ])
    
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C5F2D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')])
    ]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
