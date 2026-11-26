from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, Response
from app.modules import (pulverizacao, receitas, estoque, talhoes,
                         clima, fila_aplicacao as fila, eficacia,
                         historico_manejo as historico, auth)
from app.modules.login_manager import login_required, admin_required
from datetime import datetime
import io
import csv
import json
from app.models import get_logger

logger = get_logger(__name__)
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
        pragas = pulverizacao.listar_pragas_doencas()
        contagem_fila = fila.contar_tarefas()
        return render_template('pulverizacao/dashboard.html',
                             aplicacoes=aplicacoes[:10],
                             total_aplicacoes=len(aplicacoes),
                             total_receitas=len(receitas),
                             periodos=periodos,
                             pragas=pragas,
                             tarefas_pendentes=contagem_fila['pendente'],
                             tarefas_aplicadas=contagem_fila['aplicada'])
    except Exception as e:
        logger.error(f"pulverizacao_routes.dashboard: {e}")
        flash('Erro ao carregar painel de pulverização.', 'error')
        return render_template('pulverizacao/dashboard.html',
                             aplicacoes=[], total_aplicacoes=0,
                             total_receitas=0, periodos=[], pragas=[],
                             tarefas_pendentes=0, tarefas_aplicadas=0)

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
        logger.error(f"pulverizacao_routes.listar_aplicacoes: {e}")
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
            logger.error(f"pulverizacao_routes.nova_aplicacao: {e}")
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        periodos = pulverizacao.listar_periodos()
        receitas = pulverizacao.listar_receitas()
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('pulverizacao/aplicacoes/nova.html',
                             periodos=periodos, receitas=receitas, talhoes=talhoes_lista)
    except Exception as e:
        logger.error(f"pulverizacao_routes.nova_aplicacao: {e}")
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
        logger.error(f"pulverizacao_routes.detalhe_aplicacao: {e}")
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
            logger.error(f"pulverizacao_routes.editar_aplicacao: {e}")
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
        logger.error(f"pulverizacao_routes.editar_aplicacao: {e}")
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
        logger.error(f"pulverizacao_routes.excluir_aplicacao: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/periodos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_periodo(id):
    # Períodos e pragas/doenças fazem parte do cadastro base do sistema.
    flash('Períodos da lavoura são cadastrados pelo sistema e não podem ser excluídos.', 'warning')
    return redirect(url_for('pulverizacao.dashboard'))

@pulverizacao_bp.route('/pragas/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_praga(id):
    flash('Pragas e doenças fazem parte do cadastro base e não podem ser excluídas.', 'warning')
    return redirect(url_for('pulverizacao.dashboard'))

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
            logger.error(f"pulverizacao_routes.retorno_aplicacao: {e}")
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
        logger.error(f"pulverizacao_routes.retorno_aplicacao: {e}")
        flash('Erro ao carregar retorno.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/aplicacoes/<int:id>/retorno/limpar', methods=['POST'])
@login_required
@admin_required
def limpar_retorno(id):
    try:
        sucesso, msg = pulverizacao.limpar_retorno(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"pulverizacao_routes.limpar_retorno: {e}")
        flash('Erro ao limpar retorno.', 'error')
    return redirect(url_for('pulverizacao.retorno_aplicacao', id=id))

# =====================================================
# RECEITAS ESTRUTURADAS (PRODUTOS + TALHOES + COMPRAS)
# =====================================================

def _dados_formulario_receita():
    return {
        'periodos': pulverizacao.listar_periodos(),
        'produtos': estoque.listar_produtos(ativos=True),
        'talhoes_disponiveis': talhoes.listar_talhoes(),
    }


def _lista_do_formulario(campo, mensagem):
    try:
        valores = json.loads(request.form.get(campo) or '[]')
    except (TypeError, ValueError):
        raise ValueError(mensagem)
    if not isinstance(valores, list):
        raise ValueError(mensagem)
    return valores


def _cabecalho_do_formulario():
    return {
        'nome': request.form.get('nome'),
        'periodo_id': request.form.get('periodo_id'),
        'descricao': request.form.get('descricao'),
        'observacoes': request.form.get('observacoes'),
        '_usuario': session.get('usuario'),
    }


def _periodo_nome(periodo_id):
    if not periodo_id:
        return 'Geral'
    for periodo in pulverizacao.listar_periodos():
        if periodo['id'] == periodo_id:
            return periodo['nome']
    return 'Geral'


@pulverizacao_bp.route('/receitas')
@login_required
def listar_receitas():
    try:
        lista = pulverizacao.listar_receitas()
        contagens = receitas.contar_talhoes_por_receita()
        return render_template('pulverizacao/receitas/lista.html',
                               receitas=lista, contagens=contagens)
    except Exception as e:
        logger.error(f"pulverizacao_routes.listar_receitas: {e}")
        flash('Erro ao carregar receitas.', 'error')
        return render_template('pulverizacao/receitas/lista.html', receitas=[], contagens={})


@pulverizacao_bp.route('/receitas/nova', methods=['GET', 'POST'])
@login_required
def nova_receita():
    if request.method == 'POST':
        try:
            receita_id, _ = receitas.salvar_receita(
                _cabecalho_do_formulario(),
                _lista_do_formulario('itens_json', 'Lista de produtos inválida.'),
                _lista_do_formulario('talhoes_json', 'Seleção de talhões inválida.'),
            )
            flash('Receita cadastrada com sucesso!', 'success')
            return redirect(url_for('pulverizacao.detalhe_receita', id=receita_id))
        except Exception as e:
            logger.error(f"pulverizacao_routes.nova_receita: {e}")
            flash(str(e), 'error')

    try:
        return render_template('pulverizacao/receitas/formulario.html',
                               receita=None, itens=[], talhoes_selecionados=[],
                               resumo=None, acao=url_for('pulverizacao.nova_receita'),
                               **_dados_formulario_receita())
    except Exception as e:
        logger.error(f"pulverizacao_routes.nova_receita: {e}")
        flash('Erro ao carregar formulário.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))


@pulverizacao_bp.route('/receitas/<int:id>')
@login_required
def detalhe_receita(id):
    try:
        receita = pulverizacao.buscar_receita_por_id(id)
        if not receita:
            flash('Receita não encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_receitas'))
        return render_template(
            'pulverizacao/receitas/detalhe.html',
            receita=receita,
            periodo_nome=_periodo_nome(receita.get('periodo_id')),
            itens=receitas.listar_itens(id),
            talhoes=receitas.listar_talhoes(id),
            resumo=receitas.resumo_compras(id),
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.detalhe_receita: {e}")
        flash('Erro ao carregar receita.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))


@pulverizacao_bp.route('/receitas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_receita(id):
    if request.method == 'POST':
        try:
            receitas.salvar_receita(
                _cabecalho_do_formulario(),
                _lista_do_formulario('itens_json', 'Lista de produtos inválida.'),
                _lista_do_formulario('talhoes_json', 'Seleção de talhões inválida.'),
                receita_id=id,
            )
            flash('Receita atualizada com sucesso!', 'success')
            return redirect(url_for('pulverizacao.detalhe_receita', id=id))
        except Exception as e:
            logger.error(f"pulverizacao_routes.editar_receita: {e}")
            flash(str(e), 'error')

    try:
        receita = pulverizacao.buscar_receita_por_id(id)
        if not receita:
            flash('Receita não encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_receitas'))
        return render_template(
            'pulverizacao/receitas/formulario.html',
            receita=receita,
            itens=receitas.listar_itens(id),
            talhoes_selecionados=receitas.listar_talhoes(id),
            resumo=receitas.resumo_compras(id),
            acao=url_for('pulverizacao.editar_receita', id=id),
            **_dados_formulario_receita()
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.editar_receita: {e}")
        flash('Erro ao carregar formulário.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))


@pulverizacao_bp.route('/receitas/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_receita(id):
    try:
        sucesso, msg = pulverizacao.excluir_receita(id)
        if sucesso:
            receitas.desativar_detalhes(id)
            flash(msg, 'success')
        else:
            flash(msg, 'warning')
    except Exception as e:
        logger.error(f"pulverizacao_routes.excluir_receita: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('pulverizacao.listar_receitas'))

# =====================================================
# FILA DE APLICACAO (CAMPO)
# =====================================================

@pulverizacao_bp.route('/fila')
@login_required
def fila_aplicacao():
    try:
        filtro = request.args.get('status', 'pendente')
        if filtro not in ('pendente', 'aplicada', 'todas'):
            filtro = 'pendente'
        status = None if filtro == 'todas' else filtro
        receita_id = request.args.get('receita', type=int)
        talhao_id = request.args.get('talhao', type=int)
        tarefas = fila.listar_tarefas(status=status, talhao_id=talhao_id, receita_id=receita_id)
        contagem = fila.contar_tarefas()
        return render_template('pulverizacao/fila/lista.html',
                               tarefas=tarefas, filtro=filtro, contagem=contagem,
                               opcoes=fila.opcoes_filtro_fila(),
                               receita_id=receita_id, talhao_id=talhao_id)
    except Exception as e:
        logger.error(f"pulverizacao_routes.fila_aplicacao: {e}")
        flash('Erro ao carregar a fila de aplicação.', 'error')
        return render_template('pulverizacao/fila/lista.html',
                               tarefas=[], filtro='pendente',
                               contagem={'pendente': 0, 'aplicada': 0},
                               opcoes={'receitas': [], 'talhoes': []},
                               receita_id=None, talhao_id=None)


@pulverizacao_bp.route('/fila/<int:id>')
@login_required
def detalhe_tarefa(id):
    try:
        tarefa = fila.buscar_tarefa(id)
        if not tarefa:
            flash('Tarefa não encontrada.', 'warning')
            return redirect(url_for('pulverizacao.fila_aplicacao'))
        pendente = tarefa['status'] == 'pendente'
        clima_atual = clima.get_clima_atual() if pendente else None
        pode_editar = (pendente or
                       session.get('tipo') in ('admin', 'agronomista'))
        return render_template(
            'pulverizacao/fila/detalhe.html',
            tarefa=tarefa,
            itens=fila.listar_itens_tarefa(id),
            clima_atual=clima_atual,
            pode_editar=pode_editar,
            pode_avaliar=session.get('tipo') in ('admin', 'agronomista'),
            avaliacao=eficacia.buscar_avaliacao(id),
            log=fila.listar_log(id),
            faltantes=fila.produtos_para_entrada_rapida(id) if pendente else [],
            abrir_modal=request.args.get('entrada') == '1',
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.detalhe_tarefa: {e}")
        flash('Erro ao carregar a tarefa.', 'error')
        return redirect(url_for('pulverizacao.fila_aplicacao'))


@pulverizacao_bp.route('/fila/<int:id>/aplicar', methods=['POST'])
@login_required
def marcar_tarefa_aplicada(id):
    tarefa = fila.buscar_tarefa(id)
    if not tarefa:
        flash('Tarefa não encontrada.', 'warning')
        return redirect(url_for('pulverizacao.fila_aplicacao'))
    if tarefa['status'] != 'pendente':
        flash('Esta tarefa já foi marcada como aplicada.', 'warning')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))

    try:
        clima_atual = clima.get_clima_atual()
        fila.marcar_aplicada(
            id,
            request.form.get('responsavel') or session.get('usuario'),
            request.form.get('observacoes'),
            session.get('usuario'),
            clima_atual,
        )
        flash('Aplicação registrada: data, hora e clima capturados; estoque baixado.', 'success')
    except fila.SaldoInsuficienteError as e:
        logger.error(f"pulverizacao_routes.marcar_tarefa_aplicada: {e}")
        flash(str(e), 'error')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id, entrada=1))
    except Exception as e:
        logger.error(f"pulverizacao_routes.marcar_tarefa_aplicada: {e}")
        flash(str(e), 'error')
    return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))


@pulverizacao_bp.route('/fila/<int:id>/entrada-rapida', methods=['POST'])
@login_required
def entrada_rapida_tarefa(id):
    tarefa = fila.buscar_tarefa(id)
    if not tarefa:
        flash('Tarefa não encontrada.', 'warning')
        return redirect(url_for('pulverizacao.fila_aplicacao'))
    if tarefa['status'] != 'pendente':
        flash('Esta tarefa já foi marcada como aplicada.', 'warning')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))

    produto_ids = request.form.getlist('produto_ids[]')
    quantidades = request.form.getlist('quantidades[]')
    if not produto_ids or len(produto_ids) != len(quantidades):
        flash('Informe a quantidade de pelo menos um produto.', 'error')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id, entrada=1))

    login = request.form.get('nome')
    senha = request.form.get('senha')
    usuario, erro = auth.autenticar_usuario(login, senha)
    if not usuario:
        logger.warning(
            f"pulverizacao_routes.entrada_rapida_tarefa: confirmação negada "
            f"para '{login}' na tarefa {id}: {erro}"
        )
        flash('Login ou senha incorretos. A entrada não foi registrada.', 'error')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id, entrada=1))

    entradas = list(zip(produto_ids, quantidades))
    try:
        itens = fila.registrar_entrada_rapida(
            id, entradas, usuario['nome'], login, session.get('usuario')
        )
        flash('Entrada rápida registrada e confirmada: ' + '; '.join(itens) + '.', 'success')
    except Exception as e:
        logger.error(f"pulverizacao_routes.entrada_rapida_tarefa: {e}")
        flash(str(e), 'error')
    return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))


