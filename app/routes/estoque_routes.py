from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.modules import estoque

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')

# =====================================================
# DASHBOARD DO ESTOQUE
# =====================================================

@estoque_bp.route('/')
def dashboard():
    """Página principal do estoque com resumo e alertas."""
    try:
        resumo = estoque.get_resumo_estoque()
        produtos = estoque.listar_produtos(ativos=True)
        # Filtrar apenas produtos com estoque baixo para o alerta
        produtos_baixo = [p for p in produtos if p.get('estoque_baixo')]
        return render_template('estoque/dashboard.html', resumo=resumo, produtos_baixo=produtos_baixo)
    except Exception as e:
        flash('Erro ao carregar o painel de estoque.', 'error')
        return render_template('estoque/dashboard.html', resumo=None, produtos_baixo=[])

# =====================================================
# CRUD DE PRODUTOS
# =====================================================

@estoque_bp.route('/produtos')
def listar_produtos():
    """Lista todos os produtos do estoque."""
    try:
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/produtos/lista.html', produtos=produtos)
    except Exception as e:
        flash('Erro ao carregar a lista de produtos.', 'error')
        return render_template('estoque/produtos/lista.html', produtos=[])

@estoque_bp.route('/produtos/novo', methods=['GET', 'POST'])
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
def detalhe_produto(id):
    """Exibe detalhes de um produto específico."""
    try:
        produto = estoque.buscar_produto_por_id(id)
        if not produto:
            flash('Produto não encontrado.', 'warning')
            return redirect(url_for('estoque.listar_produtos'))
        # Buscar movimentações deste produto
        movimentacoes = estoque.listar_movimentacoes(produto_id=id)
        return render_template('estoque/produtos/detalhe.html', produto=produto, movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar detalhes do produto.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/produtos/<int:id>/editar', methods=['GET', 'POST'])
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