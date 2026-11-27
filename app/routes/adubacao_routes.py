from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules import adubacao
from app.modules.login_manager import login_required, admin_required
from datetime import datetime
from app.models import get_logger

logger = get_logger(__name__)
adubacao_bp = Blueprint('adubacao', __name__, url_prefix='/adubacao')

@adubacao_bp.route('/')
@login_required
def dashboard():
    try:
        resumo = adubacao.resumo_nutricao()
        compras = adubacao.listar_compras(limite=6)
        formulacoes = adubacao.listar_formulacoes(disponiveis=True, limite=8)
        aplicacoes = adubacao.listar_aplicacoes(limite=6)
        recomendacoes = adubacao.listar_recomendacoes()
        return render_template('adubacao/dashboard.html',
                               resumo=resumo,
                               compras=compras,
                               formulacoes=formulacoes,
                               aplicacoes=aplicacoes,
                               recomendacoes=recomendacoes[:5],
                               alertas=adubacao.listar_alertas(),
                               total_recomendacoes=len(recomendacoes),
                               total_adubacoes=resumo.get('aplicacoes_30d', 0))
    except Exception as e:
        logger.error(f"adubacao_routes.dashboard: {e}")
        flash('Erro ao carregar painel.', 'error')
        return render_template('adubacao/dashboard.html',
                               resumo={}, compras=[], formulacoes=[],
                               aplicacoes=[], recomendacoes=[], alertas=[],
                               total_recomendacoes=0, total_adubacoes=0)

@adubacao_bp.route('/recomendacoes')
@login_required
def listar_recomendacoes():
    try:
        recomendacoes = adubacao.listar_recomendacoes()
        return render_template('adubacao/recomendacoes/lista.html', recomendacoes=recomendacoes)
    except Exception as e:
        logger.error(f"adubacao_routes.listar_recomendacoes: {e}")
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
                # Itens recomendados (campos repetiveis no formulario)
                nutrientes = request.form.getlist('nutriente')
                quantidades = request.form.getlist('quantidade')
                unidades = request.form.getlist('unidade')
                fontes = request.form.getlist('fonte')
                observacoes_itens = request.form.getlist('observacoes_item')
                for i, nutriente in enumerate(nutrientes):
                    if not (nutriente or '').strip():
                        continue
                    adubacao.inserir_item_recomendacao({
                        'recomendacao_id': rec_id,
                        'nutriente': nutriente.strip(),
                        'quantidade': quantidades[i] if i < len(quantidades) else None,
                        'unidade': unidades[i] if i < len(unidades) else None,
                        'fonte': fontes[i] if i < len(fontes) else None,
                        'observacoes': observacoes_itens[i] if i < len(observacoes_itens) else None
                    })
                flash('Recomendacao criada com sucesso!', 'success')
                return redirect(url_for('adubacao.detalhe_recomendacao', id=rec_id))
            else:
                flash('Erro ao criar recomendacao.', 'error')
        except Exception as e:
            logger.error(f"adubacao_routes.nova_recomendacao: {e}")
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes, analises
        talhoes_lista = talhoes.listar_talhoes()
        analises_lista = analises.listar_analises()
        return render_template('adubacao/recomendacoes/nova.html',
                               talhoes=talhoes_lista, analises=analises_lista)
    except Exception as e:
        logger.error(f"adubacao_routes.nova_recomendacao: {e}")
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
        logger.error(f"adubacao_routes.detalhe_recomendacao: {e}")
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
        logger.error(f"adubacao_routes.atualizar_status: {e}")
        flash('Erro.', 'error')
    return redirect(url_for('adubacao.detalhe_recomendacao', id=id))

