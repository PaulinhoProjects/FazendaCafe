from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.modules import maquinario
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger

logger = get_logger(__name__)
maquinario_bp = Blueprint('maquinario', __name__, url_prefix='/maquinario')


def _dados(*campos):
    return {campo: request.form.get(campo) for campo in campos}


def _flash(msg, sucesso):
    flash(msg, 'success' if sucesso else 'error')


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------
@maquinario_bp.route('/')
@login_required
def dashboard():
    try:
        return render_template(
            'maquinario/dashboard.html',
            estoque=maquinario.resumo_estoque(),
            maquinas=maquinario.listar_maquinas(),
            manutencoes=maquinario.resumo_manutencoes(),
            combustivel=maquinario.resumo_combustivel(),
            gastos=maquinario.resumo_gastos(),
            alertas=maquinario.listar_alertas(),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.dashboard: {e}")
        flash('Erro ao carregar o painel de maquinário.', 'error')
        return render_template('maquinario/dashboard.html', alertas=[])


# ---------------------------------------------------------------------------
# Estoque isolado
# ---------------------------------------------------------------------------
@maquinario_bp.route('/estoque')
@login_required
def estoque():
    try:
        return render_template(
            'maquinario/estoque.html',
            produtos=maquinario.listar_produtos(),
            resumo=maquinario.resumo_estoque(),
            categorias=maquinario.CATEGORIAS_ESTOQUE,
        )
    except Exception as e:
        logger.error(f"maquinario_routes.estoque: {e}")
        flash('Erro ao carregar o estoque de maquinário.', 'error')
        return render_template('maquinario/estoque.html', produtos=[], resumo={}, categorias=[])


@maquinario_bp.route('/estoque/novo', methods=['GET', 'POST'])
@login_required
def produto_novo():
    if request.method == 'POST':
        try:
            produto_id, msg = maquinario.inserir_produto(_dados(
                'nome', 'categoria', 'unidade', 'quantidade_atual', 'estoque_minimo',
                'local_armazenagem', 'observacoes',
            ))
            if produto_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.estoque'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.produto_novo: {e}")
            flash(f'Erro ao cadastrar produto: {e}', 'error')
    return render_template('maquinario/produto_form.html', produto=None,
                           categorias=maquinario.CATEGORIAS_ESTOQUE)


@maquinario_bp.route('/estoque/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def produto_editar(id):
    if request.method == 'POST':
        try:
            sucesso, msg = maquinario.atualizar_produto(id, _dados(
                'nome', 'categoria', 'unidade', 'estoque_minimo',
                'local_armazenagem', 'observacoes',
            ))
            _flash(msg, sucesso)
            if sucesso:
                return redirect(url_for('maquinario.estoque'))
        except Exception as e:
            logger.error(f"maquinario_routes.produto_editar: {e}")
            flash(f'Erro ao atualizar produto: {e}', 'error')
    produto = maquinario.buscar_produto(id)
    if not produto:
        flash('Produto não encontrado.', 'warning')
        return redirect(url_for('maquinario.estoque'))
    return render_template('maquinario/produto_form.html', produto=produto,
                           categorias=maquinario.CATEGORIAS_ESTOQUE)


@maquinario_bp.route('/estoque/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def produto_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_produto(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.produto_excluir: {e}")
        flash('Erro ao remover produto.', 'error')
    return redirect(url_for('maquinario.estoque'))


@maquinario_bp.route('/movimentacoes')
@login_required
def movimentacoes():
    try:
        return render_template(
            'maquinario/movimentacoes.html',
            movimentacoes=maquinario.listar_movimentacoes(),
            produtos=maquinario.listar_produtos(),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.movimentacoes: {e}")
        flash('Erro ao carregar movimentações.', 'error')
        return render_template('maquinario/movimentacoes.html', movimentacoes=[], produtos=[])


@maquinario_bp.route('/movimentacoes/nova', methods=['GET', 'POST'])
@login_required
def movimentacao_nova():
    if request.method == 'POST':
        try:
            mov_id, msg = maquinario.registrar_movimentacao(_dados(
                'produto_id', 'tipo', 'quantidade', 'unidade', 'data_movimento',
                'valor_unitario', 'nota_fiscal', 'observacoes',
            ))
            if mov_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.movimentacoes'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.movimentacao_nova: {e}")
            flash(f'Erro ao registrar movimentação: {e}', 'error')
    return render_template('maquinario/movimentacao_form.html',
                           produtos=maquinario.listar_produtos())


@maquinario_bp.route('/movimentacoes/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def movimentacao_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_movimentacao(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.movimentacao_excluir: {e}")
        flash('Erro ao remover movimentação.', 'error')
    return redirect(url_for('maquinario.movimentacoes'))


# ---------------------------------------------------------------------------
# Máquinas e manutenção
# ---------------------------------------------------------------------------
@maquinario_bp.route('/maquinas')
@login_required
def maquinas():
    try:
        return render_template('maquinario/maquinas.html',
                               maquinas=maquinario.listar_maquinas())
    except Exception as e:
        logger.error(f"maquinario_routes.maquinas: {e}")
        flash('Erro ao carregar máquinas.', 'error')
        return render_template('maquinario/maquinas.html', maquinas=[])


@maquinario_bp.route('/maquinas/novo', methods=['GET', 'POST'])
@login_required
def maquina_novo():
    if request.method == 'POST':
        try:
            maquina_id, msg = maquinario.inserir_maquina(_dados(
                'nome', 'marca', 'modelo', 'ano', 'numero_serie', 'placa',
                'horas_atuais', 'data_aquisicao', 'observacoes',
            ))
            if maquina_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.maquinas'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.maquina_novo: {e}")
            flash(f'Erro ao cadastrar máquina: {e}', 'error')
    return render_template('maquinario/maquina_form.html', maquina=None)


@maquinario_bp.route('/maquinas/<int:id>')
@login_required
def maquina_detalhe(id):
    maquina = maquinario.buscar_maquina(id)
    if not maquina:
        flash('Máquina não encontrada.', 'warning')
        return redirect(url_for('maquinario.maquinas'))
    return render_template(
        'maquinario/maquina_detalhe.html', maquina=maquina,
        manutencoes=maquinario.listar_manutencoes(maquina_id=id),
        gastos=[g for g in maquinario.listar_gastos() if g['maquina_id'] == id][:20],
    )


@maquinario_bp.route('/maquinas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def maquina_editar(id):
    if request.method == 'POST':
        try:
            sucesso, msg = maquinario.atualizar_maquina(id, _dados(
                'nome', 'marca', 'modelo', 'ano', 'numero_serie', 'placa',
                'horas_atuais', 'data_aquisicao', 'observacoes',
            ))
            _flash(msg, sucesso)
            if sucesso:
                return redirect(url_for('maquinario.maquinas'))
        except Exception as e:
            logger.error(f"maquinario_routes.maquina_editar: {e}")
            flash(f'Erro ao atualizar máquina: {e}', 'error')
    maquina = maquinario.buscar_maquina(id)
    if not maquina:
        flash('Máquina não encontrada.', 'warning')
        return redirect(url_for('maquinario.maquinas'))
    return render_template('maquinario/maquina_form.html', maquina=maquina)


@maquinario_bp.route('/maquinas/<int:id>/horimetro', methods=['POST'])
@login_required
def horimetro(id):
    try:
        sucesso, msg = maquinario.atualizar_horimetro(id, request.form.get('horas_atuais'))
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.horimetro: {e}")
        flash('Erro ao atualizar horímetro.', 'error')
    return redirect(url_for('maquinario.maquina_detalhe', id=id))


@maquinario_bp.route('/maquinas/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def maquina_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_maquina(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.maquina_excluir: {e}")
        flash('Erro ao remover máquina.', 'error')
    return redirect(url_for('maquinario.maquinas'))


@maquinario_bp.route('/manutencoes')
@login_required
def manutencoes():
    try:
        return render_template(
            'maquinario/manutencoes.html',
            manutencoes=maquinario.listar_manutencoes(),
            maquinas=maquinario.listar_maquinas(),
            resumo=maquinario.resumo_manutencoes(),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.manutencoes: {e}")
        flash('Erro ao carregar manutenções.', 'error')
        return render_template('maquinario/manutencoes.html', manutencoes=[], maquinas=[], resumo={})


@maquinario_bp.route('/manutencoes/nova', methods=['GET', 'POST'])
@login_required
def manutencao_nova():
    if request.method == 'POST':
        try:
            registro_id, msg = maquinario.inserir_manutencao(_dados(
                'maquina_id', 'tipo', 'data_servico', 'horimetro', 'descricao',
                'valor', 'fornecedor', 'proxima_data', 'proximas_horas', 'observacoes',
            ))
            if registro_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.manutencoes'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.manutencao_nova: {e}")
            flash(f'Erro ao registrar manutenção: {e}', 'error')
    return render_template('maquinario/manutencao_form.html',
                           manutencao=None, maquinas=maquinario.listar_maquinas(),
                           tipos=maquinario.TIPOS_MANUTENCAO)


@maquinario_bp.route('/manutencoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def manutencao_editar(id):
    if request.method == 'POST':
        try:
            sucesso, msg = maquinario.atualizar_manutencao(id, _dados(
                'maquina_id', 'tipo', 'data_servico', 'horimetro', 'descricao',
                'valor', 'fornecedor', 'proxima_data', 'proximas_horas', 'observacoes',
            ))
            _flash(msg, sucesso)
            if sucesso:
                return redirect(url_for('maquinario.manutencoes'))
        except Exception as e:
            logger.error(f"maquinario_routes.manutencao_editar: {e}")
            flash(f'Erro ao atualizar manutenção: {e}', 'error')
    manutencao = None
    for item in maquinario.listar_manutencoes():
        if item['id'] == id:
            manutencao = item
            break
    if not manutencao:
        flash('Manutenção não encontrada.', 'warning')
        return redirect(url_for('maquinario.manutencoes'))
    return render_template('maquinario/manutencao_form.html', manutencao=manutencao,
                           maquinas=maquinario.listar_maquinas(),
                           tipos=maquinario.TIPOS_MANUTENCAO)


@maquinario_bp.route('/manutencoes/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def manutencao_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_manutencao(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.manutencao_excluir: {e}")
        flash('Erro ao remover manutenção.', 'error')
    return redirect(url_for('maquinario.manutencoes'))


# ---------------------------------------------------------------------------
# Combustível
# ---------------------------------------------------------------------------
@maquinario_bp.route('/combustivel')
@login_required
def combustivel():
    try:
        referencia = maquinario.obter_preco_referencia()
        resumo = maquinario.resumo_combustivel()
        pago = float(resumo['preco_pago'] or 0)
        referencia_preco = float((referencia or {}).get('municipio', {}).get('preco') or 0)
        comparativo = {
            'referencia': referencia_preco,
            'pago': pago,
            'diferenca': referencia_preco - pago,
            'percentual': ((referencia_preco - pago) / referencia_preco * 100) if referencia_preco else 0,
            'economia': (referencia_preco - pago) * float(resumo['litros'] or 0),
        }
        return render_template(
            'maquinario/combustivel.html',
            referencia=referencia,
            comparativo=comparativo,
            resumo=resumo,
            abastecimentos=maquinario.listar_abastecimentos(limite=100),
            precos=maquinario.listar_precos_diesel(limite=30),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.combustivel: {e}")
        flash('Erro ao carregar dados de combustível.', 'error')
        return render_template('maquinario/combustivel.html', referencia=None,
                               comparativo={}, resumo={}, abastecimentos=[],
                               precos=[])


@maquinario_bp.route('/combustivel/atualizar-precos', methods=['POST'])
@login_required
@admin_required
def precos_atualizar():
    try:
        dados = maquinario.buscar_precos_anp(force=True, usar_cache_em_falha=False)
        flash(f"Preços da ANP atualizados: semana de {dados['semana'].strftime('%d/%m/%Y')}.", 'success')
    except Exception as e:
        logger.error(f"maquinario_routes.precos_atualizar: {e}")
        flash(f'Falha ao atualizar preços da ANP: {e}', 'error')
    return redirect(url_for('maquinario.combustivel'))


@maquinario_bp.route('/combustivel/abastecimentos')
@login_required
def abastecimentos():
    try:
        return render_template(
            'maquinario/abastecimentos.html',
            abastecimentos=maquinario.listar_abastecimentos(),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.abastecimentos: {e}")
        flash('Erro ao carregar abastecimentos.', 'error')
        return render_template('maquinario/abastecimentos.html', abastecimentos=[])


@maquinario_bp.route('/combustivel/novo', methods=['GET', 'POST'])
@login_required
def abastecimento_novo():
    if request.method == 'POST':
        try:
            registro_id, msg = maquinario.inserir_abastecimento(_dados(
                'data_abastecimento', 'produto', 'quantidade_litros',
                'valor_litro', 'valor_total', 'fornecedor', 'boleto', 'vencimento',
                'lembrete_em', 'pago', 'observacoes',
            ))
            if registro_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.abastecimentos'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.abastecimento_novo: {e}")
            flash(f'Erro ao registrar entrega: {e}', 'error')
    return render_template('maquinario/abastecimento_form.html', abastecimento=None)


@maquinario_bp.route('/combustivel/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def abastecimento_editar(id):
    if request.method == 'POST':
        try:
            sucesso, msg = maquinario.atualizar_abastecimento(id, _dados(
                'data_abastecimento', 'produto', 'quantidade_litros',
                'valor_litro', 'valor_total', 'fornecedor', 'boleto', 'vencimento',
                'lembrete_em', 'pago', 'observacoes',
            ))
            _flash(msg, sucesso)
            if sucesso:
                return redirect(url_for('maquinario.abastecimentos'))
        except Exception as e:
            logger.error(f"maquinario_routes.abastecimento_editar: {e}")
            flash(f'Erro ao atualizar entrega: {e}', 'error')
    abastecimento = maquinario.buscar_abastecimento(id)
    if not abastecimento:
        flash('Entrega não encontrada.', 'warning')
        return redirect(url_for('maquinario.abastecimentos'))
    return render_template('maquinario/abastecimento_form.html',
                           abastecimento=abastecimento)


@maquinario_bp.route('/combustivel/<int:id>/pagar', methods=['POST'])
@login_required
def abastecimento_pagar(id):
    try:
        sucesso, msg = maquinario.marcar_pago(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.abastecimento_pagar: {e}")
        flash('Erro ao registrar pagamento.', 'error')
    return redirect(url_for('maquinario.abastecimentos'))


@maquinario_bp.route('/combustivel/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def abastecimento_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_abastecimento(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.abastecimento_excluir: {e}")
        flash('Erro ao remover abastecimento.', 'error')
    return redirect(url_for('maquinario.abastecimentos'))


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------
@maquinario_bp.route('/gastos')
@login_required
def gastos():
    try:
        return render_template(
            'maquinario/gastos.html',
            gastos=maquinario.listar_gastos(),
            resumo=maquinario.resumo_gastos(),
            maquinas=maquinario.listar_maquinas(),
        )
    except Exception as e:
        logger.error(f"maquinario_routes.gastos: {e}")
        flash('Erro ao carregar gastos.', 'error')
        return render_template('maquinario/gastos.html', gastos=[], resumo={}, maquinas=[])


@maquinario_bp.route('/gastos/novo', methods=['GET', 'POST'])
@login_required
def gasto_novo():
    if request.method == 'POST':
        try:
            registro_id, msg = maquinario.inserir_gasto(_dados(
                'data_gasto', 'descricao', 'categoria', 'maquina_id', 'valor',
                'local_compra', 'fornecedor', 'nota_fiscal', 'observacoes',
            ))
            if registro_id:
                flash(msg, 'success')
                return redirect(url_for('maquinario.gastos'))
            _flash(msg, False)
        except Exception as e:
            logger.error(f"maquinario_routes.gasto_novo: {e}")
            flash(f'Erro ao registrar gasto: {e}', 'error')
    return render_template('maquinario/gasto_form.html', gasto=None,
                           maquinas=maquinario.listar_maquinas(),
                           categorias=maquinario.CATEGORIAS_GASTO)


@maquinario_bp.route('/gastos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def gasto_editar(id):
    if request.method == 'POST':
        try:
            sucesso, msg = maquinario.atualizar_gasto(id, _dados(
                'data_gasto', 'descricao', 'categoria', 'maquina_id', 'valor',
                'local_compra', 'fornecedor', 'nota_fiscal', 'observacoes',
            ))
            _flash(msg, sucesso)
            if sucesso:
                return redirect(url_for('maquinario.gastos'))
        except Exception as e:
            logger.error(f"maquinario_routes.gasto_editar: {e}")
            flash(f'Erro ao atualizar gasto: {e}', 'error')
    gasto = maquinario.buscar_gasto(id)
    if not gasto:
        flash('Gasto não encontrado.', 'warning')
        return redirect(url_for('maquinario.gastos'))
    return render_template('maquinario/gasto_form.html', gasto=gasto,
                           maquinas=maquinario.listar_maquinas(),
                           categorias=maquinario.CATEGORIAS_GASTO)


@maquinario_bp.route('/gastos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def gasto_excluir(id):
    try:
        sucesso, msg = maquinario.excluir_gasto(id)
        _flash(msg, sucesso)
    except Exception as e:
        logger.error(f"maquinario_routes.gasto_excluir: {e}")
        flash('Erro ao remover gasto.', 'error')
    return redirect(url_for('maquinario.gastos'))