@pulverizacao_bp.route('/fila/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tarefa(id):
    tarefa = fila.buscar_tarefa(id)
    if not tarefa:
        flash('Tarefa não encontrada.', 'warning')
        return redirect(url_for('pulverizacao.fila_aplicacao'))

    if tarefa['status'] == 'aplicada' and session.get('tipo') not in ('admin', 'agronomista'):
        logger.warning(
            f"pulverizacao_routes.editar_tarefa: edição negada ao usuário {session.get('usuario')} "
            f"(nível {session.get('tipo')}) na tarefa {id}"
        )
        flash('Depois de aplicada, só agronomista ou administrador pode editar.', 'error')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))

    if request.method == 'POST':
        try:
            fila.atualizar_tarefa(id, {
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes'),
                'data_aplicacao': request.form.get('data_aplicacao'),
                'hora_aplicacao': request.form.get('hora_aplicacao'),
                'clima_temperatura': request.form.get('clima_temperatura'),
                'clima_umidade': request.form.get('clima_umidade'),
                'clima_descricao': request.form.get('clima_descricao'),
                'clima_vento': request.form.get('clima_vento'),
            }, session.get('usuario'))
            flash('Tarefa atualizada. Alteração registrada no histórico.', 'success')
            return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))
        except Exception as e:
            logger.error(f"pulverizacao_routes.editar_tarefa: {e}")
            flash(str(e), 'error')

    return render_template('pulverizacao/fila/editar.html',
                           tarefa=tarefa, log=fila.listar_log(id))