@adubacao_bp.route('/recomendacoes/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_recomendacao(id):
    try:
        sucesso, msg = adubacao.excluir_recomendacao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"adubacao_routes.excluir_recomendacao: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('adubacao.listar_recomendacoes'))

# A adubação antiga (produtos digitados sem compra) foi substituída pelas
# Aplicações da Nutrição, que baixam o saldo da formulação comprada.
@adubacao_bp.route('/adubacoes')
@login_required
def listar_adubacoes():
    return redirect(url_for('adubacao.listar_aplicacoes'))


@adubacao_bp.route('/adubacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_adubacao():
    flash('O registro de adubação agora é feito em Aplicações, a partir da formulação comprada.', 'info')
    return redirect(url_for('adubacao.nova_aplicacao'))


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
        logger.error(f"adubacao_routes.detalhe_adubacao: {e}")
        flash('Erro ao carregar adubacao.', 'error')
        return redirect(url_for('adubacao.listar_adubacoes'))

@adubacao_bp.route('/adubacoes/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_adubacao(id):
    try:
        sucesso, msg = adubacao.excluir_adubacao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"adubacao_routes.excluir_adubacao: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('adubacao.listar_adubacoes'))


# =====================================================
# Nutrição e Correção do Solo
# =====================================================

def _linhas_formulacao():
    """Linhas repetidas do formulário de compra (uma nota, várias formulações)."""
    produtos = request.form.getlist('produto')
    campos = {
        'formulacao': request.form.getlist('formulacao'),
        'marca': request.form.getlist('marca'),
        'tecnologia': request.form.getlist('tecnologia'),
        'categoria_id': request.form.getlist('categoria_id'),
        'quantidade': request.form.getlist('quantidade'),
        'unidade': request.form.getlist('unidade'),
        'peso_saco_kg': request.form.getlist('peso_saco_kg'),
        'valor_unitario': request.form.getlist('valor_unitario'),
        'valor_total': request.form.getlist('valor_total'),
        'lote': request.form.getlist('lote'),
        'validade': request.form.getlist('validade'),
        'observacoes': request.form.getlist('observacoes_item'),
    }
    linhas = []
    for i, produto in enumerate(produtos):
        if not (produto or '').strip():
            continue
        linha = {'produto': produto.strip()}
        for nome, valores in campos.items():
            linha[nome] = valores[i] if i < len(valores) else None
        linhas.append(linha)
    return linhas


def _linhas_talhao():
    """Talhões de uma mesma aplicação, cada um com sua dose."""
    talhoes_ids = request.form.getlist('talhao_id')
    campos = {
        'recomendacao_id': request.form.getlist('recomendacao_id'),
        'quantidade_kg': request.form.getlist('quantidade_kg'),
        'area_ha': request.form.getlist('area_ha'),
        'observacoes': request.form.getlist('observacoes_talhao'),
    }
    linhas = []
    for i, talhao_id in enumerate(talhoes_ids):
        if not (talhao_id or '').strip():
            continue
        linha = {'talhao_id': talhao_id}
        for nome, valores in campos.items():
            linha[nome] = valores[i] if i < len(valores) else None
        linhas.append(linha)
    return linhas


@adubacao_bp.route('/compras')
@login_required
def listar_compras():
    try:
        return render_template('adubacao/compras/lista.html',
                               compras=adubacao.listar_compras())
    except Exception as e:
        logger.error(f"adubacao_routes.listar_compras: {e}")
        flash('Erro ao carregar compras.', 'error')
        return render_template('adubacao/compras/lista.html', compras=[])


@adubacao_bp.route('/compras/nova', methods=['GET', 'POST'])
@login_required
def nova_compra():
    if request.method == 'POST':
        try:
            compra_id, msg = adubacao.inserir_compra({
                'fornecedor': request.form.get('fornecedor'),
                'numero_nota': request.form.get('numero_nota'),
                'data_nota': request.form.get('data_nota'),
                'observacoes': request.form.get('observacoes'),
            }, _linhas_formulacao())
            if compra_id:
                flash(msg, 'success')
                return redirect(url_for('adubacao.detalhe_compra', id=compra_id))
            flash(msg, 'error')
        except Exception as e:
            logger.error(f"adubacao_routes.nova_compra: {e}")
            flash(f'Erro ao registrar compra: {e}', 'error')
    return render_template('adubacao/compras/form.html',
                           compra=None, itens=[],
                           catalogo=adubacao.listar_catalogo())


@adubacao_bp.route('/compras/<int:id>')
@login_required
def detalhe_compra(id):
    compra = adubacao.buscar_compra(id)
    if not compra:
        flash('Nota não encontrada.', 'warning')
        return redirect(url_for('adubacao.listar_compras'))
    return render_template('adubacao/compras/detalhe.html',
                           compra=compra, itens=adubacao.listar_itens_compra(id))


@adubacao_bp.route('/compras/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_compra(id):
    if request.method == 'POST':
        try:
            sucesso, msg = adubacao.atualizar_compra(id, {
                'fornecedor': request.form.get('fornecedor'),
                'numero_nota': request.form.get('numero_nota'),
                'data_nota': request.form.get('data_nota'),
                'observacoes': request.form.get('observacoes'),
            })
            flash(msg, 'success' if sucesso else 'error')
            if sucesso:
                return redirect(url_for('adubacao.detalhe_compra', id=id))
        except Exception as e:
            logger.error(f"adubacao_routes.editar_compra: {e}")
            flash(f'Erro ao atualizar nota: {e}', 'error')
    compra = adubacao.buscar_compra(id)
    if not compra:
        flash('Nota não encontrada.', 'warning')
        return redirect(url_for('adubacao.listar_compras'))
    return render_template('adubacao/compras/form.html', compra=compra,
                           itens=adubacao.listar_itens_compra(id),
                           catalogo=adubacao.listar_catalogo())


@adubacao_bp.route('/compras/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_compra(id):
    try:
        sucesso, msg = adubacao.excluir_compra(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"adubacao_routes.excluir_compra: {e}")
        flash('Erro ao excluir nota.', 'error')
    return redirect(url_for('adubacao.listar_compras'))


@adubacao_bp.route('/formulacoes')
@login_required
def formulacoes():
    try:
        return render_template('adubacao/formulacoes/lista.html',
                               formulacoes=adubacao.listar_formulacoes())
    except Exception as e:
        logger.error(f"adubacao_routes.formulacoes: {e}")
        flash('Erro ao carregar formulações.', 'error')
        return render_template('adubacao/formulacoes/lista.html', formulacoes=[])


@adubacao_bp.route('/formulacoes/<int:id>')
@login_required
def detalhe_formulacao(id):
    formulacao = adubacao.buscar_formulacao(id)
    if not formulacao:
        flash('Formulação não encontrada.', 'warning')
        return redirect(url_for('adubacao.formulacoes'))
    return render_template('adubacao/formulacoes/detalhe.html',
                           formulacao=formulacao,
                           aplicacoes=adubacao.listar_aplicacoes_formulacao(id))


@adubacao_bp.route('/aplicacoes')
@login_required
def listar_aplicacoes():
    try:
        return render_template('adubacao/aplicacoes/lista.html',
                               aplicacoes=adubacao.listar_aplicacoes())
    except Exception as e:
        logger.error(f"adubacao_routes.listar_aplicacoes: {e}")
        flash('Erro ao carregar aplicações.', 'error')
        return render_template('adubacao/aplicacoes/lista.html', aplicacoes=[])


def _dados_aplicacao_form():
    try:
        from app.modules import talhoes
        return {
            'formulacoes': adubacao.listar_formulacoes(disponiveis=True),
            'talhoes': talhoes.listar_talhoes(),
            'recomendacoes': adubacao.listar_recomendacoes(),
            'catalogo': adubacao.listar_catalogo(),
        }
    except Exception as e:
        logger.error(f"adubacao_routes._dados_aplicacao_form: {e}")
        flash('Erro ao carregar o formulário.', 'error')
        return {'formulacoes': [], 'talhoes': [], 'recomendacoes': [],
                'catalogo': adubacao.listar_catalogo()}


@adubacao_bp.route('/aplicacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_aplicacao():
    if request.method == 'POST':
        try:
            aplicacao_id, msg = adubacao.inserir_aplicacao({
                'compra_item_id': request.form.get('compra_item_id'),
                'data_aplicacao': request.form.get('data_aplicacao'),
                'metodo': request.form.get('metodo'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes'),
            }, _linhas_talhao())
            if aplicacao_id:
                flash(msg, 'success')
                return redirect(url_for('adubacao.detalhe_aplicacao', id=aplicacao_id))
            flash(msg, 'error')
        except Exception as e:
            logger.error(f"adubacao_routes.nova_aplicacao: {e}")
            flash(f'Erro ao registrar aplicação: {e}', 'error')
    dados = _dados_aplicacao_form()
    return render_template('adubacao/aplicacoes/form.html', aplicacao=None,
                           talhoes_aplicacao=[], **dados)


@adubacao_bp.route('/aplicacoes/<int:id>')
@login_required
def detalhe_aplicacao(id):
    aplicacao = adubacao.buscar_aplicacao(id)
    if not aplicacao:
        flash('Aplicação não encontrada.', 'warning')
        return redirect(url_for('adubacao.listar_aplicacoes'))
    return render_template('adubacao/aplicacoes/detalhe.html',
                           aplicacao=aplicacao,
                           talhoes=adubacao.listar_talhoes_aplicacao(id))


@adubacao_bp.route('/aplicacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_aplicacao(id):
    if request.method == 'POST':
        try:
            sucesso, msg = adubacao.atualizar_aplicacao(id, {
                'compra_item_id': request.form.get('compra_item_id'),
                'data_aplicacao': request.form.get('data_aplicacao'),
                'metodo': request.form.get('metodo'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes'),
            }, _linhas_talhao())
            flash(msg, 'success' if sucesso else 'error')
            if sucesso:
                return redirect(url_for('adubacao.detalhe_aplicacao', id=id))
        except Exception as e:
            logger.error(f"adubacao_routes.editar_aplicacao: {e}")
            flash(f'Erro ao atualizar aplicação: {e}', 'error')
    aplicacao = adubacao.buscar_aplicacao(id)
    if not aplicacao:
        flash('Aplicação não encontrada.', 'warning')
        return redirect(url_for('adubacao.listar_aplicacoes'))
    dados = _dados_aplicacao_form()
    if not any(f['id'] == aplicacao['compra_item_id'] for f in dados['formulacoes']):
        formulacao = adubacao.buscar_formulacao(aplicacao['compra_item_id'])
        if formulacao:
            dados['formulacoes'].insert(0, formulacao)
    # Na edição, a quantidade desta aplicação volta a contar como disponível
    for f in dados['formulacoes']:
        if f['id'] == aplicacao['compra_item_id']:
            f['saldo_kg'] = float(f['saldo_kg'] or 0) + float(aplicacao['total_kg'] or 0)
    return render_template('adubacao/aplicacoes/form.html', aplicacao=aplicacao,
                           talhoes_aplicacao=adubacao.listar_talhoes_aplicacao(id),
                           **dados)


@adubacao_bp.route('/aplicacoes/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_aplicacao(id):
    try:
        sucesso, msg = adubacao.excluir_aplicacao(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"adubacao_routes.excluir_aplicacao: {e}")
        flash('Erro ao excluir aplicação.', 'error')
    return redirect(url_for('adubacao.listar_aplicacoes'))


@adubacao_bp.route('/catalogo')
@login_required
def catalogo():
    return render_template('adubacao/catalogo.html',
                           catalogo=adubacao.listar_catalogo())