from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules.login_manager import login_required, admin_required
from app.modules import manejo, calendario_cafe, gastos_cafe, talhoes
from app.models import get_logger

logger = get_logger(__name__)
manejo_bp = Blueprint('manejo', __name__, url_prefix='/manejo')

@manejo_bp.route('/')
@login_required
def visao_geral():
    """Pagina principal de Manejo do Cafezal."""
    try:
        timeline = manejo.get_timeline_manejo(30)
        resumo = manejo.get_resumo_manejo()
        return render_template('manejo/visao_geral.html', timeline=timeline, resumo=resumo,
                               sugestoes=calendario_cafe.sugestoes_do_mes(),
                               gastos=gastos_cafe.resumo(calendario_cafe.safra_de()))
    except Exception as e:
        logger.error(f"manejo_routes.visao_geral: {e}")
        flash('Erro ao carregar o manejo.', 'error')
        return render_template('manejo/visao_geral.html', timeline=[], resumo={},
                               sugestoes=None, gastos=None)

@manejo_bp.route('/talhao/<int:id>')
@login_required
def manejo_talhao(id):
    """Manejo de um talhao especifico."""
    try:
        from app.modules import talhoes
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhao nao encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        timeline = manejo.get_manejo_por_talhao(id)
        return render_template('manejo/visao_geral.html', timeline=timeline, resumo=manejo.get_resumo_manejo(),
                               talhao=talhao, sugestoes=calendario_cafe.sugestoes_do_mes(),
                               gastos=gastos_cafe.resumo(calendario_cafe.safra_de(), talhao_id=id))
    except Exception as e:
        logger.error(f"manejo_routes.manejo_talhao: {e}")
        flash('Erro ao carregar manejo do talhao.', 'error')
        return redirect(url_for('manejo.visao_geral'))


# =====================================================
# CALENDÁRIO DO CAFÉ
# =====================================================
def _safra_escolhida():
    safra = (request.args.get('safra') or request.form.get('safra') or '').strip()
    return safra if safra in calendario_cafe.safras_disponiveis() else calendario_cafe.safra_de()


@manejo_bp.route('/calendario')
@login_required
def calendario():
    try:
        dados = calendario_cafe.montar_calendario(_safra_escolhida())
        return render_template('manejo/calendario.html', cal=dados,
                               safras=calendario_cafe.safras_disponiveis(),
                               talhoes=talhoes.listar_talhoes(),
                               categorias=calendario_cafe.CATEGORIAS)
    except Exception as e:
        logger.error(f"manejo_routes.calendario: {e}")
        flash('Erro ao carregar o calendário do café.', 'error')
        return redirect(url_for('manejo.visao_geral'))


@manejo_bp.route('/calendario/<int:tarefa_id>/feito', methods=['POST'])
@login_required
def calendario_feito(tarefa_id):
    safra = _safra_escolhida()
    try:
        ok, msg = calendario_cafe.registrar_execucao(tarefa_id, safra, request.form, session.get('usuario'))
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"manejo_routes.calendario_feito: {e}")
        flash('Erro ao marcar a tarefa.', 'error')
    return redirect(url_for('manejo.calendario', safra=safra) + f'#tarefa-{tarefa_id}')


@manejo_bp.route('/calendario/execucao/<int:execucao_id>/desfazer', methods=['POST'])
@login_required
def calendario_desfazer(execucao_id):
    safra = _safra_escolhida()
    try:
        ok, msg = calendario_cafe.desfazer_execucao(execucao_id)
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"manejo_routes.calendario_desfazer: {e}")
        flash('Erro ao desfazer.', 'error')
    return redirect(url_for('manejo.calendario', safra=safra))


@manejo_bp.route('/calendario/tarefas/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def calendario_tarefa_nova():
    if request.method == 'POST':
        try:
            ok, msg = calendario_cafe.salvar_tarefa(None, request.form)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('manejo.calendario'))
        except Exception as e:
            logger.error(f"manejo_routes.calendario_tarefa_nova: {e}")
            flash('Erro ao salvar a tarefa.', 'error')
    return render_template('manejo/calendario_tarefa_form.html', tarefa=None,
                           periodos=calendario_cafe.listar_periodos(),
                           categorias=calendario_cafe.CATEGORIAS, meses=calendario_cafe.MESES_NOME)


@manejo_bp.route('/calendario/tarefas/<int:tarefa_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def calendario_tarefa_editar(tarefa_id):
    if request.method == 'POST':
        try:
            ok, msg = calendario_cafe.salvar_tarefa(tarefa_id, request.form)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('manejo.calendario') + f'#tarefa-{tarefa_id}')
        except Exception as e:
            logger.error(f"manejo_routes.calendario_tarefa_editar: {e}")
            flash('Erro ao salvar a tarefa.', 'error')
    tarefa = calendario_cafe.buscar_tarefa(tarefa_id)
    if not tarefa:
        flash('Tarefa não encontrada.', 'warning')
        return redirect(url_for('manejo.calendario'))
    return render_template('manejo/calendario_tarefa_form.html', tarefa=tarefa,
                           periodos=calendario_cafe.listar_periodos(),
                           categorias=calendario_cafe.CATEGORIAS, meses=calendario_cafe.MESES_NOME)