@pulverizacao_bp.route('/fila/<int:id>/eficacia', methods=['GET', 'POST'])
@login_required
def avaliar_eficacia(id):
    tarefa = fila.buscar_tarefa(id)
    if not tarefa:
        flash('Tarefa não encontrada.', 'warning')
        return redirect(url_for('pulverizacao.fila_aplicacao'))
    if tarefa['status'] != 'aplicada':
        flash('Só é possível avaliar uma aplicação já concluída.', 'warning')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))
    if session.get('tipo') not in ('admin', 'agronomista'):
        logger.warning(
            f"pulverizacao_routes.avaliar_eficacia: avaliação negada ao usuário "
            f"{session.get('usuario')} (nível {session.get('tipo')}) na tarefa {id}"
        )
        flash('Somente agronomista ou administrador pode registrar eficácia.', 'error')
        return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))

    if request.method == 'POST':
        try:
            eficacia.salvar_avaliacao(id, {
                'resultado': request.form.get('resultado'),
                'nota': request.form.get('nota'),
                'data_avaliacao': request.form.get('data_avaliacao'),
                'observacoes': request.form.get('observacoes'),
            }, session.get('usuario'))
            flash('Eficácia registrada e ligada ao histórico do talhão.', 'success')
            return redirect(url_for('pulverizacao.detalhe_tarefa', id=id))
        except Exception as e:
            logger.error(f"pulverizacao_routes.avaliar_eficacia: {e}")
            flash(str(e), 'error')

    return render_template(
        'pulverizacao/fila/eficacia.html',
        tarefa=tarefa,
        avaliacao=eficacia.buscar_avaliacao(id),
        resultados=eficacia.RESULTADOS,
        cores=eficacia.CORES,
    )


