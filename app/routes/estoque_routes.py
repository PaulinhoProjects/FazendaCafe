from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.modules import estoque
from app.modules.login_manager import login_required
from datetime import date

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')

# =====================================================
# DASHBOARD DO ESTOQUE
# =====================================================

@estoque_bp.route('/')
@login_required
def dashboard():
    """Página principal do estoque com resumo e alertas."""
    try:
        resumo = estoque.get_resumo_estoque()
        produtos = estoque.listar_produtos(ativos=True)
        produtos_baixo = [p for p in produtos if p.get('estoque_baixo')]
        return render_template('estoque/dashboard.html', resumo=resumo, produtos_baixo=produtos_baixo)
    except Exception as e:
        flash('Erro ao carregar o painel de estoque.', 'error')
        return render_template('estoque/dashboard.html', resumo=None, produtos_baixo=[])

# =====================================================
# CRUD DE PRODUTOS
# =====================================================

@estoque_bp.route('/produtos')
@login_required
def listar_produtos():
    """Lista todos os produtos do estoque."""
    try:
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/produtos/lista.html', produtos=produtos)
    except Exception as e:
        flash('Erro ao carregar a lista de produtos.', 'error')
        return render_template('estoque/produtos/lista.html', produtos=[])

@estoque_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def novo_produto():
    """Cadastra um novo produto no estoque."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'categoria': request.form.get('categoria'),
                'unidade': request.form.get('unidade'),
                'estoque_minimo': request.form.get('estoque_minimo') or 0,
                'quantidade_atual': request.form.get('quantidade_atual') or 0,
                'observacoes': request.form.get('observacoes')
            }
            produto_id = estoque.inserir_produto(dados)
            if produto_id:
                flash('Produto cadastrado com sucesso!', 'success')
                return redirect(url_for('estoque.listar_produtos'))
            else:
                flash('Erro ao cadastrar produto. Verifique os dados.', 'error')
                return redirect(url_for('estoque.novo_produto'))
        except Exception as e:
            flash(f'Erro ao cadastrar produto: {e}', 'error')
            return redirect(url_for('estoque.novo_produto'))

    return render_template('estoque/produtos/novo.html')

@estoque_bp.route('/produtos/<int:id>')
@login_required
def detalhe_produto(id):
    """Exibe detalhes de um produto específico."""
    try:
        produto = estoque.buscar_produto_por_id(id)
        if not produto:
            flash('Produto não encontrado.', 'warning')
            return redirect(url_for('estoque.listar_produtos'))
        movimentacoes = estoque.listar_movimentacoes(produto_id=id)
        return render_template('estoque/produtos/detalhe.html', produto=produto, movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar detalhes do produto.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/produtos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
    """Edita um produto existente."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'categoria': request.form.get('categoria'),
                'unidade': request.form.get('unidade'),
                'estoque_minimo': request.form.get('estoque_minimo') or 0,
                'quantidade_atual': request.form.get('quantidade_atual') or 0,
                'observacoes': request.form.get('observacoes')
            }
            sucesso = estoque.atualizar_produto(id, dados)
            if sucesso:
                flash('Produto atualizado com sucesso!', 'success')
                return redirect(url_for('estoque.detalhe_produto', id=id))
            else:
                flash('Erro ao atualizar produto.', 'error')
        except Exception as e:
            flash(f'Erro ao atualizar produto: {e}', 'error')

    try:
        produto = estoque.buscar_produto_por_id(id)
        if not produto:
            flash('Produto não encontrado.', 'warning')
            return redirect(url_for('estoque.listar_produtos'))
        return render_template('estoque/produtos/editar.html', produto=produto)
    except Exception as e:
        flash('Erro ao carregar formulário de edição.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/produtos/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_produto(id):
    """Exclui um produto (exclusão lógica)."""
    try:
        sucesso, mensagem = estoque.excluir_produto(id)
        if sucesso:
            flash(mensagem, 'success')
        else:
            flash(mensagem, 'warning')
    except Exception as e:
        flash('Erro ao excluir produto.', 'error')
    return redirect(url_for('estoque.listar_produtos'))

# =====================================================
# MOVIMENTAÇÕES DE ESTOQUE (ENTRADA / SAÍDA)
# =====================================================

@estoque_bp.route('/movimentacoes')
@login_required
def listar_movimentacoes():
    """Lista todas as movimentações de estoque."""
    try:
        movimentacoes = estoque.listar_movimentacoes()
        return render_template('estoque/movimentacoes/lista.html', movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar movimentações.', 'error')
        return render_template('estoque/movimentacoes/lista.html', movimentacoes=[])

@estoque_bp.route('/movimentacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_movimentacao():
    """Registra uma nova movimentação (entrada ou saída)."""
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': request.form.get('produto_id'),
                'tipo': request.form.get('tipo'),
                'quantidade': request.form.get('quantidade'),
                'unidade': request.form.get('unidade'),
                'data_movimento': request.form.get('data_movimento'),
                'valor_unitario': request.form.get('valor_unitario') or None,
                'observacoes': request.form.get('observacoes')
            }
            mov_id = estoque.registrar_movimentacao(dados)
            if mov_id:
                flash('Movimentação registrada com sucesso!', 'success')
                return redirect(url_for('estoque.listar_movimentacoes'))
            else:
                flash('Erro ao registrar movimentação.', 'error')
                return redirect(url_for('estoque.nova_movimentacao'))
        except Exception as e:
            flash(f'Erro ao registrar movimentação: {e}', 'error')
            return redirect(url_for('estoque.nova_movimentacao'))

    try:
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/movimentacoes/nova.html', produtos=produtos, hoje=date.today().strftime('%Y-%m-%d'))
    except Exception as e:
        flash('Erro ao carregar formulário.', 'error')
        return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/movimentacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_movimentacao(id):
    """Edita uma movimentação existente."""
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': request.form.get('produto_id'),
                'tipo': request.form.get('tipo'),
                'quantidade': request.form.get('quantidade'),
                'unidade': request.form.get('unidade'),
                'data_movimento': request.form.get('data_movimento'),
                'valor_unitario': request.form.get('valor_unitario') or None,
                'observacoes': request.form.get('observacoes')
            }
            sucesso = estoque.atualizar_movimentacao(id, dados)
            if sucesso:
                flash('Movimentação atualizada com sucesso!', 'success')
            else:
                flash('Erro ao atualizar movimentação.', 'error')
            return redirect(url_for('estoque.listar_movimentacoes'))
        except Exception as e:
            flash(f'Erro ao atualizar movimentação: {e}', 'error')
            return redirect(url_for('estoque.editar_movimentacao', id=id))

    try:
        movimentacao = estoque.buscar_movimentacao_por_id(id)
        if not movimentacao:
            flash('Movimentação não encontrada.', 'warning')
            return redirect(url_for('estoque.listar_movimentacoes'))
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/movimentacoes/editar.html', movimentacao=movimentacao, produtos=produtos)
    except Exception as e:
        flash('Erro ao carregar formulário de edição.', 'error')
        return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/movimentacoes/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_movimentacao(id):
    """Exclui uma movimentação e reverte o saldo do produto."""
    try:
        sucesso, mensagem = estoque.excluir_movimentacao(id)
        if sucesso:
            flash(mensagem, 'success')
        else:
            flash(mensagem, 'warning')
    except Exception as e:
        flash('Erro ao excluir movimentação.', 'error')
    return redirect(url_for('estoque.listar_movimentacoes'))