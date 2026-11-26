from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.modules import talhoes, mapa
from datetime import datetime
import io
import csv

from app.modules.login_manager import login_required, admin_required
from app.models import get_logger

logger = get_logger(__name__)

talhoes_bp = Blueprint('talhoes', __name__, url_prefix='/talhoes')

@talhoes_bp.route('/')
@login_required
def listar():
    """Lista todos os talhões."""
    try:
        lista_talhoes = talhoes.listar_talhoes()
        dados_mapa = mapa.obter_dados_mapa()
        return render_template('talhoes/lista.html', talhoes=lista_talhoes, dados_mapa=dados_mapa)
    except Exception as e:
        logger.error(f"talhoes_routes.listar: {e}")
        return render_template('talhoes/lista.html', talhoes=[],
                               dados_mapa={'talhoes': [], 'elementos': [], 'importacao': None})


@talhoes_bp.route('/mapa/importar', methods=['POST'])
@login_required
@admin_required
def importar_mapa():
    """Importa camada KML/KMZ exportada do Google Earth."""
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        flash('Selecione um arquivo KML ou KMZ.', 'error')
        return redirect(url_for('talhoes.listar'))
    try:
        sucesso, mensagem, _ = mapa.salvar_mapa(arquivo.filename, arquivo.read())
        if sucesso:
            flash(f'Mapa importado: {mensagem}.', 'success')
        else:
            flash(f'Erro ao importar mapa: {mensagem}', 'error')
    except Exception as e:
        logger.error(f"talhoes_routes.importar_mapa: {e}")
        flash('Erro ao importar mapa.', 'error')
    return redirect(url_for('talhoes.listar'))


@talhoes_bp.route('/mapa/remover', methods=['POST'])
@login_required
@admin_required
def remover_mapa():
    """Desativa a camada importada sem apagar o histórico."""
    try:
        sucesso, mensagem = mapa.desativar_mapa()
        if sucesso:
            flash('Camadas do mapa removidas da visualização.', 'success')
        else:
            flash(f'Erro ao remover camadas: {mensagem}', 'error')
    except Exception as e:
        logger.error(f"talhoes_routes.remover_mapa: {e}")
        flash('Erro ao remover camadas do mapa.', 'error')
    return redirect(url_for('talhoes.listar'))


@talhoes_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    """Cadastra um novo talhão."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': request.form.get('area'),
                'data_plantio': request.form.get('data_plantio'),
                'variedade': request.form.get('variedade'),
                'altitude': request.form.get('altitude'),
                'observacoes': request.form.get('observacoes'),
                'espacamento': request.form.get('espacamento'),
                'latitude': request.form.get('latitude'),
                'longitude': request.form.get('longitude'),
            }
            talhoes.inserir_talhao(dados)
            flash('Talhão cadastrado com sucesso!', 'success')
            return redirect(url_for('talhoes.listar'))
        except Exception as e:
            logger.error(f"talhoes_routes.novo: {e}")
            flash(f'Erro ao cadastrar talhão: {e}', 'error')
            return redirect(url_for('talhoes.novo'))
    return render_template('talhoes/novo.html')

@talhoes_bp.route('/<int:id>')
@login_required
def detalhe(id):
    """Exibe detalhes de um talhão."""
    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhão não encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        historico = talhoes.get_historico_talhao(id)
        return render_template('talhoes/detalhe.html', talhao=talhao, historico=historico, datetime=datetime)
    except Exception as e:
        logger.error(f"talhoes_routes.detalhe: {e}")
        flash('Erro ao carregar detalhes do talhão.', 'error')
        return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Edita um talhão existente."""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form.get('nome'),
                'area': request.form.get('area'),
                'data_plantio': request.form.get('data_plantio'),
                'variedade': request.form.get('variedade'),
                'altitude': request.form.get('altitude'),
                'observacoes': request.form.get('observacoes'),
                'espacamento': request.form.get('espacamento'),
                'latitude': request.form.get('latitude'),
                'longitude': request.form.get('longitude'),
            }
            talhoes.atualizar_talhao(id, dados)
            flash('Talhão atualizado com sucesso!', 'success')
            return redirect(url_for('talhoes.detalhe', id=id))
        except Exception as e:
            logger.error(f"talhoes_routes.editar: {e}")
            flash(f'Erro ao atualizar: {e}', 'error')
    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhão não encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        return render_template('talhoes/editar.html', talhao=talhao)
    except Exception as e:
        logger.error(f"talhoes_routes.editar: {e}")
        flash('Erro ao carregar formulário de edição.', 'error')
        return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir(id):
    """Exclui um talhão (exclusão lógica)."""
    try:
        talhoes.excluir_talhao(id)
        flash('Talhão excluído com sucesso!', 'success')
    except Exception as e:
        logger.error(f"talhoes_routes.excluir: {e}")
        flash('Erro ao excluir talhão.', 'error')
    return redirect(url_for('talhoes.listar'))

@talhoes_bp.route('/exportar-csv')
@login_required
def exportar_csv():
    """Exporta talhões para CSV."""
    try:
        lista = talhoes.listar_talhoes()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Nome', 'Area (ha)', 'Plantio', 'Variedade', 'Altitude', 'Espacamento', 'Pes Cafe', 'Latitude', 'Longitude'])
        for t in lista:
            writer.writerow([
                t.get('id', ''), t.get('nome', ''), t.get('area', 0),
                t.get('data_plantio', ''), t.get('variedade', ''),
                t.get('altitude', ''), t.get('espacamento', ''),
                t.get('pes_cafe', 0), t.get('latitude', ''), t.get('longitude', '')
            ])
        output.seek(0)
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=talhoes_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    except Exception as e:
        logger.error(f"talhoes_routes.exportar_csv: {e}")
        flash('Erro ao exportar CSV.', 'error')
        return redirect(url_for('talhoes.listar'))