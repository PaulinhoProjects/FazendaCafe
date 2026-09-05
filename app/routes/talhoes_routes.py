from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.modules import talhoes
from datetime import datetime
from app.modules.login_manager import login_required

talhoes_bp = Blueprint('talhoes', __name__, url_prefix='/talhoes')

@talhoes_bp.route('/')
@login_required
def listar():
    """Lista todos os talhões cadastrados."""
    try:
        lista_talhoes = talhoes.listar_talhoes()
        return render_template('talhoes/lista.html', talhoes=lista_talhoes)
    except Exception as e:
        flash('Erro ao carregar a lista de talhões.', 'error')
        return render_template('talhoes/lista.html', talhoes=[])

@talhoes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    """Cadastra um novo talhão."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': request.form.get('area'),
                'numero_pes': request.form.get('numero_pes'),
                'variedade': request.form.get('variedade'),
                'data_plantio': request.form.get('data_plantio'),
            }
            # Aqui no projeto real as chaves são separadas na função inserir_talhao
            talhoes.inserir_talhao(
                dados['nome'], dados['area'], dados['numero_pes'], 
                dados['variedade'], request.form.get('espacamento_rua'),
                request.form.get('espacamento_planta'), dados['data_plantio'],
                request.form.get('altitude'), request.form.get('observacoes')
            )
            flash('Talhão cadastrado com sucesso!', 'success')
            return redirect(url_for('talhoes.listar'))
        except Exception as e:
            flash(f'Erro ao cadastrar talhão: {e}', 'error')
            return redirect(url_for('talhoes.novo'))

    return render_template('talhoes/novo.html')

@talhoes_bp.route('/<int:id>')
@login_required
def detalhe(id):
    """Exibe detalhes de um talhão específico."""
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
    """Edita um talhão existente."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': request.form.get('area'),
                'numero_pes': request.form.get('numero_pes'),
                'variedade': request.form.get('variedade'),
                'data_plantio': request.form.get('data_plantio'),
                'espacamento_rua': request.form.get('espacamento_rua'),
                'espacamento_planta': request.form.get('espacamento_planta'),
                'altitude': request.form.get('altitude'),
                'observacoes': request.form.get('observacoes')
            }
            talhoes.atualizar_talhao(
                id, dados['nome'], dados['area'], dados['numero_pes'],
                dados['variedade'], dados['espacamento_rua'],
                dados['espacamento_planta'], dados['data_plantio'],
                dados['altitude'], dados['observacoes']
            )
            flash('Talhão atualizado com sucesso!', 'success')
            return redirect(url_for('talhoes.detalhe', id=id))
        except Exception as e:
            flash(f'Erro ao atualizar talhão: {e}', 'error')

    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        return render_template('talhoes/editar.html', talhao=talhao)
    except Exception as e:
        flash('Erro ao carregar formulário de edição.', 'error')
        return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    """Exclui um talhão."""
    try:
        talhoes.excluir_talhao(id)
        flash('Talhão excluído com sucesso!', 'success')
    except Exception as e:
        flash('Erro ao excluir talhão.', 'error')
    return redirect(url_for('talhoes.listar'))
