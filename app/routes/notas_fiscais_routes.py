from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules import notas_fiscais
from app.modules.login_manager import login_required
import os

notas_fiscais_bp = Blueprint('notas_fiscais', __name__, url_prefix='/notas-fiscais')

@notas_fiscais_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = notas_fiscais.get_resumo_notas()
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/dashboard.html', resumo=resumo, notas=notas[:10])
    except Exception as e:
        flash('Erro ao carregar painel.', 'error')
        return render_template('notas_fiscais/dashboard.html', resumo=None, notas=[])

@notas_fiscais_bp.route('/lista')
@login_required
def listar():
    try:
        notas = notas_fiscais.listar_notas()
        return render_template('notas_fiscais/lista.html', notas=notas)
    except Exception as e:
        flash('Erro ao carregar notas.', 'error')
        return render_template('notas_fiscais/lista.html', notas=[])

@notas_fiscais_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            dados = {
                'numero_nota': request.form.get('numero_nota'),
                'serie': request.form.get('serie'),
                'data_emissao': request.form.get('data_emissao'),
                'data_recebimento': request.form.get('data_recebimento'),
                'fornecedor': request.form.get('fornecedor'),
                'cnpj_fornecedor': request.form.get('cnpj_fornecedor'),
                'valor_total': request.form.get('valor_total'),
                'observacoes': request.form.get('observacoes')
            }
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename:
                    filename = f"nota_{request.form.get('numero_nota', 'sem_numero')}.pdf"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    arquivo_pdf = filename

            nota_id = notas_fiscais.inserir_nota_fiscal(dados, arquivo_pdf)
            if nota_id:
                flash('Nota fiscal cadastrada!', 'success')
                return redirect(url_for('notas_fiscais.detalhe', id=nota_id))
            else:
                flash('Erro ao cadastrar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('notas_fiscais/nova.html')

@notas_fiscais_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        nota = notas_fiscais.buscar_nota_por_id(id)
        if not nota:
            flash('Nota nao encontrada.', 'warning')
            return redirect(url_for('notas_fiscais.listar'))
        movimentacoes = notas_fiscais.listar_movimentacoes_por_nota(id)
        return render_template('notas_fiscais/detalhe.html', nota=nota, movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar nota.', 'error')
        return redirect(url_for('notas_fiscais.listar'))

@notas_fiscais_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    try:
        sucesso, msg = notas_fiscais.excluir_nota_fiscal(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('notas_fiscais.listar'))