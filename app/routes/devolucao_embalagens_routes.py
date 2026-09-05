from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.modules import devolucao_embalagens
from app.modules.login_manager import login_required
import os

devolucao_bp = Blueprint('devolucao', __name__, url_prefix='/devolucoes')

@devolucao_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = devolucao_embalagens.get_resumo_devolucoes()
        devolucoes = devolucao_embalagens.listar_devolucoes()
        return render_template('devolucao/dashboard.html', resumo=resumo, devolucoes=devolucoes[:10])
    except Exception as e:
        flash('Erro ao carregar painel.', 'error')
        return render_template('devolucao/dashboard.html', resumo=None, devolucoes=[])

@devolucao_bp.route('/lista')
@login_required
def listar():
    try:
        devolucoes = devolucao_embalagens.listar_devolucoes()
        return render_template('devolucao/lista.html', devolucoes=devolucoes)
    except Exception as e:
        flash('Erro ao carregar devolucoes.', 'error')
        return render_template('devolucao/lista.html', devolucoes=[])

@devolucao_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            dados = {
                'data_devolucao': request.form.get('data_devolucao'),
                'local_devolucao': request.form.get('local_devolucao'),
                'quantidade_embalagens': request.form.get('quantidade_embalagens'),
                'nome_responsavel': request.form.get('nome_responsavel'),
                'numero_comprovante': request.form.get('numero_comprovante'),
                'observacoes': request.form.get('observacoes')
            }
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename:
                    filename = f"devolucao_{request.form.get('data_devolucao', 'sem_data')}.pdf"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    arquivo_pdf = filename

            dev_id = devolucao_embalagens.inserir_devolucao(dados, arquivo_pdf)
            if dev_id:
                flash('Devolucao registrada!', 'success')
                return redirect(url_for('devolucao.listar'))
            else:
                flash('Erro ao registrar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('devolucao/nova.html')

@devolucao_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        dev = devolucao_embalagens.buscar_devolucao_por_id(id)
        if not dev:
            flash('Devolucao nao encontrada.', 'warning')
            return redirect(url_for('devolucao.listar'))
        return render_template('devolucao/detalhe.html', devolucao=dev)
    except Exception as e:
        flash('Erro ao carregar devolucao.', 'error')
        return redirect(url_for('devolucao.listar'))

@devolucao_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    try:
        sucesso, msg = devolucao_embalagens.excluir_devolucao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('devolucao.listar'))