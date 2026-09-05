from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.modules import pulverizacao
from app.modules.login_manager import login_required
from datetime import datetime

pulverizacao_bp = Blueprint('pulverizacao', __name__, url_prefix='/pulverizacao')

# =====================================================
# DASHBOARD
# =====================================================

@pulverizacao_bp.route('/')
@login_required
def dashboard():
    try:
        aplicacoes = pulverizacao.listar_aplicacoes()
        receitas = pulverizacao.listar_receitas()
        periodos = pulverizacao.listar_periodos()
        return render_template('pulverizacao/dashboard.html',
                             aplicacoes=aplicacoes[:10],
                             total_aplicacoes=len(aplicacoes),
                             total_receitas=len(receitas),
                             periodos=periodos)
    except Exception as e:
        flash('Erro ao carregar painel de pulverizacao.', 'error')
        return render_template('pulverizacao/dashboard.html',
                             aplicacoes=[], total_aplicacoes=0,
                             total_receitas=0, periodos=[])

# =====================================================
# APLICACOES
# =====================================================

@pulverizacao_bp.route('/aplicacoes')
@login_required
def listar_aplicacoes():
    try:
        aplicacoes = pulverizacao.listar_aplicacoes()
        return render_template('pulverizacao/aplicacoes/lista.html', aplicacoes=aplicacoes)
    except Exception as e:
        flash('Erro ao carregar aplicacoes.', 'error')
        return render_template('pulverizacao/aplicacoes/lista.html', aplicacoes=[])

@pulverizacao_bp.route('/aplicacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_aplicacao():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'periodo_id': request.form.get('periodo_id'),
                'receita_id': request.form.get('receita_id') or None,
                'data_aplicacao': request.form.get('data_aplicacao'),
                'data_retorno': request.form.get('data_retorno') or None,
                'responsavel': request.form.get('responsavel'),
                'condicoes': request.form.get('condicoes'),
                'observacoes': request.form.get('observacoes'),
                'tipo_aplicacao': request.form.get('tipo_aplicacao', 'Foliar')
            }
            app_id = pulverizacao.inserir_aplicacao(dados)
            if app_id:
                flash('Aplicacao registrada com sucesso!', 'success')
                return redirect(url_for('pulverizacao.detalhe_aplicacao', id=app_id))
            else:
                flash('Erro ao registrar aplicacao.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        periodos = pulverizacao.listar_periodos()
        receitas = pulverizacao.listar_receitas()
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('pulverizacao/aplicacoes/nova.html',
                             periodos=periodos, receitas=receitas, talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/aplicacoes/<int:id>')
@login_required
def detalhe_aplicacao(id):
    try:
        app = pulverizacao.buscar_aplicacao_por_id(id)
        if not app:
            flash('Aplicacao nao encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_aplicacoes'))
        ocorrencias = pulverizacao.listar_ocorrencias_por_aplicacao(id)
        pragas = pulverizacao.listar_pragas_doencas()
        return render_template('pulverizacao/aplicacoes/detalhe.html',
                             aplicacao=app, ocorrencias=ocorrencias, pragas=pragas)
    except Exception as e:
        flash('Erro ao carregar aplicacao.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/aplicacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_aplicacao(id):
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'periodo_id': request.form.get('periodo_id'),
                'receita_id': request.form.get('receita_id') or None,
                'data_aplicacao': request.form.get('data_aplicacao'),
                'data_prevista_retorno': request.form.get('data_retorno') or None,
                'responsavel': request.form.get('responsavel'),
                'condicoes': request.form.get('condicoes'),
                'observacoes': request.form.get('observacoes'),
                'tipo_aplicacao': request.form.get('tipo_aplicacao', 'Foliar')
            }
            if pulverizacao.atualizar_aplicacao(id, dados):
                flash('Aplicacao atualizada com sucesso!', 'success')
                return redirect(url_for('pulverizacao.detalhe_aplicacao', id=id))
            else:
                flash('Erro ao atualizar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        app = pulverizacao.buscar_aplicacao_por_id(id)
        if not app:
            flash('Aplicacao nao encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_aplicacoes'))
        periodos = pulverizacao.listar_periodos()
        receitas = pulverizacao.listar_receitas()
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('pulverizacao/aplicacoes/editar.html',
                             aplicacao=app, periodos=periodos,
                             receitas=receitas, talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/aplicacoes/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_aplicacao(id):
    try:
        sucesso, msg = pulverizacao.excluir_aplicacao(id)
        if sucesso:
            flash(msg, 'success')
        else:
            flash(msg, 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('pulverizacao.listar_aplicacoes'))

# =====================================================
# RETORNO (CONTROLE DE CARENCIA)
# =====================================================

@pulverizacao_bp.route('/aplicacoes/<int:id>/retorno', methods=['GET', 'POST'])
@login_required
def retorno_aplicacao(id):
    if request.method == 'POST':
        try:
            dados = {
                'status_retorno': request.form.get('status_retorno'),
                'observacoes_retorno': request.form.get('observacoes_retorno'),
                'data_retorno_realizado': request.form.get('data_retorno_realizado') or datetime.now().strftime('%Y-%m-%d')
            }
            if pulverizacao.atualizar_retorno(id, dados):
                flash('Retorno atualizado com sucesso!', 'success')
            else:
                flash('Erro ao atualizar retorno.', 'error')
            return redirect(url_for('pulverizacao.detalhe_aplicacao', id=id))
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        app = pulverizacao.buscar_aplicacao_por_id(id)
        if not app:
            flash('Aplicacao nao encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_aplicacoes'))
        retorno = pulverizacao.buscar_retorno_por_aplicacao(id)
        return render_template('pulverizacao/aplicacoes/retorno.html',
                             aplicacao=app, retorno=retorno)
    except Exception as e:
        flash('Erro ao carregar retorno.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

# =====================================================
# RECEITAS
# =====================================================

@pulverizacao_bp.route('/receitas')
@login_required
def listar_receitas():
    try:
        receitas = pulverizacao.listar_receitas()
        return render_template('pulverizacao/receitas/lista.html', receitas=receitas)
    except Exception as e:
        flash('Erro ao carregar receitas.', 'error')
        return render_template('pulverizacao/receitas/lista.html', receitas=[])

@pulverizacao_bp.route('/receitas/nova', methods=['GET', 'POST'])
@login_required
def nova_receita():
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'periodo_id': request.form.get('periodo_id'),
                'descricao': request.form.get('descricao'),
                'formula': request.form.get('formula'),
                'produtos': request.form.get('produtos'),
                'observacoes': request.form.get('observacoes')
            }
            receita_id = pulverizacao.inserir_receita(dados)
            if receita_id:
                flash('Receita cadastrada com sucesso!', 'success')
                return redirect(url_for('pulverizacao.listar_receitas'))
            else:
                flash('Erro ao cadastrar receita.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        periodos = pulverizacao.listar_periodos()
        return render_template('pulverizacao/receitas/nova.html', periodos=periodos)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))

