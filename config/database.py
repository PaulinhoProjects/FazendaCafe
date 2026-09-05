"""
Módulo de conexão com o banco de dados PostgreSQL
CORRIGIDO - Versão estável com cálculo de pés de café
"""

import psycopg2
from psycopg2 import pool
import os
import re
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
# FUNÇÕES DE CÁLCULO
# =====================================================

def calcular_pes_cafe(area, espacamento):
    """
    Calcula o número aproximado de pés de café baseado na área e espaçamento
    Retorna: (numero_pes, formula_utilizada)
    """
    if not area or area <= 0:
        return 0, "Área não informada"
    
    if not espacamento:
        return 0, "Espaçamento não informado"
    
    try:
        # Extrair números do espaçamento (ex: "3,5 x 1,2" ou "3.5x0.8")
        numeros = re.findall(r'(\d+[.,]?\d*)', espacamento)
        
        if len(numeros) < 2:
            return 0, "Formato de espaçamento inválido"
        
        # Converter vírgula para ponto e parse para float
        entre_linhas = float(numeros[0].replace(',', '.'))
        entre_plantas = float(numeros[1].replace(',', '.'))
        
        if entre_linhas <= 0 or entre_plantas <= 0:
            return 0, "Valores de espaçamento inválidos"
        
        # Cálculo: plantas por hectare = 10000 / (espaçamento_linhas * espaçamento_plantas)
        plantas_por_ha = 10000 / (entre_linhas * entre_plantas)
        total_plantas = plantas_por_ha * area
        
        formula = f"{plantas_por_ha:.0f} plantas/ha × {area:.2f} ha = {total_plantas:.0f} plantas"
        
        return round(total_plantas), formula
        
    except Exception as e:
        print(f"Erro ao calcular pés: {e}")
        return 0, "Erro no cálculo"

# =====================================================
# FUNÇÕES PARA TALHÕES (VERSÃO ÚNICA E CORRETA)
# =====================================================

def listar_talhoes(ativos=True):
    """Retorna lista de todos os talhões - COM CÁLCULO DE PÉS"""
    query = """
    SELECT 
        id, 
        nome, 
        area_hectares, 
        data_plantio,
        variedade_cafe, 
        altitude_media,
        espacamento
    FROM talhoes 
    WHERE ativo = %s 
    """
    try:
        resultado = executar_query(query, (ativos,), fetch_all=True)
        if not resultado:
            return []
        
        talhoes_lista = []
        total_pes_geral = 0
        
        for row in resultado:
            area = float(row[2]) if row[2] is not None else 0
            espacamento = row[6]
            
            # Calcular pés de café
            pes, formula = calcular_pes_cafe(area, espacamento)
            total_pes_geral += pes
            
            talhao = {
                'id': row[0],
                'nome': row[1],
                'area': area,
                'data_plantio': row[3],
                'variedade': row[4] if row[4] else 'Não informada',
                'altitude': float(row[5]) if row[5] is not None else None,
                'espacamento': espacamento,
                'pes_cafe': pes,
                'formula_pes': formula
            }
            talhoes_lista.append(talhao)
        
        # Ordenar manualmente em Python pelo número no nome
        def extrair_numero(nome):
            match = re.search(r'^(\d+)', nome)
            return int(match.group(1)) if match else 9999
        
        talhoes_lista.sort(key=lambda x: extrair_numero(x['nome']))
        
        return talhoes_lista
    except Exception as e:
        print(f"Erro ao listar talhões: {e}")
        return []

def buscar_talhao_por_id(talhao_id):
    """Busca um talhão específico pelo ID"""
    query = "SELECT * FROM talhoes WHERE id = %s"
    try:
        return executar_query(query, (talhao_id,), fetch_one=True)
    except Exception as e:
        print(f"Erro ao buscar talhão: {e}")
        return None

