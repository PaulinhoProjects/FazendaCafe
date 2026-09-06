from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from app.modules import estoque
from app.modules.login_manager import login_required, admin_required
from datetime import datetime
import io
import csv

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')

@estoque_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = estoque.get_resumo_estoque()
        produtos = estoque.listar_produtos(ativos=True)
        produtos_baixo = [p for p in produtos if p.get('estoque_baixo')]
        return render_template('estoque/dashboard.html', resumo=resumo, produtos_baixo=produtos_baixo)
    except Exception as e:
        flash('Erro ao carregar o painel de estoque.', 'error')
        return render_template('estoque/dashboard.html', resumo=None, produtos_baixo=[])

@estoque_bp.route('/produtos')
@login_required
def listar_produtos():
    try:
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/produtos/lista.html', produtos=produtos)
    except Exception as e:
        flash('Erro ao carregar a lista de produtos.', 'error')
        return render_template('estoque/produtos/lista.html', produtos=[])

@estoque_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def novo_produto():
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
                flash('Erro ao cadastrar produto.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('estoque/produtos/novo.html')

@estoque_bp.route('/produtos/<int:id>')
@login_required
def detalhe_produto(id):
    try:
        produto = estoque.buscar_produto_por_id(id)
        if not produto:
            flash('Produto nao encontrado.', 'warning')
            return redirect(url_for('estoque.listar_produtos'))
        movimentacoes = estoque.listar_movimentacoes(produto_id=id)
        return render_template('estoque/produtos/detalhe.html', produto=produto, movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar detalhes.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/produtos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
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
            if estoque.atualizar_produto(id, dados):
                flash('Produto atualizado!', 'success')
                return redirect(url_for('estoque.detalhe_produto', id=id))
            else:
                flash('Erro ao atualizar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    try:
        produto = estoque.buscar_produto_por_id(id)
        if not produto:
            flash('Produto nao encontrado.', 'warning')
            return redirect(url_for('estoque.listar_produtos'))
        return render_template('estoque/produtos/editar.html', produto=produto)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/produtos/<int:id>/excluir', methods=['POST'])
@admin_required
@login_required
def excluir_produto(id):
    try:
        sucesso, mensagem = estoque.excluir_produto(id)
        if sucesso:
            flash(mensagem, 'success')
        else:
            flash(mensagem, 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/movimentacoes')
@login_required
def listar_movimentacoes():
    try:
        movimentacoes = estoque.listar_movimentacoes()
        return render_template('estoque/movimentacoes/lista.html', movimentacoes=movimentacoes)
    except Exception as e:
        flash('Erro ao carregar movimentacoes.', 'error')
        return render_template('estoque/movimentacoes/lista.html', movimentacoes=[])

@estoque_bp.route('/movimentacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_movimentacao():
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': request.form.get('produto_id'),
                'tipo': request.form.get('tipo'),
                'quantidade': request.form.get('quantidade'),
                'unidade': request.form.get('unidade'),
                'valor_unitario': request.form.get('valor_unitario'),
                'data_movimento': request.form.get('data_movimento'),
                'observacoes': request.form.get('observacoes')
            }
            mov_id = estoque.registrar_movimentacao(dados)
            if mov_id:
                flash('Movimentacao registrada!', 'success')
                return redirect(url_for('estoque.listar_movimentacoes'))
            else:
                flash('Erro ao registrar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    try:
        produtos = estoque.listar_produtos(ativos=True)
        from datetime import datetime
        return render_template('estoque/movimentacoes/nova.html', produtos=produtos, hoje=datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/movimentacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_movimentacao(id):
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': request.form.get('produto_id'),
                'tipo': request.form.get('tipo'),
                'quantidade': request.form.get('quantidade'),
                'unidade': request.form.get('unidade'),
                'valor_unitario': request.form.get('valor_unitario'),
                'data_movimento': request.form.get('data_movimento'),
                'observacoes': request.form.get('observacoes')
            }
            if estoque.atualizar_movimentacao(id, dados):
                flash('Movimentacao atualizada!', 'success')
                return redirect(url_for('estoque.listar_movimentacoes'))
            else:
                flash('Erro ao atualizar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    try:
        mov = estoque.buscar_movimentacao_por_id(id)
        if not mov:
            flash('Movimentacao nao encontrada.', 'warning')
            return redirect(url_for('estoque.listar_movimentacoes'))
        produtos = estoque.listar_produtos(ativos=True)
        return render_template('estoque/movimentacoes/editar.html', movimentacao=mov, produtos=produtos)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/movimentacoes/<int:id>')
@login_required
def detalhe_movimentacao(id):
    try:
        mov = estoque.buscar_movimentacao_por_id(id)
        if not mov:
            flash('Movimentacao nao encontrada.', 'warning')
            return redirect(url_for('estoque.listar_movimentacoes'))
        return render_template('estoque/movimentacoes/detalhe.html', movimentacao=mov)
    except Exception as e:
        flash('Erro ao carregar detalhes.', 'error')
        return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/movimentacoes/<int:id>/excluir', methods=['POST'])
@admin_required
@login_required
def excluir_movimentacao(id):
    try:
        sucesso, mensagem = estoque.excluir_movimentacao(id)
        if sucesso:
            flash(mensagem, 'success')
        else:
            flash(mensagem, 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('estoque.listar_movimentacoes'))

@estoque_bp.route('/produtos/exportar-csv')
@login_required
def exportar_csv_produtos():
    """Exporta lista de produtos para CSV."""
    try:
        produtos = estoque.listar_produtos(ativos=True)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Nome', 'Categoria', 'Unidade', 'Quantidade Atual', 'Estoque Minimo', 'Valor Unitario'])
        for p in produtos:
            writer.writerow([
                p.get('id', ''),
                p.get('nome', ''),
                p.get('categoria', ''),
                p.get('unidade', ''),
                p.get('quantidade_atual', 0),
                p.get('estoque_minimo', 0),
                p.get('valor_unitario', 0)
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=estoque_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    except Exception as e:
        flash('Erro ao exportar CSV.', 'error')
        return redirect(url_for('estoque.listar_produtos'))

@estoque_bp.route('/categorias')
@login_required
def listar_categorias():
    try:
        categorias = estoque.listar_categorias()
        return render_template('estoque/categorias/lista.html', categorias=categorias)
    except Exception as e:
        flash('Erro ao carregar categorias.', 'error')
        return render_template('estoque/categorias/lista.html', categorias=[])

@estoque_bp.route('/relatorio')
@login_required
def relatorio():
    try:
        produtos = estoque.listar_produtos(ativos=True)
        resumo = estoque.get_resumo_estoque()
        grafico_categoria = estoque.get_valor_por_categoria()
        grafico_consumo = estoque.get_consumo_ultimos_6_meses()
        grafico_top = estoque.get_top_produtos_consumo(10)
        return render_template('estoque/relatorio.html',
            produtos=produtos, resumo=resumo,
            grafico_categoria=grafico_categoria,
            grafico_consumo=grafico_consumo,
            grafico_top=grafico_top
        )
    except Exception as e:
        flash('Erro ao gerar relatorio.', 'error')
        return redirect(url_for('estoque.dashboard'))