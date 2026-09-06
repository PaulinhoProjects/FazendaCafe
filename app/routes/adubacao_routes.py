from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules import adubacao
from app.modules.login_manager import login_required, admin_required
from datetime import datetime

adubacao_bp = Blueprint('adubacao', __name__, url_prefix='/adubacao')

@adubacao_bp.route('/')
@login_required
def dashboard():
    try:
        recomendacoes = adubacao.listar_recomendacoes()
        adubacoes = adubacao.listar_adubacoes(limite=10)
        tipos = adubacao.listar_tipos_adubacao()
        return render_template('adubacao/dashboard.html',
                             recomendacoes=recomendacoes[:5],
                             adubacoes=adubacoes,
                             total_recomendacoes=len(recomendacoes),
                             total_adubacoes=len(adubacoes),
                             tipos=tipos)
    except Exception as e:
        flash('Erro ao carregar painel.', 'error')
        return render_template('adubacao/dashboard.html',
                             recomendacoes=[], adubacoes=[],
                             total_recomendacoes=0, total_adubacoes=0, tipos=[])

@adubacao_bp.route('/recomendacoes')
@login_required
def listar_recomendacoes():
    try:
        recomendacoes = adubacao.listar_recomendacoes()
        return render_template('adubacao/recomendacoes/lista.html', recomendacoes=recomendacoes)
    except Exception as e:
        flash('Erro ao carregar recomendacoes.', 'error')
        return render_template('adubacao/recomendacoes/lista.html', recomendacoes=[])

@adubacao_bp.route('/recomendacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_recomendacao():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'analise_id': request.form.get('analise_id') or None,
                'data_recomendacao': request.form.get('data_recomendacao'),
                'data_validade': request.form.get('data_validade') or None,
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes'),
                'status': 'Pendente'
            }
            rec_id = adubacao.inserir_recomendacao(dados)
            if rec_id:
                flash('Recomendacao criada com sucesso!', 'success')
                return redirect(url_for('adubacao.detalhe_recomendacao', id=rec_id))
            else:
                flash('Erro ao criar recomendacao.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('adubacao/recomendacoes/nova.html', talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('adubacao.listar_recomendacoes'))

@adubacao_bp.route('/recomendacoes/<int:id>')
@login_required
def detalhe_recomendacao(id):
    try:
        rec = adubacao.buscar_recomendacao_por_id(id)
        if not rec:
            flash('Recomendacao nao encontrada.', 'warning')
            return redirect(url_for('adubacao.listar_recomendacoes'))
        itens = adubacao.listar_itens_recomendacao(id)
        return render_template('adubacao/recomendacoes/detalhe.html', rec=rec, itens=itens)
    except Exception as e:
        flash('Erro ao carregar recomendacao.', 'error')
        return redirect(url_for('adubacao.listar_recomendacoes'))

@adubacao_bp.route('/recomendacoes/<int:id>/status', methods=['POST'])
@login_required
def atualizar_status(id):
    try:
        novo_status = request.form.get('status')
        if adubacao.atualizar_status_recomendacao(id, novo_status):
            flash('Status atualizado!', 'success')
        else:
            flash('Erro ao atualizar status.', 'error')
    except Exception as e:
        flash('Erro.', 'error')
    return redirect(url_for('adubacao.detalhe_recomendacao', id=id))

@adubacao_bp.route('/recomendacoes/<int:id>/excluir', methods=['POST'])
@admin_required
@login_required
def excluir_recomendacao(id):
    try:
        sucesso, msg = adubacao.excluir_recomendacao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('adubacao.listar_recomendacoes'))

@adubacao_bp.route('/adubacoes')
@login_required
def listar_adubacoes():
    try:
        adubacoes = adubacao.listar_adubacoes()
        return render_template('adubacao/adubacoes/lista.html', adubacoes=adubacoes)
    except Exception as e:
        flash('Erro ao carregar adubacoes.', 'error')
        return render_template('adubacao/adubacoes/lista.html', adubacoes=[])

@adubacao_bp.route('/adubacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_adubacao():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'recomendacao_id': request.form.get('recomendacao_id') or None,
                'tipo_adubacao_id': request.form.get('tipo_adubacao_id') or None,
                'data_aplicacao': request.form.get('data_aplicacao'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            adub_id = adubacao.inserir_adubacao(dados)
            if adub_id:
                flash('Adubacao registrada com sucesso!', 'success')
                return redirect(url_for('adubacao.detalhe_adubacao', id=adub_id))
            else:
                flash('Erro ao registrar adubacao.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        tipos = adubacao.listar_tipos_adubacao()
        recomendacoes = adubacao.listar_recomendacoes()
        return render_template('adubacao/adubacoes/nova.html',
                             talhoes=talhoes_lista, tipos=tipos, recomendacoes=recomendacoes)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('adubacao.listar_adubacoes'))

@adubacao_bp.route('/adubacoes/<int:id>')
@login_required
def detalhe_adubacao(id):
    try:
        adub = adubacao.buscar_adubacao_por_id(id)
        if not adub:
            flash('Adubacao nao encontrada.', 'warning')
            return redirect(url_for('adubacao.listar_adubacoes'))
        produtos = adubacao.listar_produtos_adubacao(id)
        nutrientes = adubacao.listar_nutrientes_aplicados(id)
        return render_template('adubacao/adubacoes/detalhe.html',
                             adubacao=adub, produtos=produtos, nutrientes=nutrientes)
    except Exception as e:
        flash('Erro ao carregar adubacao.', 'error')
        return redirect(url_for('adubacao.listar_adubacoes'))

@adubacao_bp.route('/adubacoes/<int:id>/excluir', methods=['POST'])
@admin_required
@login_required
def excluir_adubacao(id):
    try:
        sucesso, msg = adubacao.excluir_adubacao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('adubacao.listar_adubacoes'))