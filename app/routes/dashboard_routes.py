from flask import Blueprint, render_template
from app.modules import dashboard
from app.modules.login_manager import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Página inicial com indicadores e métricas."""
    try:
        from app.modules.dashboard import (
            get_resumo_geral, get_atividades_recentes, get_alertas_retorno,
            get_pragas_por_talhao, get_aplicacoes_por_periodo,
            get_aplicacoes_ultimos_6_meses, get_tipos_pragas,
            get_resumo_estoque, get_resumo_analises, get_resumo_pdfs,
            get_produtos_estoque_baixo, get_ultimas_analises, get_ultimos_manejos
        )
        from app.modules.clima import get_clima_atual, get_previsao
        from datetime import datetime

        # Resumo geral
        resumo = get_resumo_geral()
        atividades = get_atividades_recentes(8)
        alertas = get_alertas_retorno()

        # Gráficos
        grafico_pragas_talhao = get_pragas_por_talhao()
        grafico_aplicacoes_periodo = get_aplicacoes_por_periodo()
        grafico_tendencia = get_aplicacoes_ultimos_6_meses()
        grafico_tipos_pragas = get_tipos_pragas()

        # Resumos
        resumo_estoque = get_resumo_estoque()
        resumo_analises = get_resumo_analises()
        resumo_pdfs = get_resumo_pdfs()

        # Listas
        produtos_baixo = get_produtos_estoque_baixo(5)
        ultimas_analises = get_ultimas_analises(3)
        ultimos_manejos = get_ultimos_manejos(3)

        # Clima
        clima_atual = get_clima_atual()
        previsao = get_previsao()

        return render_template('dashboard.html',
                             resumo=resumo,
                             atividades=atividades,
                             alertas=alertas,
                             grafico_pragas_talhao=grafico_pragas_talhao,
                             grafico_aplicacoes_periodo=grafico_aplicacoes_periodo,
                             grafico_tendencia=grafico_tendencia,
                             grafico_tipos_pragas=grafico_tipos_pragas,
                             resumo_estoque=resumo_estoque,
                             resumo_analises=resumo_analises,
                             resumo_pdfs=resumo_pdfs,
                             produtos_baixo=produtos_baixo,
                             ultimas_analises=ultimas_analises,
                             ultimos_manejos=ultimos_manejos,
                             clima_atual=clima_atual,
                             previsao=previsao,
                             data_atual=datetime.now().strftime('%d/%m/%Y'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template('dashboard.html', resumo=None)