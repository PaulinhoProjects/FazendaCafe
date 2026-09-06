from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.modules import talhoes
from datetime import datetime
import io
import csv

try:
    from app.modules.login_manager import login_required, admin_required
except Exception:
    from app.modules.login_manager import login_required
    admin_required = login_required

talhoes_bp = Blueprint('talhoes', __name__, url_prefix='/talhoes')

@talhoes_bp.route('/')
@login_required
def listar():
    """Lista todos os talhões."""
    try:
        lista_talhoes = talhoes.listar_talhoes()
        return render_template('talhoes/lista.html', talhoes=lista_talhoes)
    except Exception as e:
        print(f"Erro ao listar talhões: {e}")
        return render_template('talhoes/lista.html', talhoes=[])

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
            flash(f'Erro ao atualizar: {e}', 'error')
    try:
        talhao = talhoes.buscar_talhao_por_id(id)
        if not talhao:
            flash('Talhão não encontrado.', 'warning')
            return redirect(url_for('talhoes.listar'))
        return render_template('talhoes/editar.html', talhao=talhao)
    except Exception as e:
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
        flash('Erro ao exportar CSV.', 'error')
        return redirect(url_for('talhoes.listar'))