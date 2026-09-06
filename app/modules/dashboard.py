"""
M├│dulo de Dashboard e Estat├¡sticas
Fun├º├Áes para gerar dados dos gr├íficos e resumos
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime, timedelta



def get_resumo_geral():
    """Retorna resumo geral da fazenda"""
    resumo = {}
    
    # Total de talh├Áes
    query_talhoes = "SELECT COUNT(*) FROM talhoes WHERE ativo = TRUE"
    resumo['total_talhoes'] = executar_query(query_talhoes, fetch_one=True)[0] or 0
    
    # ├ürea total
    query_area = "SELECT SUM(area_hectares) FROM talhoes WHERE ativo = TRUE"
    resumo['area_total'] = float(executar_query(query_area, fetch_one=True)[0] or 0)
    
    # Total de pulveriza├º├Áes no ano
    query_pulv = """
    SELECT COUNT(*) FROM aplicacoes_pulverizacao 
    WHERE EXTRACT(YEAR FROM data_aplicacao) = EXTRACT(YEAR FROM CURRENT_DATE)
    """
    resumo['pulverizacoes_ano'] = executar_query(query_pulv, fetch_one=True)[0] or 0
    
    # Total de pragas registradas
    query_pragas = "SELECT COUNT(DISTINCT praga_doenca_id) FROM ocorrencias_pragas"
    resumo['pragas_detectadas'] = executar_query(query_pragas, fetch_one=True)[0] or 0
    
    return resumo

def get_atividades_recentes(limite=10):
    """Retorna as ├║ltimas atividades (pulveriza├º├Áes)"""
    query = """
    SELECT 
        ap.data_aplicacao,
        t.nome as talhao,
        p.nome as periodo,
        r.nome as receita,
        ap.responsavel,
        ap.id
    FROM aplicacoes_pulverizacao ap
    JOIN talhoes t ON t.id = ap.talhao_id
    JOIN periodos_lavoura p ON p.id = ap.periodo_id
    LEFT JOIN receitas r ON r.id = ap.receita_id
    ORDER BY ap.data_aplicacao DESC
    LIMIT %s
    """
    try:
        resultado = executar_query(query, (limite,), fetch_all=True)
        atividades = []
        for r in resultado:
            atividades.append({
                'data': r[0],
                'talhao': r[1],
                'periodo': r[2],
                'receita': r[3] or 'N├úo informada',
                'responsavel': r[4] or 'N├úo informado',
                'id': r[5]
            })
        return atividades
    except Exception as e:
        print(f"Erro ao buscar atividades: {e}")
        return []

def get_alertas_retorno():
    """Retorna pulveriza├º├Áes com data de retorno pr├│xima ou atrasada (n├úo resolvidas)"""
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=7)  # Pr├│ximos 7 dias
    
    query = """
    SELECT 
        ap.id,
        t.nome as talhao,
        ap.data_aplicacao,
        ap.data_prevista_retorno,
        p.nome as periodo,
        CASE 
            WHEN ap.data_prevista_retorno < CURRENT_DATE THEN 'atrasado'
            WHEN ap.data_prevista_retorno <= %s THEN 'proximo'
            ELSE 'ok'
        END as status
    FROM aplicacoes_pulverizacao ap
    JOIN talhoes t ON t.id = ap.talhao_id
    JOIN periodos_lavoura p ON p.id = ap.periodo_id
    WHERE ap.data_prevista_retorno IS NOT NULL
    AND ap.data_prevista_retorno <= %s
    AND (ap.status_retorno IS NULL OR ap.status_retorno != 'concluido')
    ORDER BY ap.data_prevista_retorno ASC
    """
    try:
        resultado = executar_query(query, (limite, limite), fetch_all=True)
        alertas = []
        for r in resultado:
            alertas.append({
                'id': r[0],
                'talhao': r[1],
                'data_aplicacao': r[2],
                'data_retorno': r[3],
                'periodo': r[4],
                'status': r[5]
            })
        return alertas
    except Exception as e:
        print(f"Erro ao buscar alertas: {e}")
        return []

def get_pragas_por_talhao():
    """Retorna contagem de pragas por talh├úo para gr├ífico"""
    query = """
    SELECT 
        t.nome,
        COUNT(op.id) as total_ocorrencias
    FROM talhoes t
    LEFT JOIN ocorrencias_pragas op ON op.talhao_id = t.id
    WHERE t.ativo = TRUE
    GROUP BY t.id, t.nome
    ORDER BY total_ocorrencias DESC
    LIMIT 10
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        labels = [r[0] for r in resultado]
        dados = [r[1] for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar pragas por talh├úo: {e}")
        return {'labels': [], 'dados': []}

def get_aplicacoes_por_periodo():
    """Retorna distribui├º├úo de aplica├º├Áes por per├¡odo da lavoura"""
    query = """
    SELECT 
        p.nome,
        COUNT(ap.id) as total
    FROM periodos_lavoura p
    LEFT JOIN aplicacoes_pulverizacao ap ON ap.periodo_id = p.id
    GROUP BY p.id, p.nome
    ORDER BY total DESC
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        labels = [r[0] for r in resultado]
        dados = [r[1] for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar aplica├º├Áes por per├¡odo: {e}")
        return {'labels': [], 'dados': []}

def get_aplicacoes_ultimos_6_meses():
    """Retorna n├║mero de aplica├º├Áes nos ├║ltimos 6 meses"""
    query = """
    SELECT 
        TO_CHAR(data_aplicacao, 'YYYY-MM') as mes,
        COUNT(*) as total
    FROM aplicacoes_pulverizacao
    WHERE data_aplicacao >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY TO_CHAR(data_aplicacao, 'YYYY-MM')
    ORDER BY mes ASC
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        meses = []
        dados = []
        for r in resultado:
            # Converter YYYY-MM para nome do m├¬s
            ano, mes = r[0].split('-')
            meses.append(f"{mes}/{ano}")
            dados.append(r[1])
        return {'labels': meses, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar aplica├º├Áes mensais: {e}")
        return {'labels': [], 'dados': []}

def get_tipos_pragas():
    """Retorna distribui├º├úo de pragas vs doen├ºas"""
    query = """
    SELECT 
        pd.tipo,
        COUNT(op.id) as total
    FROM pragas_doencas pd
    LEFT JOIN ocorrencias_pragas op ON op.praga_doenca_id = pd.id
    GROUP BY pd.tipo
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        tipos = []
        dados = []
        for r in resultado:
            tipos.append(r[0].capitalize() + 's')
            dados.append(r[1])
        return {'labels': tipos, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar tipos de pragas: {e}")
        return {'labels': [], 'dados': []}
    
def get_resumo_estoque():
    """Retorna resumo do estoque para o dashboard"""
    try:
        # Total de produtos
        total_produtos = executar_query("SELECT COUNT(*) FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True)[0]
        
        # Produtos com estoque baixo
        estoque_baixo = executar_query("""
            SELECT COUNT(*) FROM produtos_estoque 
            WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)
        """, fetch_one=True)[0]
        
        # Total de itens em estoque
        total_itens = executar_query("SELECT SUM(quantidade_atual) FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True)[0]
        
        return {
            'total_produtos': total_produtos or 0,
            'estoque_baixo': estoque_baixo or 0,
            'total_itens': float(total_itens) if total_itens else 0
        }
    except Exception as e:
        print(f"Erro ao buscar resumo estoque: {e}")
        return {'total_produtos': 0, 'estoque_baixo': 0, 'total_itens': 0}

def get_resumo_analises():
    """Retorna resumo das an├ílises para o dashboard (apenas ativas)"""
    try:
        # Total de an├ílises no ano (ativas)
        analises_ano = executar_query("""
            SELECT COUNT(*) FROM analises 
            WHERE EXTRACT(YEAR FROM data_coleta) = EXTRACT(YEAR FROM CURRENT_DATE)
            AND ativo = TRUE
        """, fetch_one=True)[0]
        
        # An├ílises pendentes (sem resultado) e ativas
        pendentes = executar_query("""
            SELECT COUNT(*) FROM analises 
            WHERE data_resultado IS NULL
            AND ativo = TRUE
        """, fetch_one=True)[0]
        
        # ├Ültima an├ílise ativa
        ultima = executar_query("""
            SELECT data_coleta, talhao_id FROM analises 
            WHERE ativo = TRUE
            ORDER BY data_coleta DESC LIMIT 1
        """, fetch_one=True)
        
        return {
            'analises_ano': analises_ano or 0,
            'pendentes': pendentes or 0,
            'ultima_data': ultima[0] if ultima else None,
            'ultima_talhao': ultima[1] if ultima else None
        }
    except Exception as e:
        print(f"Erro ao buscar resumo an├ílises: {e}")
        return {'analises_ano': 0, 'pendentes': 0}

def get_resumo_pdfs():
    """Retorna resumo dos PDFs para o dashboard"""
    import os
    from flask import current_app
    
    try:
        pdf_folder = current_app.config['UPLOAD_FOLDER']
        total_pdfs = 0
        pdfs_mes = 0
        
        if os.path.exists(pdf_folder):
            from datetime import datetime
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year
            
            for arquivo in os.listdir(pdf_folder):
                if arquivo.endswith('.pdf'):
                    total_pdfs += 1
                    # Verificar data do arquivo
                    caminho = os.path.join(pdf_folder, arquivo)
                    data_mod = datetime.fromtimestamp(os.path.getmtime(caminho))
                    if data_mod.month == mes_atual and data_mod.year == ano_atual:
                        pdfs_mes += 1
        
        return {
            'total_pdfs': total_pdfs,
            'pdfs_mes': pdfs_mes
        }
    except Exception as e:
        print(f"Erro ao buscar resumo PDFs: {e}")
        return {'total_pdfs': 0, 'pdfs_mes': 0}

def get_produtos_estoque_baixo(limite=5):
    """Retorna lista de produtos com estoque baixo"""
    try:
        query = """
        SELECT id, nome, quantidade_atual, estoque_minimo, unidade
        FROM produtos_estoque 
        WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)
        ORDER BY quantidade_atual ASC
        LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        
        produtos = []
        for r in resultado:
            produtos.append({
                'id': r[0],
                'nome': r[1],
                'quantidade': float(r[2]) if r[2] else 0,
                'minimo': float(r[3]) if r[3] else 0,
                'unidade': r[4]
            })
        return produtos
    except Exception as e:
        print(f"Erro ao buscar produtos estoque baixo: {e}")
        return []

