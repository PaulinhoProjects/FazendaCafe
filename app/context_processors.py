"""
Context processors do AgroCafé.
Disponibiliza contadores de alertas para todos os templates.
"""
from flask import session
from config.database import executar_query

def alertas_context():
    """Disponibiliza contadores de alertas para a sidebar e topbar."""
    alertas = {
        'count_estoque_baixo': 0,
        'count_retornos_pendentes': 0,
        'count_analises_pendentes': 0,
        'count_total_alertas': 0,
    }

    if 'user_id' not in session:
        return {'alertas_globais': alertas}

    try:
        # Estoque baixo
        resultado = executar_query(
            "SELECT COUNT(*) FROM produtos_estoque WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)",
            fetch_one=True
        )
        alertas['count_estoque_baixo'] = resultado[0] if resultado else 0
    except Exception:
        pass

    try:
        # Retornos pendentes/atrasados
        resultado = executar_query(
            """SELECT COUNT(*) FROM aplicacoes_pulverizacao
               WHERE status_retorno IN ('pendente', 'atrasado')""",
            fetch_one=True
        )
        alertas['count_retornos_pendentes'] = resultado[0] if resultado else 0
    except Exception:
        pass

    try:
        # Análises pendentes
        resultado = executar_query(
            "SELECT COUNT(*) FROM analises WHERE data_resultado IS NULL AND ativo = TRUE",
            fetch_one=True
        )
        alertas['count_analises_pendentes'] = resultado[0] if resultado else 0
    except Exception:
        pass

    alertas['count_total_alertas'] = (
        alertas['count_estoque_baixo'] +
        alertas['count_retornos_pendentes'] +
        alertas['count_analises_pendentes']
    )

    return {'alertas_globais': alertas}
