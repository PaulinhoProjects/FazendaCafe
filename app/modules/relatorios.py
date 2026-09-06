"""
Módulo de Geração de Relatórios PDF — AgroCafé
Usa reportlab para gerar PDFs profissionais com cabeçalho padronizado.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime

# Cores da marca AgroCafé
COR_PRIMARIA = HexColor('#1B4332')
COR_ACENT = HexColor('#D4A373')
COR_CINZA = HexColor('#6C757D')
COR_CINZA_CLARO = HexColor('#F8F9FA')
COR_BRANCO = HexColor('#FFFFFF')

def gerar_pdf(titulo, subtitulo, dados, colunas, nome_arquivo, orientacao='retrato'):
    """
    Função genérica para gerar PDFs do AgroCafé.

    Parametros:
    - titulo: str (titulo principal do relatorio)
    - subtitulo: str (subtitulo descritivo)
    - dados: list of lists (linhas de dados, cada linha = lista de valores)
    - colunas: list of str (nomes das colunas)
    - nome_arquivo: str (nome do arquivo .pdf)
    - orientacao: str ('retrato' ou 'paisagem')
    """
    output = io.BytesIO()

    if orientacao == 'paisagem':
        pagesize = A4[1], A4[0]  # landscape
    else:
        pagesize = A4

    doc = SimpleDocTemplate(
        output,
        pagesize=pagesize,
        topMargin=2.5*cm,
        bottomMargin=2*cm,
        leftMargin=2*cm,
        rightMargin=2*cm
    )

    elementos = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    estilo_titulo = ParagraphStyle(
        'TituloAgroCafe',
        parent=styles['Title'],
        fontSize=18,
        textColor=COR_PRIMARIA,
        spaceAfter=4,
        alignment=TA_CENTER
    )

    estilo_subtitulo = ParagraphStyle(
        'SubtituloAgroCafe',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COR_CINZA,
        spaceAfter=20,
        alignment=TA_CENTER
    )

    estilo_cabecalho_tabela = ParagraphStyle(
        'CabecalhoTabela',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COR_BRANCO,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER
    )

    estilo_celula = ParagraphStyle(
        'CelulaAgroCafe',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#343A40'),
        alignment=TA_LEFT
    )

    # Cabeçalho
    elementos.append(Paragraph("AgroCafé", ParagraphStyle(
        'LogoAgroCafe',
        parent=styles['Title'],
        fontSize=22,
        textColor=COR_PRIMARIA,
        fontName='Helvetica-Bold',
        spaceAfter=2,
        alignment=TA_CENTER
    )))
    elementos.append(Paragraph("Tecnologia que Colhe Resultados", ParagraphStyle(
        'SloganAgroCafe',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COR_ACENT,
        spaceAfter=15,
        alignment=TA_CENTER
    )))

    # Linha separadora
    elementos.append(Table(
        [['']],
        colWidths=[pagesize[0] - 4*cm],
        rowHeights=[1],
        style=TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 2, COR_PRIMARIA),
        ])
    ))
    elementos.append(Spacer(1, 15))

    # Titulo e subtitulo do relatorio
    elementos.append(Paragraph(titulo, estilo_titulo))
    elementos.append(Paragraph(subtitulo, estilo_subtitulo))

    # Tabela de dados
    if dados:
        # Converter colunas em Paragraphs
        cabecalho = [Paragraph(col, estilo_cabecalho_tabela) for col in colunas]

        # Converter dados em Paragraphs
        linas_formatadas = [cabecalho]
        for linha in dados:
            linha_fmt = [Paragraph(str(val) if val is not None else '—', estilo_celula) for val in linha]
            linas_formatadas.append(linha_fmt)

        # Largura das colunas
        largura_total = pagesize[0] - 4*cm
        num_colunas = len(colunas)
        largura_coluna = largura_total / num_colunas

        tabela = Table(
            linas_formatadas,
            colWidths=[largura_coluna] * num_colunas,
            repeatRows=1
        )

        tabela.setStyle(TableStyle([
            # Cabecalho
            ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA),
            ('TEXTCOLOR', (0, 0), (-1, 0), COR_BRANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

            # Linhas de dados
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), HexColor('#343A40')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COR_BRANCO, COR_CINZA_CLARO]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),

            # Bordas
            ('LINEBELOW', (0, 0), (-1, 0), 1, COR_PRIMARIA),
            ('LINEBELOW', (0, -1), (-1, -1), 1, COR_CINZA),
        ]))

        elementos.append(tabela)
    else:
        elementos.append(Paragraph(
            "Nenhum dado encontrado para este relatório.",
            ParagraphStyle(
                'SemDados',
                parent=styles['Normal'],
                fontSize=12,
                textColor=COR_CINZA,
                alignment=TA_CENTER,
                spaceBefore=50
            )
        ))

    # Rodapé com data de geração
    elementos.append(Spacer(1, 25))
    elementos.append(Table(
        [[
            Paragraph(
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                ParagraphStyle('RodapeData', parent=styles['Normal'], fontSize=8, textColor=COR_CINZA)
            ),
            Paragraph(
                "AgroCafé · Tecnologia que Colhe Resultados",
                ParagraphStyle('RodapeMarca', parent=styles['Normal'], fontSize=8, textColor=COR_CINZA, alignment=TA_RIGHT)
            )
        ]],
        colWidths=[(pagesize[0] - 4*cm) / 2, (pagesize[0] - 4*cm) / 2]
    ))

    doc.build(elementos)
    output.seek(0)
    return output

def gerar_relatorio_pulverizacoes(data_inicio=None, data_fim=None):
    """Gera relatório PDF de pulverizações por período."""
    from app.modules.dashboard import get_atividades_recentes
    from config.database import executar_query

    query = """
        SELECT
            ap.data_aplicacao,
            t.nome as talhao,
            p.nome as periodo,
            ap.responsavel,
            r.nome as receita,
            ap.data_prevista_retorno,
            ap.status_retorno
        FROM aplicacoes_pulverizacao ap
        JOIN talhoes t ON t.id = ap.talhao_id
        JOIN periodos_lavoura p ON p.id = ap.periodo_id
        LEFT JOIN receitas r ON r.id = ap.receita_id
        ORDER BY ap.data_aplicacao DESC
    """
    params = []
    if data_inicio and data_fim:
        query = """
            SELECT
                ap.data_aplicacao,
                t.nome as talhao,
                p.nome as periodo,
                ap.responsavel,
                r.nome as receita,
                ap.data_prevista_retorno,
                ap.status_retorno
            FROM aplicacoes_pulverizacao ap
            JOIN talhoes t ON t.id = ap.talhao_id
            JOIN periodos_lavoura p ON p.id = ap.periodo_id
            LEFT JOIN receitas r ON r.id = ap.receita_id
            WHERE ap.data_aplicacao BETWEEN %s AND %s
            ORDER BY ap.data_aplicacao DESC
        """
        params = [data_inicio, data_fim]

    try:
        resultado = executar_query(query, tuple(params) if params else None, fetch_all=True)
    except Exception:
        resultado = []

    dados = []
    for r in resultado:
        dados.append([
            r[0].strftime('%d/%m/%Y') if r[0] else '—',
            r[1] or '—',
            r[2] or '—',
            r[3] or '—',
            r[4] or 'Não informada',
            r[5].strftime('%d/%m/%Y') if r[5] else '—',
            r[6] or '—'
        ])

    colunas = ['Data', 'Talhão', 'Período', 'Responsável', 'Receita', 'Data Retorno', 'Status']
    subtitulo = f"Total: {len(dados)} aplicações"
    if data_inicio and data_fim:
        subtitulo += f" | Período: {data_inicio} a {data_fim}"

    return gerar_pdf(
        'Relatório de Pulverizações',
        subtitulo,
        dados,
        colunas,
        f'pulverizacoes_{datetime.now().strftime("%Y%m%d")}.pdf',
        orientacao='paisagem'
    )

def gerar_relatorio_estoque():
    """Gera relatório PDF do estoque atual."""
    from app.modules import estoque

    try:
        produtos = estoque.listar_produtos(ativos=True)
    except Exception:
        produtos = []

    dados = []
    for p in produtos:
        dados.append([
            p.get('nome', '—'),
            p.get('categoria', '—'),
            p.get('unidade', '—'),
            f"{p.get('quantidade_atual', 0)}",
            f"{p.get('estoque_minimo', 0)}",
            f"R$ {p.get('valor_unitario', 0):.2f}" if p.get('valor_unitario') else '—',
            'BAIXO' if p.get('quantidade_atual', 0) <= (p.get('estoque_minimo') or 0) else 'OK'
        ])

    colunas = ['Produto', 'Categoria', 'Unidade', 'Qtd Atual', 'Qtd Mínima', 'Valor Unit.', 'Status']
    total_baixo = sum(1 for d in dados if d[-1] == 'BAIXO')

    return gerar_pdf(
        'Relatório de Estoque',
        f"Total: {len(dados)} produtos | Estoque baixo: {total_baixo}",
        dados,
        colunas,
        f'estoque_{datetime.now().strftime("%Y%m%d")}.pdf',
        orientacao='paisagem'
    )

def gerar_relatorio_analises():
    """Gera relatório PDF de análises."""
    from app.modules import analises

    try:
        lista = analises.listar_analises()
    except Exception:
        lista = []

    dados = []
    for a in lista:
        dados.append([
            a.get('data_coleta', '—').strftime('%d/%m/%Y') if hasattr(a.get('data_coleta'), 'strftime') else str(a.get('data_coleta', '—')),
            a.get('talhao', '—') or a.get('talhao_nome', '—'),
            a.get('tipo', '—') or a.get('tipo_analise', '—'),
            a.get('laboratorio', '—') or 'Não informado',
            a.get('responsavel', '—') or '—',
            'Pendente' if not a.get('data_resultado') else 'Concluída'
        ])

    colunas = ['Data Coleta', 'Talhão', 'Tipo', 'Laboratório', 'Responsável', 'Status']
    total_pendentes = sum(1 for d in dados if d[-1] == 'Pendente')

    return gerar_pdf(
        'Relatório de Análises',
        f"Total: {len(dados)} análises | Pendentes: {total_pendentes}",
        dados,
        colunas,
        f'analises_{datetime.now().strftime("%Y%m%d")}.pdf',
        orientacao='paisagem'
    )

def gerar_relatorio_manejos():
    """Gera relatório PDF de manejos do mato."""
    from app.modules import manejo_mato

    try:
        manejos = manejo_mato.listar_manejos()
    except Exception:
        manejos = []

    dados = []
    for m in manejos:
        dados.append([
            m.get('data_manejo', '—').strftime('%d/%m/%Y') if hasattr(m.get('data_manejo'), 'strftime') else str(m.get('data_manejo', '—')),
            m.get('talhao', '—') or m.get('talhao_nome', '—'),
            m.get('tipo_manejo', '—'),
            m.get('produtos', '—') or 'Não informado',
            m.get('responsavel', '—') or '—'
        ])

    colunas = ['Data', 'Talhão', 'Tipo de Manejo', 'Produtos', 'Responsável']

    return gerar_pdf(
        'Relatório de Manejos do Mato',
        f"Total: {len(dados)} manejos registrados",
        dados,
        colunas,
        f'manejos_{datetime.now().strftime("%Y%m%d")}.pdf',
        orientacao='retrato'
    )