def get_ultimas_analises(limite=3):
    """Retorna as ├║ltimas an├ílises registradas (apenas ativas)"""
    try:
        query = """
        SELECT a.id, a.data_coleta, t.nome as talhao, tp.nome as tipo,
               CASE WHEN a.data_resultado IS NULL THEN 'Pendente' ELSE 'Conclu├¡da' END as status
        FROM analises a
        JOIN talhoes t ON t.id = a.talhao_id
        JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
        WHERE a.ativo = TRUE
        ORDER BY a.data_coleta DESC
        LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        
        analises = []
        for r in resultado:
            analises.append({
                'id': r[0],
                'data': r[1],
                'talhao': r[2],
                'tipo': r[3],
                'status': r[4]
            })
        return analises
    except Exception as e:
        print(f"Erro ao buscar ├║ltimas an├ílises: {e}")
        return []

def get_ultimos_manejos(limite=3):
    """Retorna os ├║ltimos manejos do mato registrados"""
    try:
        query = """
        SELECT m.id, m.data_manejo, t.nome as talhao, m.tipo_manejo
        FROM manejos_mato m
        JOIN talhoes t ON t.id = m.talhao_id
        ORDER BY m.data_manejo DESC
        LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        
        manejos = []
        for r in resultado:
            manejos.append({
                'id': r[0],
                'data': r[1],
                'talhao': r[2],
                'tipo': r[3]
            })
        return manejos
    except Exception as e:
        print(f"Erro ao buscar ├║ltimos manejos: {e}")
        return []
    
