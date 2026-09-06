from flask import Blueprint, render_template, session, redirect, url_for
from app.modules.login_manager import login_required
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

def get_icone_clima(codigo):
    codigos = {
        '01d': 'bi-sun-fill', '01n': 'bi-moon-stars-fill',
        '02d': 'bi-cloud-sun-fill', '02n': 'bi-cloud-moon-fill',
        '03d': 'bi-cloud-fill', '03n': 'bi-cloud-fill',
        '04d': 'bi-clouds-fill', '04n': 'bi-clouds-fill',
        '09d': 'bi-cloud-rain-heavy-fill', '09n': 'bi-cloud-rain-heavy-fill',
        '10d': 'bi-cloud-rain-fill', '10n': 'bi-cloud-rain-fill',
        '11d': 'bi-cloud-lightning-rain-fill', '11n': 'bi-cloud-lightning-rain-fill',
        '13d': 'bi-snow', '13n': 'bi-snow',
        '50d': 'bi-cloud-fog-fill', '50n': 'bi-cloud-fog-fill',
    }
    return codigos.get(str(codigo), 'bi-cloud-fill')

@dashboard_bp.route('/')
@login_required
def index():
    try:
        from app.modules.dashboard import (
            get_resumo_geral, get_atividades_recentes, get_alertas_retorno,
            get_pragas_por_talhao, get_aplicacoes_por_periodo,
            get_aplicacoes_ultimos_6_meses, get_tipos_pragas,
            get_resumo_estoque, get_resumo_analises, get_resumo_pdfs,
            get_produtos_estoque_baixo, get_ultimas_analises, get_ultimos_manejos
        )

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
        ultimos_manejos = get_ultimos_manejos(3)

        clima_atual = None
        try:
            from app.modules.clima import get_clima_atual
            clima_atual = get_clima_atual()
        except Exception:
            pass

        return render_template('dashboard.html',
            resumo=resumo, alertas=alertas, atividades=atividades,
            grafico_tendencia=grafico_tendencia,
            grafico_aplicacoes_periodo=grafico_aplicacoes_periodo,
            grafico_pragas_talhao=grafico_pragas_talhao,
            grafico_tipos_pragas=grafico_tipos_pragas,
            resumo_estoque=resumo_estoque, resumo_analises=resumo_analises,
            resumo_pdfs=resumo_pdfs, produtos_baixo=produtos_baixo,
            ultimas_analises=ultimas_analises, ultimos_manejos=ultimos_manejos,
            clima_atual=clima_atual,
            data_atual=datetime.now().strftime('%d/%m/%Y'),
            get_icone_clima=get_icone_clima
        )
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        import traceback
        traceback.print_exc()
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
            clima_atual=None,
            data_atual=datetime.now().strftime('%d/%m/%Y'),
            get_icone_clima=get_icone_clima
        )