@pulverizacao_bp.route('/historico')
@login_required
def historico_manejo():
    try:
        talhao_id = request.args.get('talhao_id', type=int)
        ano = request.args.get('ano', type=int)
        periodo_id = request.args.get('periodo_id', type=int)
        aplicacoes = historico.listar_aplicacoes(talhao_id, ano, periodo_id)
        return render_template(
            'pulverizacao/historico.html',
            aplicacoes=aplicacoes,
            resumo=historico.resumo(aplicacoes),
            safras=historico.por_safra(aplicacoes),
            produtos=historico.por_produto(talhao_id, ano, periodo_id),
            receitas=historico.por_receita(talhao_id, ano, periodo_id),
            talhoes=talhoes.listar_talhoes(),
            periodos=pulverizacao.listar_periodos(),
            anos=historico.anos_disponiveis(),
            filtro_talhao=talhao_id,
            filtro_ano=ano,
            filtro_periodo=periodo_id,
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.historico_manejo: {e}")
        flash('Erro ao carregar o histórico de manejo.', 'error')
        return render_template(
            'pulverizacao/historico.html',
            aplicacoes=[], resumo=historico.resumo([]), safras=[],
            produtos=[], receitas=[], talhoes=[], periodos=[], anos=[],
            filtro_talhao=None, filtro_ano=None, filtro_periodo=None,
        )


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
            logger.error(f"pulverizacao_routes.nova_ocorrencia: {e}")
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        pragas = pulverizacao.listar_pragas_doencas()
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('pulverizacao/ocorrencias/nova.html',
                             pragas=pragas, talhoes=talhoes_lista)
    except Exception as e:
        logger.error(f"pulverizacao_routes.nova_ocorrencia: {e}")
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))

