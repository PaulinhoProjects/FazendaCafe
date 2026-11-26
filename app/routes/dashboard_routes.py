from flask import Blueprint, render_template, session, redirect, url_for
from app.modules.login_manager import login_required
from app.modules.clima import get_icone_clima
from app.models import get_logger
from datetime import datetime

logger = get_logger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    try:
        from app.modules.dashboard import (
            get_resumo_geral, get_atividades_recentes, get_alertas_retorno,
            get_pragas_por_talhao, get_aplicacoes_por_periodo,
            get_aplicacoes_ultimos_6_meses, get_tipos_pragas,
            get_resumo_estoque, get_resumo_analises, get_resumo_pdfs,
            get_produtos_estoque_baixo, get_ultimas_analises
        )
        from app.modules import manejo
        ultimos_manejos = manejo.get_timeline_manejo(5)

        resumo = get_resumo_geral()
        alertas = get_alertas_retorno()
        atividades = get_atividades_recentes(5)
        grafico_tendencia = get_aplicacoes_ultimos_6_meses()
        grafico_aplicacoes_periodo = get_aplicacoes_por_periodo()
        grafico_pragas_talhao = get_pragas_por_talhao()
        grafico_tipos_pragas = get_tipos_pragas()
        resumo_estoque = get_resumo_estoque()
        resumo_analises = get_resumo_analises()
        resumo_pdfs = get_resumo_pdfs()
        produtos_baixo = get_produtos_estoque_baixo(5)
        ultimas_analises = get_ultimas_analises(3)

        clima_atual = None
        try:
            from app.modules.clima import get_clima_atual
            clima_atual = get_clima_atual()
        except Exception:
            pass

        cotacoes_atuais = None
        try:
            from app.modules.cotacoes import obter_cotacoes
            cotacoes_atuais = obter_cotacoes()
        except Exception as e:
            logger.error(f"dashboard_routes.index cotacoes: {e}")

        return render_template('dashboard.html',
            resumo=resumo, alertas=alertas, atividades=atividades,
            grafico_tendencia=grafico_tendencia,
            grafico_aplicacoes_periodo=grafico_aplicacoes_periodo,
            grafico_pragas_talhao=grafico_pragas_talhao,
            grafico_tipos_pragas=grafico_tipos_pragas,
            resumo_estoque=resumo_estoque, resumo_analises=resumo_analises,
            resumo_pdfs=resumo_pdfs, produtos_baixo=produtos_baixo,
            ultimas_analises=ultimas_analises,
            ultimos_manejos=ultimos_manejos,
            clima_atual=clima_atual,
            cotacoes_atuais=cotacoes_atuais,
            data_atual=datetime.now().strftime('%d/%m/%Y'),
            get_icone_clima=get_icone_clima
        )
    except Exception as e:
        logger.error(f"dashboard_routes.index: {e}")
        return render_template('dashboard.html',
            resumo=None, alertas=[], atividades=[],
            grafico_tendencia={'labels': [], 'dados': []},
            grafico_aplicacoes_periodo={'labels': [], 'dados': []},
            grafico_pragas_talhao={'labels': [], 'dados': []},
            grafico_tipos_pragas={'labels': [], 'dados': []},
            resumo_estoque={'total_produtos': 0, 'estoque_baixo': 0, 'total_itens': 0},
            resumo_analises={'analises_ano': 0, 'pendentes': 0},
            resumo_pdfs={'total_pdfs': 0, 'pdfs_mes': 0},
            produtos_baixo=[], ultimas_analises=[], ultimos_manejos=[],
            clima_atual=None, cotacoes_atuais=None,
            data_atual=datetime.now().strftime('%d/%m/%Y'),
            get_icone_clima=get_icone_clima
        )


@dashboard_bp.route('/busca')
@login_required
def busca():
    """Busca global: talhões, produtos, receitas e notas fiscais."""
    from flask import request
    from app.modules import busca as busca_modulo
    termo = (request.args.get('q') or request.args.get('busca') or '').strip()
    grupos = busca_modulo.buscar(termo) if termo else []
    destinos = {
        'talhoes': 'talhoes.detalhe',
        'produtos': 'estoque.detalhe_produto',
        'receitas': 'pulverizacao.detalhe_receita',
        'notas': 'notas_fiscais.detalhe',
    }
    for grupo in grupos:
        for item in grupo['itens']:
            try:
                item['url'] = url_for(destinos[grupo['chave']], id=item['id'])
            except Exception as e:
                logger.error(f"dashboard_routes.busca url ({grupo['chave']}): {e}")
                item['url'] = '#'
    total = sum(len(g['itens']) for g in grupos)
    return render_template('busca.html', termo=termo, grupos=grupos, total=total)


@dashboard_bp.route('/api/alertas')
@login_required
def api_alertas():
    """Alertas do sino da barra do topo (JSON)."""
    from flask import jsonify
    from app.modules import alertas as alertas_modulo
    itens = []
    for a in alertas_modulo.coletar():
        endpoint, ancora = a.pop('destino')
        try:
            a['url'] = url_for(endpoint) + ancora
        except Exception:
            a['url'] = url_for('dashboard.index')
        itens.append(a)
    resposta = jsonify({'total': len(itens), 'itens': itens})
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta
