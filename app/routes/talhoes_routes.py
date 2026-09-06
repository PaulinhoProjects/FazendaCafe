from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.modules import talhoes
from datetime import datetime
from app.modules.login_manager import login_required

talhoes_bp = Blueprint('talhoes', __name__, url_prefix='/talhoes')

def limpar_vazio(valor):
    """Converte string vazia em None para campos numericos."""
    if valor is None or valor == '':
        return None
    return valor

@talhoes_bp.route('/')
@login_required
def listar():
    try:
        lista_talhoes = talhoes.listar_talhoes()
        return render_template('talhoes/lista.html', talhoes=lista_talhoes)
    except Exception as e:
        flash('Erro ao carregar a lista de talhões.', 'error')
        return render_template('talhoes/lista.html', talhoes=[])

@talhoes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': limpar_vazio(request.form.get('area')),
                'variedade': request.form.get('variedade') or '',
                'data_plantio': limpar_vazio(request.form.get('data_plantio')),
                'altitude': limpar_vazio(request.form.get('altitude')),
                'espacamento': limpar_vazio(request.form.get('espacamento')) or 
                    f"{request.form.get('espacamento_rua') or ''} x {request.form.get('espacamento_planta') or ''}".strip()
                    if request.form.get('espacamento_rua') or request.form.get('espacamento_planta') else None,
                'observacoes': request.form.get('observacoes') or ''
            }
            talhoes.inserir_talhao(dados)
            flash('Talhão cadastrado com sucesso!', 'success')
            return redirect(url_for('talhoes.listar'))
        except Exception as e:
            flash(f'Erro ao cadastrar talhão: {e}', 'error')
            return redirect(url_for('talhoes.novo'))
    return render_template('talhoes/novo.html')

@talhoes_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhão não encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        return render_template('talhoes/detalhe.html', talhao=talhao, datetime=datetime)
    except Exception as e:
        flash('Erro ao carregar detalhes do talhão.', 'error')
        return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': limpar_vazio(request.form.get('area')),
                'variedade': request.form.get('variedade') or '',
                'data_plantio': limpar_vazio(request.form.get('data_plantio')),
                'altitude': limpar_vazio(request.form.get('altitude')),
                'espacamento': limpar_vazio(request.form.get('espacamento')) or 
                    f"{request.form.get('espacamento_rua') or ''} x {request.form.get('espacamento_planta') or ''}".strip()
                    if request.form.get('espacamento_rua') or request.form.get('espacamento_planta') else None,
                'observacoes': request.form.get('observacoes') or ''
            }
            talhoes.atualizar_talhao(id, dados)
            flash('Talhão atualizado com sucesso!', 'success')
            return redirect(url_for('talhoes.detalhe', id=id))
        except Exception as e:
            flash(f'Erro ao atualizar talhão: {e}', 'error')
    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhão não encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        return render_template('talhoes/editar.html', talhao=talhao)
    except Exception as e:
        flash('Erro ao carregar formulário de edição.', 'error')
        return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    try:
        talhoes.excluir_talhao(id)
        flash('Talhão excluído com sucesso!', 'success')
    except Exception as e:
        flash('Erro ao excluir talhão.', 'error')
    return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/pdf')
@login_required
def gerar_pdf():
    try:
        lista_talhoes = talhoes.listar_talhoes()
        pdf_buffer = talhoes.gerar_pdf_talhoes(lista_talhoes)
        return send_file(pdf_buffer, mimetype='application/pdf',
                        as_attachment=True, download_name='talhoes.pdf')
    except Exception as e:
        flash('Erro ao gerar PDF.', 'error')
        return redirect(url_for('talhoes.listar'))