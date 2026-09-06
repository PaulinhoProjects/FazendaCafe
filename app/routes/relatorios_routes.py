from flask import Blueprint, send_file, flash, redirect, url_for, render_template
from app.modules.login_manager import login_required
from app.modules import relatorios

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')

@relatorios_bp.route('/')
@login_required
def index():
    return render_template('relatorios/index.html')

@relatorios_bp.route('/pulverizacoes')
@login_required
def rel_pulverizacoes():
    try:
        pdf = relatorios.gerar_relatorio_pulverizacoes()
        return send_file(
            pdf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_pulverizacoes.pdf'
        )
    except Exception as e:
        flash('Erro ao gerar relatório de pulverizações.', 'error')
        return redirect(url_for('dashboard.index'))

@relatorios_bp.route('/estoque')
@login_required
def rel_estoque():
    try:
        pdf = relatorios.gerar_relatorio_estoque()
        return send_file(
            pdf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_estoque.pdf'
        )
    except Exception as e:
        flash('Erro ao gerar relatório de estoque.', 'error')
        return redirect(url_for('dashboard.index'))

@relatorios_bp.route('/analises')
@login_required
def rel_analises():
    try:
        pdf = relatorios.gerar_relatorio_analises()
        return send_file(
            pdf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_analises.pdf'
        )
    except Exception as e:
        flash('Erro ao gerar relatório de análises.', 'error')
        return redirect(url_for('dashboard.index'))

@relatorios_bp.route('/manejos')
@login_required
def rel_manejos():
    try:
        pdf = relatorios.gerar_relatorio_manejos()
        return send_file(
            pdf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_manejos.pdf'
        )
    except Exception as e:
        flash('Erro ao gerar relatório de manejos.', 'error')
        return redirect(url_for('dashboard.index'))