def inserir_talhao(dados):
    """Insere um novo talhão"""
    query = """
    INSERT INTO talhoes (nome, area_hectares, data_plantio, variedade_cafe, altitude_media, observacoes, espacamento)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(
            query, 
            (dados['nome'], dados['area'], dados['data_plantio'], 
             dados['variedade'], dados['altitude'], dados['observacoes'],
             dados.get('espacamento')),
            fetch_one=True
        )
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir talhão: {e}")
        return None

def atualizar_talhao(id, dados):
    """Atualiza um talhão existente"""
    query = """
    UPDATE talhoes 
    SET nome=%s, area_hectares=%s, data_plantio=%s, 
        variedade_cafe=%s, altitude_media=%s, observacoes=%s,
        espacamento=%s
    WHERE id=%s
    """
    try:
        executar_query(query, 
            (dados['nome'], dados['area'], dados['data_plantio'],
             dados['variedade'], dados['altitude'], dados['observacoes'],
             dados.get('espacamento'), id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar talhão: {e}")
        return False

def excluir_talhao(talhao_id):
    """Exclui um talhão (exclusão lógica - marca como inativo)"""
    query = "UPDATE talhoes SET ativo = FALSE WHERE id = %s"
    try:
        executar_query(query, (talhao_id,))
        return True
    except Exception as e:
        print(f"Erro ao excluir talhão: {e}")
        return False

def criar_tabela_talhoes():
    """Cria a tabela de talhões se ela não existir"""
    query = """
    CREATE TABLE IF NOT EXISTS talhoes (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        area_hectares DECIMAL(10,2) NOT NULL,
        data_plantio DATE,
        variedade_cafe VARCHAR(50),
        altitude_media DECIMAL(10,2),
        espacamento VARCHAR(50),
        observacoes TEXT,
        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo BOOLEAN DEFAULT TRUE
    );
    """
    try:
        executar_query(query)
        print("Tabela 'talhoes' verificada/criada com sucesso!")
        return True
    except Exception as e:
        print(f"Erro ao criar tabela: {e}")
        return False

# =====================================================
# FUNÇÕES PARA EXPORTAÇÃO DE PDF
# =====================================================

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
import io

def gerar_pdf_talhoes(talhoes):
    """Gera arquivo PDF com a lista de talhões - COM PÉS DE CAFÉ"""
    buffer = io.BytesIO()
    
    # Configurar documento
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=2*cm,
        bottomMargin=1.5*cm,
        title="Relatório de Talhões",
        author="Sistema Fazenda Café"
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Calcular totais
    total_pes = sum(t.get('pes_cafe', 0) for t in talhoes)
    area_total = sum(t['area'] for t in talhoes)
    
    # Função para adicionar cabeçalho e rodapé
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1*cm, doc.height + 1*cm, "Sítio do Morro do Paiol - Relatório de Talhões")
        canvas.drawRightString(doc.width + 1*cm, doc.height + 1*cm, datetime.now().strftime('%d/%m/%Y %H:%M'))
        canvas.drawString(1*cm, 0.75*cm, f"Página {doc.page}")
        canvas.drawRightString(doc.width + 1*cm, 0.75*cm, "Documento gerado pelo Sistema de Gestão")
        canvas.restoreState()
    
    doc.build = lambda *args, **kwargs: SimpleDocTemplate.build(doc, onFirstPage=add_page_number, onLaterPages=add_page_number, *args, **kwargs)
    
    # Título
    titulo_style = styles['Title']
    titulo = Paragraph(f"Relatório de Talhões", titulo_style)
    elements.append(titulo)
    elements.append(Spacer(1, 0.3*cm))
    
    # Subtítulo com resumo
    subtitulo = Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')} | "
        f"Total de talhões: {len(talhoes)} | "
        f"Área total: {area_total:.2f} ha | "
        f"Total de pés: {total_pes:,.0f}".replace(',', '.'),
        styles['Normal']
    )
    elements.append(subtitulo)
    elements.append(Spacer(1, 0.5*cm))
    
    # Cabeçalho da tabela
    data = [['Nome', 'Área (ha)', 'Plantio', 'Variedade', 'Altitude (m)', 'Espaçamento', 'Pés de Café']]
    
    # Dados
    for t in talhoes:
        data.append([
            t['nome'],
            f"{t['area']:.2f}",
            str(t['data_plantio']) if t['data_plantio'] else '-',
            t['variedade'] if t['variedade'] else '-',
            f"{t['altitude']:.0f}" if t['altitude'] else '-',
            t['espacamento'] if t['espacamento'] else '-',
            f"{t.get('pes_cafe', 0):,.0f}".replace(',', '.') if t.get('pes_cafe', 0) > 0 else '-'
        ])
    
    # Criar tabela
    table = Table(data, colWidths=[4.5*cm, 2.5*cm, 2.5*cm, 3.5*cm, 2.5*cm, 3.5*cm, 3*cm], repeatRows=1)
    
    # Estilo da tabela
    style = TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5f2d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Corpo da tabela
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-2, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
    ])
    
    # Linhas alternadas
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f2f2f2'))
    
    table.setStyle(style)
    elements.append(table)
    
    # Rodapé com total de pés
    elements.append(Spacer(1, 0.5*cm))
    rodape_style = ParagraphStyle(
        'Rodape',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_RIGHT
    )
    rodape = Paragraph(
        f"<b>Total aproximado de pés de café na fazenda: {total_pes:,.0f}</b>".replace(',', '.'),
        rodape_style
    )
    elements.append(rodape)
    
    # Observação sobre o cálculo
    nota = Paragraph(
        "<i>* Cálculo aproximado baseado na área e espaçamento informados</i>",
        styles['Italic']
    )
    elements.append(nota)
    
    # Gerar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# =====================================================
# TESTE
# =====================================================
if __name__ == "__main__":
    print("Testando conexão com o banco de dados...")
    
    if ConexaoBanco.inicializar_pool():
        criar_tabela_talhoes()
        
        talhoes = listar_talhoes()
        print(f"\nTalhões encontrados: {len(talhoes)}")
        for t in talhoes:
            print(f"{t['nome']} - Área: {t['area']}ha - Pés: {t.get('pes_cafe', 0)}")
        
        # Não fechar o pool aqui
    else:
        print("Falha ao inicializar pool de conexões")