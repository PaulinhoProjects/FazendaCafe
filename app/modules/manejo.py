"""
Modulo de Manejo do Cafezal — AgroCafe
Agrupa todas as atividades de manejo: pulverizacao, adubacao, pragas, mato e analises.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime, timedelta

def get_timeline_manejo(limite=30):
    """Retorna timeline unificada de todas as atividades de manejo."""
    timeline = []

    # Pulverizacoes
    try:
        query = """
        SELECT ap.id, ap.data_aplicacao, 'Pulverizacao' as tipo, t.nome as talhao,
        r.nome as detalhe, ap.responsavel, ap.data_prevista_retorno, ap.status_retorno
        FROM aplicacoes_pulverizacao ap
        JOIN talhoes t ON t.id = ap.talhao_id
        LEFT JOIN receitas r ON r.id = ap.receita_id
        ORDER BY ap.data_aplicacao DESC LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        for r in resultado:
            timeline.append({
                'id': r[0], 'data': r[1], 'tipo': r[2], 'talhao': r[3],
                'detalhe': r[4] or 'Sem receita', 'responsavel': r[5] or 'Nao informado',
                'data_retorno': r[6], 'status_retorno': r[7],
                'icone': 'bi-spray', 'cor': 'primary',
                'url': '/pulverizacao/aplicacoes/' + str(r[0])
            })
    except Exception as e:
        print(f"Erro ao buscar pulverizacoes no manejo: {e}")

    # Adubacoes
    try:
        query = """
        SELECT a.id, a.data_aplicacao, 'Adubacao' as tipo, t.nome as talhao,
        ta.nome as detalhe, a.responsavel, NULL, NULL
        FROM adubacoes a
        JOIN talhoes t ON t.id = a.talhao_id
        LEFT JOIN tipos_adubacao ta ON ta.id = a.tipo_adubacao_id
        ORDER BY a.data_aplicacao DESC LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        for r in resultado:
            timeline.append({
                'id': r[0], 'data': r[1], 'tipo': r[2], 'talhao': r[3],
                'detalhe': r[4] or 'Sem tipo', 'responsavel': r[5] or 'Nao informado',
                'data_retorno': r[6], 'status_retorno': r[7],
                'icone': 'bi-droplet-half', 'cor': 'success',
                'url': '/adubacao/adubacoes/' + str(r[0])
            })
    except Exception as e:
        print(f"Erro ao buscar adubacoes no manejo: {e}")

    # Manejos de Mato
    try:
        query = """
        SELECT m.id, m.data_manejo, 'Manejo de Mato' as tipo, t.nome as talhao,
        m.tipo_manejo as detalhe, m.responsavel, NULL, NULL
        FROM manejos_mato m
        JOIN talhoes t ON t.id = m.talhao_id
        ORDER BY m.data_manejo DESC LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        for r in resultado:
            timeline.append({
                'id': r[0], 'data': r[1], 'tipo': r[2], 'talhao': r[3],
                'detalhe': r[4] or 'Nao informado', 'responsavel': r[5] or 'Nao informado',
                'data_retorno': r[6], 'status_retorno': r[7],
                'icone': 'bi-tree', 'cor': 'info',
                'url': '/manejo-mato/' + str(r[0])
            })
    except Exception as e:
        print(f"Erro ao buscar manejos mato no manejo: {e}")

    # Analises
    try:
        query = """
        SELECT a.id, a.data_coleta, 'Analise' as tipo, t.nome as talhao,
        tp.nome as detalhe, 'Nao informado', NULL,
        CASE WHEN a.data_resultado IS NULL THEN 'Pendente' ELSE 'Concluida' END
        FROM analises a
        JOIN talhoes t ON t.id = a.talhao_id
        JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
        WHERE a.ativo = TRUE
        ORDER BY a.data_coleta DESC LIMIT %s
        """
        resultado = executar_query(query, (limite,), fetch_all=True)
        for r in resultado:
            timeline.append({
                'id': r[0], 'data': r[1], 'tipo': r[2], 'talhao': r[3],
                'detalhe': r[4], 'responsavel': r[5],
                'data_retorno': r[6], 'status_retorno': r[7],
                'icone': 'bi-clipboard-data', 'cor': 'warning',
                'url': '/analises/' + str(r[0])
            })
    except Exception as e:
        print(f"Erro ao buscar analises no manejo: {e}")

    # Ordenar por data decrescente
    timeline.sort(key=lambda x: x['data'] if x['data'] else None, reverse=True)
    return timeline[:limite]

def get_resumo_manejo():
    """Retorna resumo de todas as atividades de manejo."""
    resumo = {}

    # Pulverizacoes no ano
    try:
        resultado = executar_query("""
            SELECT COUNT(*) FROM aplicacoes_pulverizacao
            WHERE EXTRACT(YEAR FROM data_aplicacao) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, fetch_one=True)
        resumo['pulverizacoes_ano'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['pulverizacoes_ano'] = 0

    # Adubacoes no ano
    try:
        resultado = executar_query("""
            SELECT COUNT(*) FROM adubacoes
            WHERE EXTRACT(YEAR FROM data_aplicacao) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, fetch_one=True)
        resumo['adubacoes_ano'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['adubacoes_ano'] = 0

    # Manejos de mato no ano
    try:
        resultado = executar_query("""
            SELECT COUNT(*) FROM manejos_mato
            WHERE EXTRACT(YEAR FROM data_manejo) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, fetch_one=True)
        resumo['manejos_mato_ano'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['manejos_mato_ano'] = 0

    # Analises pendentes
    try:
        resultado = executar_query("""
            SELECT COUNT(*) FROM analises
            WHERE data_resultado IS NULL AND ativo = TRUE
        """, fetch_one=True)
        resumo['analises_pendentes'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['analises_pendentes'] = 0

    # Retornos pendentes/atrasados
    try:
        resultado = executar_query("""
            SELECT COUNT(*) FROM aplicacoes_pulverizacao
            WHERE status_retorno IN ('pendente', 'atrasado')
        """, fetch_one=True)
        resumo['retornos_pendentes'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['retornos_pendentes'] = 0

    # Pragas ativas
    try:
        resultado = executar_query("""
            SELECT COUNT(DISTINCT praga_doenca_id) FROM ocorrencias_pragas
        """, fetch_one=True)
        resumo['pragas_ativas'] = resultado[0] if resultado and resultado[0] else 0
    except Exception:
        resumo['pragas_ativas'] = 0

    return resumo

def get_manejo_por_talhao(talhao_id):
    """Retorna timeline de manejo de um talhao especifico."""
    timeline = get_timeline_manejo(50)
    return [t for t in timeline if t.get('talhao') == talhao_id or t.get('talhao_id') == talhao_id]