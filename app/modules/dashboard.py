"""
Módulo de Dashboard e Estatísticas
Funções para gerar dados dos gráficos e resumos
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime, timedelta



def get_resumo_geral():
    """Retorna resumo geral da fazenda"""
    resumo = {}
    
    # Total de talhões
    query_talhoes = "SELECT COUNT(*) FROM talhoes WHERE ativo = TRUE"
    resultado = executar_query(query_talhoes, fetch_one=True)
    resumo['total_talhoes'] = resultado['count'] if resultado else 0
    
    # Área total
    query_area = "SELECT SUM(area_hectares) FROM talhoes WHERE ativo = TRUE"
    resultado = executar_query(query_area, fetch_one=True)
    resumo['area_total'] = float(resultado['sum'] if resultado else 0)
    
    # Total de pulverizações no ano
    query_pulv = """
    SELECT COUNT(*) FROM aplicacoes_pulverizacao 
    WHERE EXTRACT(YEAR FROM data_aplicacao) = EXTRACT(YEAR FROM CURRENT_DATE)
    """
    resultado = executar_query(query_pulv, fetch_one=True)
    resumo['pulverizacoes_ano'] = resultado['count'] if resultado else 0
    
    # Total de pragas registradas
    query_pragas = "SELECT COUNT(DISTINCT praga_doenca_id) FROM ocorrencias_pragas"
    resultado = executar_query(query_pragas, fetch_one=True)
    resumo['pragas_detectadas'] = resultado['count'] if resultado else 0
    
    return resumo

def get_atividades_recentes(limite=10):
    """Retorna as últimas atividades (pulverizações)"""
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
                'data': r['data_aplicacao'],
                'talhao': r['talhao'],
                'periodo': r['periodo'],
                'receita': r['receita'] or 'Não informada',
                'responsavel': r['responsavel'] or 'Não informado',
                'id': r['id']
            })
        return atividades
    except Exception as e:
        print(f"Erro ao buscar atividades: {e}")
        return []

def get_alertas_retorno():
    """Retorna pulverizações com data de retorno próxima ou atrasada (não resolvidas)"""
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=7)  # Próximos 7 dias
    
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
                'id': r['id'],
                'talhao': r['talhao'],
                'data_aplicacao': r['data_aplicacao'],
                'data_retorno': r['data_prevista_retorno'],
                'periodo': r['periodo'],
                'status': r['status']
            })
        return alertas
    except Exception as e:
        print(f"Erro ao buscar alertas: {e}")
        return []

def get_pragas_por_talhao():
    """Retorna contagem de pragas por talhão para gráfico"""
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
        labels = [r['nome'] for r in resultado]
        dados = [r['total_ocorrencias'] for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar pragas por talhão: {e}")
        return {'labels': [], 'dados': []}

def get_aplicacoes_por_periodo():
    """Retorna distribuição de aplicações por período da lavoura"""
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
        labels = [r['nome'] for r in resultado]
        dados = [r['total'] for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar aplicações por período: {e}")
        return {'labels': [], 'dados': []}

def get_aplicacoes_ultimos_6_meses():
    """Retorna número de aplicações nos últimos 6 meses"""
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
            # Converter YYYY-MM para nome do mês
            ano, mes = r['mes'].split('-')
            meses.append(f"{mes}/{ano}")
            dados.append(r['total'])
        return {'labels': meses, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar aplicações mensais: {e}")
        return {'labels': [], 'dados': []}

def get_tipos_pragas():
    """Retorna distribuição de pragas vs doenças"""
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
            tipos.append(r['tipo'].capitalize() + 's')
            dados.append(r['total'])
        return {'labels': tipos, 'dados': dados}
    except Exception as e:
        print(f"Erro ao buscar tipos de pragas: {e}")
        return {'labels': [], 'dados': []}
    
def get_resumo_estoque():
    """Retorna resumo do estoque para o dashboard"""
    try:
        # Total de produtos
        resultado = executar_query("SELECT COUNT(*) FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True)
        total_produtos = resultado['count'] if resultado else 0
        
        # Produtos com estoque baixo
        resultado = executar_query("""
            SELECT COUNT(*) FROM produtos_estoque 
            WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)
        """, fetch_one=True)
        estoque_baixo = resultado['count'] if resultado else 0
        
        # Total de itens em estoque
        resultado = executar_query("SELECT SUM(quantidade_atual) FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True)
        total_itens = resultado['sum'] if resultado else 0
        
        return {
            'total_produtos': total_produtos or 0,
            'estoque_baixo': estoque_baixo or 0,
            'total_itens': float(total_itens) if total_itens else 0
        }
    except Exception as e:
        print(f"Erro ao buscar resumo estoque: {e}")
        return {'total_produtos': 0, 'estoque_baixo': 0, 'total_itens': 0}

def get_resumo_analises():
    """Retorna resumo das análises para o dashboard (apenas ativas)"""
    try:
        # Total de análises no ano (ativas)
        resultado = executar_query("""
            SELECT COUNT(*) FROM analises 
            WHERE EXTRACT(YEAR FROM data_coleta) = EXTRACT(YEAR FROM CURRENT_DATE)
            AND ativo = TRUE
        """, fetch_one=True)
        analises_ano = resultado['count'] if resultado else 0
        
        # Análises pendentes (sem resultado) e ativas
        resultado = executar_query("""
            SELECT COUNT(*) FROM analises 
            WHERE data_resultado IS NULL
            AND ativo = TRUE
        """, fetch_one=True)
        pendentes = resultado['count'] if resultado else 0
        
        # Última análise ativa
        ultima = executar_query("""
            SELECT data_coleta, talhao_id FROM analises 
            WHERE ativo = TRUE
            ORDER BY data_coleta DESC LIMIT 1
        """, fetch_one=True)
        
        return {
            'analises_ano': analises_ano or 0,
            'pendentes': pendentes or 0,
            'ultima_data': ultima['data_coleta'] if ultima else None,
            'ultima_talhao': ultima['talhao_id'] if ultima else None
        }
    except Exception as e:
        print(f"Erro ao buscar resumo análises: {e}")
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
                'id': r['id'],
                'nome': r['nome'],
                'quantidade': float(r['quantidade_atual']) if r['quantidade_atual'] else 0,
                'minimo': float(r['estoque_minimo']) if r['estoque_minimo'] else 0,
                'unidade': r['unidade']
            })
        return produtos
    except Exception as e:
        print(f"Erro ao buscar produtos estoque baixo: {e}")
        return []

def get_ultimas_analises(limite=3):
    """Retorna as últimas análises registradas (apenas ativas)"""
    try:
        query = """
        SELECT a.id, a.data_coleta, t.nome as talhao, tp.nome as tipo,
               CASE WHEN a.data_resultado IS NULL THEN 'Pendente' ELSE 'Concluída' END as status
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
                'id': r['id'],
                'data': r['data_coleta'],
                'talhao': r['talhao'],
                'tipo': r['tipo'],
                'status': r['status']
            })
        return analises
    except Exception as e:
        print(f"Erro ao buscar últimas análises: {e}")
        return []

def get_ultimos_manejos(limite=3):
    """Retorna os últimos manejos do mato registrados"""
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
                'id': r['id'],
                'data': r['data_manejo'],
                'talhao': r['talhao'],
                'tipo': r['tipo_manejo']
            })
        return manejos
    except Exception as e:
        print(f"Erro ao buscar últimos manejos: {e}")
        return []
    