@pulverizacao_bp.route('/receitas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_receita(id):
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'periodo_id': request.form.get('periodo_id'),
                'descricao': request.form.get('descricao'),
                'formula': request.form.get('formula'),
                'produtos': request.form.get('produtos'),
                'observacoes': request.form.get('observacoes')
            }
            if pulverizacao.atualizar_receita(id, dados):
                flash('Receita atualizada com sucesso!', 'success')
                return redirect(url_for('pulverizacao.listar_receitas'))
            else:
                flash('Erro ao atualizar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        receita = pulverizacao.buscar_receita_por_id(id)
        if not receita:
            flash('Receita nao encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_receitas'))
        periodos = pulverizacao.listar_periodos()
        return render_template('pulverizacao/receitas/editar.html',
                             receita=receita, periodos=periodos)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))

@pulverizacao_bp.route('/receitas/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_receita(id):
    try:
        sucesso, msg = pulverizacao.excluir_receita(id)
        if sucesso:
            flash(msg, 'success')
        else:
            flash(msg, 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('pulverizacao.listar_receitas'))

# =====================================================
# OCORRENCIAS DE PRAGAS
# =====================================================

@pulverizacao_bp.route('/ocorrencias/nova', methods=['GET', 'POST'])
@login_required
def nova_ocorrencia():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'praga_id': request.form.get('praga_id'),
                'aplicacao_id': request.form.get('aplicacao_id') or None,
                'data_deteccao': request.form.get('data_deteccao'),
                'nivel': request.form.get('nivel'),
                'tratado': request.form.get('tratado') == 'on',
                'observacoes': request.form.get('observacoes')
            }
            occ_id = pulverizacao.registrar_ocorrencia(dados)
            if occ_id:
                flash('Ocorrencia registrada com sucesso!', 'success')
                return redirect(url_for('pulverizacao.listar_aplicacoes'))
            else:
                flash('Erro ao registrar ocorrencia.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        pragas = pulverizacao.listar_pragas_doencas()
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('pulverizacao/ocorrencias/nova.html',
                             pragas=pragas, talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))