@pulverizacao_bp.route('/aplicacoes/exportar-csv')
@login_required
def exportar_csv_aplicacoes():
    """Exporta lista de aplicações para CSV."""
    try:
        aplicacoes = pulverizacao.listar_aplicacoes()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Data', 'Talhao', 'Periodo', 'Responsavel', 'Receita', 'Data Retorno', 'Status'])
        for a in aplicacoes:
            writer.writerow([
                a.get('id', ''),
                a.get('data_aplicacao', ''),
                a.get('talhao_nome', ''),
                a.get('periodo_nome', ''),
                a.get('responsavel', ''),
                a.get('receita_nome', ''),
                a.get('data_prevista_retorno', ''),
                a.get('status_retorno', '')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=aplicacoes_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.exportar_csv_aplicacoes: {e}")
        flash('Erro ao exportar CSV.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))


@pulverizacao_bp.route('/aplicacoes/exportar-pdf')
@login_required
def exportar_pdf_aplicacoes():
    """PDF completo das aplicações, com talhão, período e retorno."""
    try:
        aplicacoes = []
        for a in pulverizacao.listar_aplicacoes():
            item = dict(a)
            item['data_retorno'] = item.get('data_retorno') or item.get('data_prevista_retorno') or '-'
            item['data_aplicacao'] = item.get('data_aplicacao') or '-'
            item['periodo_nome'] = item.get('periodo_nome') or 'Geral'
            item['receita_nome'] = item.get('receita_nome') or '-'
            aplicacoes.append(item)

        buffer = pulverizacao.gerar_pdf_pulverizacoes(
            aplicacoes,
            request.args.get('data_inicio') or None,
            request.args.get('data_fim') or None,
        )
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename=aplicacoes_{datetime.now().strftime("%Y%m%d")}.pdf'}
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.exportar_pdf_aplicacoes: {e}")
        flash('Erro ao gerar PDF das aplicações.', 'error')
        return redirect(url_for('pulverizacao.listar_aplicacoes'))


@pulverizacao_bp.route('/receitas/exportar-pdf')
@login_required
def exportar_pdf_receitas():
    """PDF de todas as receitas, com o nome do período fenológico."""
    try:
        lista = []
        for r in pulverizacao.listar_receitas():
            item = dict(r)
            item['periodo_nome'] = _periodo_nome(item.get('periodo_id'))
            lista.append(item)

        buffer = pulverizacao.gerar_pdf_receitas(
            lista,
            periodo_filtro=request.args.get('periodo_id', type=int),
            mes=request.args.get('mes', type=int),
            ano=request.args.get('ano', type=int),
            termo_busca=request.args.get('termo_busca') or None,
        )
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename=receitas_{datetime.now().strftime("%Y%m%d")}.pdf'}
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.exportar_pdf_receitas: {e}")
        flash('Erro ao gerar PDF das receitas.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))


@pulverizacao_bp.route('/receitas/<int:id>/pdf')
@login_required
def pdf_receita(id):
    """PDF de uma receita específica."""
    try:
        receita = pulverizacao.buscar_receita_por_id(id)
        if not receita:
            flash('Receita não encontrada.', 'warning')
            return redirect(url_for('pulverizacao.listar_receitas'))

        item = dict(receita)
        item['periodo_nome'] = _periodo_nome(item.get('periodo_id'))
        buffer = pulverizacao.gerar_pdf_receitas([item])
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename=receita_{id}.pdf'}
        )
    except Exception as e:
        logger.error(f"pulverizacao_routes.pdf_receita: {e}")
        flash('Erro ao gerar PDF da receita.', 'error')
        return redirect(url_for('pulverizacao.listar_receitas'))