from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, send_from_directory, session, abort)
from app.modules import analises
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger
import os
import uuid
from datetime import date

logger = get_logger(__name__)
analises_bp = Blueprint('analises', __name__, url_prefix='/analises')

MAX_PDFS_POR_LOTE = 20
MAX_PDF_BYTES = 25 * 1024 * 1024
CHAVE_SESSAO_UPLOAD = 'laudos_upload'


def _dir_laudos():
    return os.path.join(current_app.config['UPLOAD_FOLDER'], 'laudos')


def _dir_temporarios():
    caminho = os.path.join(_dir_laudos(), 'tmp')
    os.makedirs(caminho, exist_ok=True)
    return caminho


def _limpar_temporarios(itens):
    for item in itens or []:
        caminho = os.path.join(_dir_temporarios(), item.get('nome_temp') or '')
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
        except Exception as e:
            logger.error(f"analises_routes._limpar_temporarios: {e}")


@analises_bp.route('/')
@login_required
def dashboard():
    try:
        lista = analises.listar_analises()
        laboratorios = analises.listar_laboratorios()
        tipos = analises.listar_tipos_analise()
        return render_template('analises/dashboard.html',
                             analises=lista[:10], total=len(lista),
                             total_labs=len(laboratorios), tipos=tipos,
                             por_tipo=analises.contar_por_tipo())
    except Exception as e:
        logger.error(f"analises_routes.dashboard: {e}")
        flash('Erro ao carregar painel.', 'error')
        return render_template('analises/dashboard.html',
                             analises=[], total=0, total_labs=0, tipos=[], por_tipo=[])

@analises_bp.route('/lista')
@login_required
def listar():
    try:
        tipo_id = request.args.get('tipo_id', type=int)
        lista = analises.listar_analises(tipo_id=tipo_id, limite=500)
        return render_template('analises/lista.html', analises=lista,
                               tipos=analises.listar_tipos_analise(), tipo_id=tipo_id)
    except Exception as e:
        logger.error(f"analises_routes.listar: {e}")
        flash('Erro ao carregar analises.', 'error')
        return render_template('analises/lista.html', analises=[], tipos=[], tipo_id=None)

@analises_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id') or None,
                'tipo_id': request.form.get('tipo_id'),
                'laboratorio_id': request.form.get('laboratorio_id') or None,
                'data_coleta': request.form.get('data_coleta') or date.today().isoformat(),
                'data_resultado': request.form.get('data_resultado') or None,
                'numero_protocolo': request.form.get('numero_protocolo'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes'),
                'arquivo_pdf': None,
                'arquivo_original': None
            }

            arquivo = request.files.get('arquivo_pdf')
            if arquivo and arquivo.filename:
                nome_original = os.path.basename(arquivo.filename.replace('\\', '/'))[:255]
                if not nome_original.lower().endswith('.pdf'):
                    flash('O laudo deve ser um arquivo PDF.', 'error')
                else:
                    nome_arquivo = f"laudo_{uuid.uuid4().hex[:12]}.pdf"
                    os.makedirs(_dir_laudos(), exist_ok=True)
                    arquivo.save(os.path.join(_dir_laudos(), nome_arquivo))
                    dados['arquivo_pdf'] = 'laudos/' + nome_arquivo
                    dados['arquivo_original'] = nome_original

            analise_id = analises.inserir_analise(dados)
            if analise_id:
                flash('Analise registrada!', 'success')
                return redirect(url_for('analises.detalhe', id=analise_id))
            else:
                flash('Erro ao registrar.', 'error')
        except Exception as e:
            logger.error(f"analises_routes.nova: {e}")
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        tipos = analises.listar_tipos_analise()
        laboratorios = analises.listar_laboratorios()
        return render_template('analises/nova.html',
                             talhoes=talhoes_lista, tipos=tipos, laboratorios=laboratorios)
    except Exception as e:
        logger.error(f"analises_routes.nova: {e}")
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('analises.listar'))

