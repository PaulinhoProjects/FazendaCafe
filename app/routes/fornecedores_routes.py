from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules import fornecedores
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger

logger = get_logger(__name__)
fornecedores_bp = Blueprint('fornecedores', __name__, url_prefix='/fornecedores')


@fornecedores_bp.route('/')
@login_required
def listar():
    try:
        return render_template('fornecedores/lista.html',
                               fornecedores=fornecedores.listar_fornecedores(ativos=False))
    except Exception as e:
        logger.error(f"fornecedores_routes.listar: {e}")
        flash('Erro ao carregar fornecedores.', 'error')
        return render_template('fornecedores/lista.html', fornecedores=[])


@fornecedores_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo():
    if request.method == 'POST':
        dados = {
            'nome': request.form.get('nome'),
            'cnpj': request.form.get('cnpj'),
            'telefone': request.form.get('telefone'),
        }
        try:
            fornecedor_id, msg = fornecedores.inserir_fornecedor(dados)
            if fornecedor_id:
                flash(msg, 'success')
                return redirect(url_for('fornecedores.listar'))
            flash(msg, 'error')
        except Exception as e:
            logger.error(f"fornecedores_routes.novo: {e}")
            flash(f'Erro ao cadastrar fornecedor: {e}', 'error')
    return render_template('fornecedores/form.html', fornecedor=None)


@fornecedores_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    if request.method == 'POST':
        dados = {
            'nome': request.form.get('nome'),
            'cnpj': request.form.get('cnpj'),
            'telefone': request.form.get('telefone'),
        }
        try:
            sucesso, msg = fornecedores.atualizar_fornecedor(id, dados)
            flash(msg, 'success' if sucesso else 'error')
            if sucesso:
                return redirect(url_for('fornecedores.listar'))
        except Exception as e:
            logger.error(f"fornecedores_routes.editar: {e}")
            flash(f'Erro ao atualizar fornecedor: {e}', 'error')
    try:
        fornecedor = fornecedores.buscar_fornecedor_por_id(id)
        if not fornecedor:
            flash('Fornecedor não encontrado.', 'warning')
            return redirect(url_for('fornecedores.listar'))
        return render_template('fornecedores/form.html', fornecedor=fornecedor)
    except Exception as e:
        logger.error(f"fornecedores_routes.editar: {e}")
        flash('Erro ao carregar fornecedor.', 'error')
        return redirect(url_for('fornecedores.listar'))


@fornecedores_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    try:
        sucesso, msg = fornecedores.excluir_fornecedor(id)
        flash(msg, 'success' if sucesso else 'error')
    except Exception as e:
        logger.error(f"fornecedores_routes.excluir: {e}")
        flash('Erro ao remover fornecedor.', 'error')
    return redirect(url_for('fornecedores.listar'))
