from flask import Blueprint, render_template, flash, redirect, request, url_for
from app.modules import clima
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger

logger = get_logger(__name__)
clima_bp = Blueprint('clima', __name__, url_prefix='/clima')


@clima_bp.route('/')
@login_required
def index():
    try:
        clima_atual = clima.get_clima_atual()
        alertas = []
        if clima_atual:
            alertas = clima.gerar_alertas(clima_atual)
        return render_template('clima/index.html', clima=clima_atual, alertas=alertas)
    except Exception as e:
        logger.error(f"clima_routes.index: {e}")
        flash('Erro ao carregar dados do clima.', 'error')
        return render_template('clima/index.html', clima=None, alertas=[])


@clima_bp.route('/previsao')
@login_required
def previsao():
    try:
        previsoes = clima.get_previsao()
        return render_template('clima/previsao.html', previsoes=previsoes or [])
    except Exception as e:
        logger.error(f"clima_routes.previsao: {e}")
        flash('Erro ao carregar previsao.', 'error')
        return render_template('clima/previsao.html', previsoes=[])


@clima_bp.route('/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar():
    try:
        clima.limpar_cache()
        clima_atual = clima.get_clima_atual(force=True)
        if clima_atual:
            flash('Dados do Climatempo atualizados com sucesso.', 'success')
        else:
            flash('Não foi possível atualizar os dados do Climatempo.', 'error')
    except Exception as e:
        logger.error(f"clima_routes.atualizar: {e}")
        flash('Erro ao atualizar dados do clima.', 'error')
    return redirect(request.referrer or url_for('clima.index'))
