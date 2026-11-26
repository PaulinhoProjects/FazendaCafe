from flask import Blueprint, render_template, flash, redirect, request, url_for
from app.modules import cotacoes
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger

logger = get_logger(__name__)
cotacoes_bp = Blueprint('cotacoes', __name__, url_prefix='/cotacoes')


@cotacoes_bp.route('/')
@login_required
def index():
    try:
        dados = cotacoes.obter_cotacoes()
        historico = cotacoes.listar_historico()
        return render_template('cotacoes/index.html', cotacoes=dados, historico=historico)
    except Exception as e:
        logger.error(f"cotacoes_routes.index: {e}")
        flash('Erro ao carregar as cotações.', 'error')
        return render_template('cotacoes/index.html', cotacoes=None, historico=[])


@cotacoes_bp.route('/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar():
    try:
        cotacoes.limpar_cache()
        dados = cotacoes.obter_cotacoes(force=True)
        if dados and not dados.get('stale'):
            flash('Cotações atualizadas com sucesso.', 'success')
        else:
            flash('Fontes indisponíveis: exibindo o último snapshot salvo.', 'warning')
    except Exception as e:
        logger.error(f"cotacoes_routes.atualizar: {e}")
        flash('Erro ao atualizar as cotações.', 'error')
    return redirect(request.referrer or url_for('cotacoes.index'))
