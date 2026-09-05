from flask import Blueprint, render_template, flash
from app.modules import clima
from app.modules.login_manager import login_required

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
        flash('Erro ao carregar dados do clima.', 'error')
        return render_template('clima/index.html', clima=None, alertas=[])

@clima_bp.route('/previsao')
@login_required
def previsao():
    try:
        previsoes = clima.get_previsao()
        return render_template('clima/previsao.html', previsoes=previsoes or [])
    except Exception as e:
        flash('Erro ao carregar previsao.', 'error')
        return render_template('clima/previsao.html', previsoes=[])