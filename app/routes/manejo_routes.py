from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules.login_manager import login_required
from app.modules import manejo

manejo_bp = Blueprint('manejo', __name__, url_prefix='/manejo')

@manejo_bp.route('/')
@login_required
def visao_geral():
    """Pagina principal de Manejo do Cafezal."""
    try:
        timeline = manejo.get_timeline_manejo(30)
        resumo = manejo.get_resumo_manejo()
        return render_template('manejo/visao_geral.html', timeline=timeline, resumo=resumo)
    except Exception as e:
        print(f"Erro no manejo: {e}")
        return render_template('manejo/visao_geral.html', timeline=[], resumo={})

@manejo_bp.route('/talhao/<int:id>')
@login_required
def manejo_talhao(id):
    """Manejo de um talhao especifico."""
    try:
        from app.modules import talhoes
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhao nao encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        timeline = manejo.get_manejo_por_talhao(id)
        return render_template('manejo/visao_geral.html', timeline=timeline, resumo=manejo.get_resumo_manejo(), talhao=talhao)
    except Exception as e:
        flash('Erro ao carregar manejo do talhao.', 'error')
        return redirect(url_for('manejo.visao_geral'))