@manejo_bp.route('/calendario/tarefas/<int:tarefa_id>/excluir', methods=['POST'])
@login_required
@admin_required
def calendario_tarefa_excluir(tarefa_id):
    try:
        ok, msg = calendario_cafe.excluir_tarefa(tarefa_id)
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"manejo_routes.calendario_tarefa_excluir: {e}")
        flash('Erro ao remover a tarefa.', 'error')
    return redirect(url_for('manejo.calendario'))


# =====================================================
# GASTOS DO CAFÉ (mão de obra e serviços)
# =====================================================
def _filtros_gastos():
    safra = (request.args.get('safra') or '').strip()
    if safra != 'todas' and safra not in calendario_cafe.safras_disponiveis():
        safra = calendario_cafe.safra_de()
    categoria = request.args.get('categoria') if request.args.get('categoria') in gastos_cafe.CATEGORIAS else None
    talhao = request.args.get('talhao') or None
    if talhao and talhao != 'geral':
        try:
            talhao = int(talhao)
        except ValueError:
            talhao = None
    return safra, categoria, talhao


@manejo_bp.route('/gastos')
@login_required
def gastos():
    safra, categoria, talhao = _filtros_gastos()
    filtro_safra = None if safra == 'todas' else safra
    try:
        return render_template(
            'manejo/gastos.html',
            gastos=gastos_cafe.listar(filtro_safra, categoria, talhao),
            resumo=gastos_cafe.resumo(filtro_safra, categoria, talhao),
            safra=safra, categoria=categoria, talhao=talhao,
            safras=calendario_cafe.safras_disponiveis(), categorias=gastos_cafe.CATEGORIAS,
            formas=gastos_cafe.FORMAS, talhoes=talhoes.listar_talhoes(),
        )
    except Exception as e:
        logger.error(f"manejo_routes.gastos: {e}")
        flash('Erro ao carregar os gastos do café.', 'error')
        return redirect(url_for('manejo.visao_geral'))


def _form_gasto(gasto):
    return render_template('manejo/gasto_form.html', gasto=gasto,
                           categorias=gastos_cafe.CATEGORIAS, formas=gastos_cafe.FORMAS,
                           unidades=gastos_cafe.UNIDADES_PRODUCAO, talhoes=talhoes.listar_talhoes(),
                           categoria_inicial=request.args.get('categoria'))


@manejo_bp.route('/gastos/novo', methods=['GET', 'POST'])
@login_required
def gasto_novo():
    if request.method == 'POST':
        try:
            ok, msg = gastos_cafe.salvar(None, request.form, session.get('usuario'))
            flash(msg, 'success' if ok else 'error')
            if ok:
                if request.form.get('continuar'):
                    return redirect(url_for('manejo.gasto_novo', categoria=request.form.get('categoria')))
                return redirect(url_for('manejo.gastos'))
        except Exception as e:
            logger.error(f"manejo_routes.gasto_novo: {e}")
            flash('Erro ao registrar o gasto.', 'error')
        return _form_gasto(dict(request.form))
    return _form_gasto(None)


@manejo_bp.route('/gastos/<int:gasto_id>/editar', methods=['GET', 'POST'])
@login_required
def gasto_editar(gasto_id):
    if request.method == 'POST':
        try:
            ok, msg = gastos_cafe.salvar(gasto_id, request.form)
            flash(msg, 'success' if ok else 'error')
            if ok:
                return redirect(url_for('manejo.gastos'))
        except Exception as e:
            logger.error(f"manejo_routes.gasto_editar: {e}")
            flash('Erro ao atualizar o gasto.', 'error')
    gasto = gastos_cafe.buscar(gasto_id)
    if not gasto:
        flash('Gasto não encontrado.', 'warning')
        return redirect(url_for('manejo.gastos'))
    return _form_gasto(gasto)


@manejo_bp.route('/gastos/<int:gasto_id>/pagar', methods=['POST'])
@login_required
def gasto_pagar(gasto_id):
    try:
        ok, msg = gastos_cafe.marcar_pago(gasto_id)
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"manejo_routes.gasto_pagar: {e}")
        flash('Erro ao registrar o pagamento.', 'error')
    return redirect(url_for('manejo.gastos'))


@manejo_bp.route('/gastos/<int:gasto_id>/excluir', methods=['POST'])
@login_required
@admin_required
def gasto_excluir(gasto_id):
    try:
        ok, msg = gastos_cafe.excluir(gasto_id)
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"manejo_routes.gasto_excluir: {e}")
        flash('Erro ao remover o gasto.', 'error')
    return redirect(url_for('manejo.gastos'))