@analises_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Envia vários laudos em PDF e sugere Solo/Folha/Raiz/Água antes de salvar."""
    if request.method == 'POST':
        from app.modules import talhoes

        arquivos = [a for a in request.files.getlist('arquivos') if a and a.filename]
        if not arquivos:
            flash('Selecione ao menos um PDF.', 'warning')
            return redirect(url_for('analises.upload'))
        if len(arquivos) > MAX_PDFS_POR_LOTE:
            flash(f'Envie no máximo {MAX_PDFS_POR_LOTE} laudos por vez.', 'warning')
            return redirect(url_for('analises.upload'))

        comum = {
            'talhao_id': request.form.get('talhao_id') or None,
            'laboratorio_id': request.form.get('laboratorio_id') or None,
            'data_coleta': request.form.get('data_coleta') or date.today().isoformat(),
            'responsavel': request.form.get('responsavel') or None,
            'numero_protocolo': request.form.get('numero_protocolo') or None,
            'observacoes': request.form.get('observacoes') or None,
        }

        itens = []
        erros = []
        for arquivo in arquivos:
            nome_original = os.path.basename(arquivo.filename.replace('\\', '/'))[:255]
            if not nome_original.lower().endswith('.pdf'):
                erros.append(f'{nome_original}: ignorado — envie apenas PDF.')
                continue
            try:
                arquivo.seek(0, 2)
                tamanho = arquivo.tell()
                arquivo.seek(0)
            except Exception as e:
                logger.error(f"analises_routes.upload (tamanho): {e}")
                erros.append(f'{nome_original}: não foi possível ler o arquivo.')
                continue
            if tamanho == 0 or tamanho > MAX_PDF_BYTES:
                erros.append(f'{nome_original}: PDF vazio ou maior que 25 MB.')
                continue

            nome_temp = f"temp_{uuid.uuid4().hex}.pdf"
            try:
                arquivo.save(os.path.join(_dir_temporarios(), nome_temp))
            except Exception as e:
                logger.error(f"analises_routes.upload (salvar): {e}")
                erros.append(f'{nome_original}: falha ao receber o arquivo.')
                continue

            try:
                dica = analises.extrair_dica_texto_pdf(
                    os.path.join(_dir_temporarios(), nome_temp))
                classificacao = analises.classificar_laudo(nome_original, dica)
            except Exception as e:
                logger.error(f"analises_routes.upload (classificar): {e}")
                classificacao = {'tipo_id': None, 'tipo_nome': 'Outros', 'origem': 'manual'}

            item = dict(comum)
            item.update({
                'nome_original': nome_original,
                'nome_temp': nome_temp,
                'tipo_id': classificacao.get('tipo_id'),
                'tipo_nome': classificacao.get('tipo_nome') or 'Outros',
                'origem': classificacao.get('origem', 'manual'),
            })
            itens.append(item)

        for erro in erros:
            flash(erro, 'warning')
        if not itens:
            return redirect(url_for('analises.upload'))

        _limpar_temporarios(session.pop(CHAVE_SESSAO_UPLOAD, None))
        session[CHAVE_SESSAO_UPLOAD] = itens
        return render_template('analises/upload_revisao.html', itens=itens,
                               tipos=analises.listar_tipos_analise(),
                               talhoes=talhoes.listar_talhoes())

    try:
        from app.modules import talhoes
        return render_template('analises/upload.html',
                               tipos=analises.listar_tipos_analise(),
                               talhoes=talhoes.listar_talhoes(),
                               laboratorios=analises.listar_laboratorios(),
                               hoje=date.today().isoformat())
    except Exception as e:
        logger.error(f"analises_routes.upload: {e}")
        flash('Erro ao abrir o envio de laudos.', 'error')
        return redirect(url_for('analises.listar'))


@analises_bp.route('/upload/confirmar', methods=['POST'])
@login_required
def upload_confirmar():
    itens = session.get(CHAVE_SESSAO_UPLOAD) or []
    if not itens:
        flash('Nenhum laudo aguardando confirmação.', 'warning')
        return redirect(url_for('analises.upload'))

    tipos_validos = {t['id'] for t in analises.listar_tipos_analise()}
    lote = []
    movimentos = []
    for indice, item in enumerate(itens):
        tipo_id = request.form.get(f'tipo_id_{indice}', type=int) or item.get('tipo_id')
        if tipo_id not in tipos_validos:
            tipo_id = item.get('tipo_id')
        nome_final = f"laudo_{uuid.uuid4().hex}.pdf"
        lote.append({
            'talhao_id': request.form.get(f'talhao_id_{indice}', type=int) or None,
            'tipo_id': tipo_id,
            'laboratorio_id': item.get('laboratorio_id'),
            'data_coleta': request.form.get(f'data_coleta_{indice}') or item.get('data_coleta'),
            'responsavel': item.get('responsavel'),
            'numero_protocolo': item.get('numero_protocolo'),
            'observacoes': item.get('observacoes'),
            'arquivo_pdf': 'laudos/' + nome_final,
            'arquivo_original': item.get('nome_original'),
        })
        movimentos.append((item.get('nome_temp'), nome_final))

    try:
        ids = analises.inserir_analises_lote(lote)
    except Exception as e:
        logger.error(f"analises_routes.upload_confirmar: {e}")
        flash('Erro ao salvar os laudos; tente novamente.', 'error')
        return redirect(url_for('analises.upload'))

    falhas = 0
    os.makedirs(_dir_laudos(), exist_ok=True)
    for nome_temp, nome_final in movimentos:
        try:
            os.replace(os.path.join(_dir_temporarios(), nome_temp or ''),
                       os.path.join(_dir_laudos(), nome_final))
        except Exception as e:
            logger.error(f"analises_routes.upload_confirmar (mover PDF): {e}")
            falhas += 1

    session.pop(CHAVE_SESSAO_UPLOAD, None)
    if falhas:
        flash(f'{len(ids)} laudos salvos, mas {falhas} PDF(s) não puderam ser movidos.', 'warning')
    else:
        flash(f'{len(ids)} laudos salvos e classificados!', 'success')
    return redirect(url_for('analises.listar'))


@analises_bp.route('/upload/cancelar', methods=['POST'])
@login_required
def upload_cancelar():
    _limpar_temporarios(session.pop(CHAVE_SESSAO_UPLOAD, None))
    flash('Envio de laudos cancelado.', 'info')
    return redirect(url_for('analises.upload'))


@analises_bp.route('/arquivo/<path:filename>')
@login_required
def arquivo(filename):
    """Serve o laudo PDF da análise a partir da pasta privada de anexos."""
    partes = filename.replace('\\', '/').split('/')
    if not filename.lower().endswith('.pdf') or '..' in partes or '' in partes:
        abort(404)
    try:
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"analises_routes.arquivo: {e}")
        flash('Laudo PDF não encontrado.', 'warning')
        return redirect(url_for('analises.listar'))


@analises_bp.route('/<int:id>')
@login_required
def detalhe(id):
    try:
        analise = analises.buscar_analise_por_id(id)
        if not analise:
            flash('Analise nao encontrada.', 'warning')
            return redirect(url_for('analises.listar'))
        resultados = analises.listar_resultados_por_analise(id)
        parametros = analises.listar_parametros_por_tipo(analise['tipo_id'])
        return render_template('analises/detalhe.html',
                             analise=analise, resultados=resultados, parametros=parametros)
    except Exception as e:
        logger.error(f"analises_routes.detalhe: {e}")
        flash('Erro ao carregar analise.', 'error')
        return redirect(url_for('analises.listar'))

@analises_bp.route('/<int:id>/resultado', methods=['POST'])
@login_required
def adicionar_resultado(id):
    try:
        dados = {
            'analise_id': id,
            'parametro_id': request.form.get('parametro_id'),
            'valor': request.form.get('valor'),
            'interpretacao': request.form.get('interpretacao'),
            'observacoes': request.form.get('observacoes')
        }
        if analises.inserir_resultado(dados):
            analises.atualizar_data_resultado(id)
            flash('Resultado adicionado!', 'success')
        else:
            flash('Erro ao adicionar.', 'error')
    except Exception as e:
        logger.error(f"analises_routes.adicionar_resultado: {e}")
        flash('Erro.', 'error')
    return redirect(url_for('analises.detalhe', id=id))

@analises_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    try:
        sucesso, msg = analises.excluir_analise(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"analises_routes.excluir: {e}")
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('analises.listar'))

@analises_bp.route('/laboratorios')
@login_required
def listar_laboratorios():
    try:
        laboratorios = analises.listar_laboratorios()
        return render_template('analises/laboratorios.html', laboratorios=laboratorios)
    except Exception as e:
        logger.error(f"analises_routes.listar_laboratorios: {e}")
        flash('Erro ao carregar laboratorios.', 'error')
        return render_template('analises/laboratorios.html', laboratorios=[])

@analises_bp.route('/laboratorios/novo', methods=['GET', 'POST'])
@login_required
def novo_laboratorio():
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'responsavel': request.form.get('responsavel'),
                'telefone': request.form.get('telefone'),
                'email': request.form.get('email'),
                'endereco': request.form.get('endereco'),
                'observacoes': request.form.get('observacoes')
            }
            if analises.inserir_laboratorio(dados):
                flash('Laboratorio cadastrado!', 'success')
                return redirect(url_for('analises.listar_laboratorios'))
            else:
                flash('Erro ao cadastrar.', 'error')
        except Exception as e:
            logger.error(f"analises_routes.novo_laboratorio: {e}")
            flash(f'Erro: {e}', 'error')
    return render_template('analises/novo_laboratorio.html')

@analises_bp.route('/laboratorios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_laboratorio(id):
    try:
        sucesso, msg = analises.excluir_laboratorio(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"analises_routes.excluir_laboratorio: {e}")
        flash('Erro.', 'error')
    return redirect(url_for('analises.listar_laboratorios'))

@analises_bp.route('/laboratorios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_laboratorio(id):
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'responsavel': request.form.get('responsavel'),
                'telefone': request.form.get('telefone'),
                'email': request.form.get('email'),
                'endereco': request.form.get('endereco'),
                'observacoes': request.form.get('observacoes')
            }
            if analises.atualizar_laboratorio(id, dados):
                flash('Laboratório atualizado!', 'success')
                return redirect(url_for('analises.listar_laboratorios'))
            else:
                flash('Erro ao atualizar laboratório.', 'error')
        except Exception as e:
            logger.error(f"analises_routes.editar_laboratorio: {e}")
            flash(f'Erro: {e}', 'error')

    try:
        laboratorio = analises.buscar_laboratorio_por_id(id)
        if not laboratorio:
            flash('Laboratório não encontrado.', 'warning')
            return redirect(url_for('analises.listar_laboratorios'))
        return render_template('analises/editar_laboratorio.html', laboratorio=laboratorio)
    except Exception as e:
        logger.error(f"analises_routes.editar_laboratorio: {e}")
        flash('Erro ao carregar laboratório.', 'error')
        return redirect(url_for('analises.listar_laboratorios'))

@analises_bp.route('/parametros')
@login_required
def listar_parametros():
    try:
        tipos = analises.listar_tipos_analise()
        grupos = [{'tipo': t, 'parametros': analises.listar_parametros_por_tipo(t['id'])} for t in tipos]
        return render_template('analises/parametros.html', grupos=grupos)
    except Exception as e:
        logger.error(f"analises_routes.listar_parametros: {e}")
        flash('Erro ao carregar parâmetros.', 'error')
        return render_template('analises/parametros.html', grupos=[])

@analises_bp.route('/parametros/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_parametro(id):
    try:
        sucesso, msg = analises.excluir_parametro(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"analises_routes.excluir_parametro: {e}")
        flash('Erro ao excluir parâmetro.', 'error')
    return redirect(url_for('analises.listar_parametros'))

@analises_bp.route('/tipos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_tipo(id):
    try:
        sucesso, msg = analises.excluir_tipo_analise(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        logger.error(f"analises_routes.excluir_tipo: {e}")
        flash('Erro ao excluir tipo de análise.', 'error')
    return redirect(url_for('analises.listar_parametros'))