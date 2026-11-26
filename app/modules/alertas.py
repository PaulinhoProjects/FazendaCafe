"""
Módulo de Alertas — Kaldi
Junta o que precisa de atenção (retornos atrasados, estoque baixo, fila de campo,
análises sem resultado) para o sino da barra do topo. Só leitura: reaproveita as
consultas já existentes nos outros módulos.
"""
from app.models import get_logger

logger = get_logger(__name__)


def coletar():
    """Lista de alertas: tipo, ícone, cor, título, texto e endpoint de destino."""
    alertas = []

    try:
        from app.modules.dashboard import get_alertas_retorno
        retornos = get_alertas_retorno()
        atrasados = [r for r in retornos if r.get('status') == 'atrasado']
        proximos = [r for r in retornos if r.get('status') == 'proximo']
        if atrasados:
            alertas.append({
                'nivel': 'alto', 'icone': 'bi-exclamation-octagon', 'cor': 'bg-danger-soft',
                'titulo': f"{len(atrasados)} retorno(s) de aplicação atrasado(s)",
                'texto': ', '.join(r['talhao'] for r in atrasados[:3]) + ('…' if len(atrasados) > 3 else ''),
                'destino': ('dashboard.index', '#painel-alertas'),
            })
        if proximos:
            alertas.append({
                'nivel': 'medio', 'icone': 'bi-clock', 'cor': 'bg-warning-soft',
                'titulo': f"{len(proximos)} retorno(s) nos próximos 7 dias",
                'texto': ', '.join(r['talhao'] for r in proximos[:3]) + ('…' if len(proximos) > 3 else ''),
                'destino': ('dashboard.index', '#painel-alertas'),
            })
    except Exception as e:
        logger.error(f"alertas.coletar retornos: {e}")

    try:
        from app.modules.dashboard import get_produtos_estoque_baixo
        baixos = get_produtos_estoque_baixo(50)
        if baixos:
            alertas.append({
                'nivel': 'medio', 'icone': 'bi-box-seam', 'cor': 'bg-danger-soft',
                'titulo': f"{len(baixos)} produto(s) abaixo do estoque mínimo",
                'texto': ', '.join(p['nome'] for p in baixos[:3]) + ('…' if len(baixos) > 3 else ''),
                'destino': ('estoque.dashboard', ''),
            })
    except Exception as e:
        logger.error(f"alertas.coletar estoque: {e}")

    try:
        from app.modules.fila_aplicacao import contar_tarefas, STATUS_PENDENTE
        pendentes = contar_tarefas().get(STATUS_PENDENTE, 0)
        if pendentes:
            alertas.append({
                'nivel': 'info', 'icone': 'bi-list-check', 'cor': 'bg-info-soft',
                'titulo': f"{pendentes} talhão(ões) na fila de aplicação",
                'texto': 'Tarefas aguardando a aplicação no campo.',
                'destino': ('pulverizacao.fila_aplicacao', ''),
            })
    except Exception as e:
        logger.error(f"alertas.coletar fila: {e}")

    try:
        from app.modules.dashboard import get_resumo_analises
        pend = get_resumo_analises().get('pendentes', 0)
        if pend:
            alertas.append({
                'nivel': 'info', 'icone': 'bi-clipboard-data', 'cor': 'bg-primary-soft',
                'titulo': f"{pend} análise(s) aguardando resultado",
                'texto': 'Coletas enviadas ao laboratório sem laudo lançado.',
                'destino': ('analises.listar', ''),
            })
    except Exception as e:
        logger.error(f"alertas.coletar analises: {e}")

    return alertas
