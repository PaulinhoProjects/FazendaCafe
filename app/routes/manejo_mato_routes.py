from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules import manejo_mato
from app.modules.login_manager import login_required

manejo_mato_bp = Blueprint('manejo_mato', __name__, url_prefix='/manejo-mato')

@manejo_mato_bp.route('/')
@login_required
def listar():
    try:
        manejos = manejo_mato.listar_manejos()
        return render_template('manejo_mato/lista.html', manejos=manejos)
    except Exception as e:
        flash('Erro ao carregar manejos.', 'error')
        return render_template('manejo_mato/lista.html', manejos=[])

@manejo_mato_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'data_manejo': request.form.get('data_manejo'),
                'tipo_manejo': request.form.get('tipo_manejo'),
                'produtos': request.form.get('produtos'),
                'dosagem': request.form.get('dosagem'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            manejo_id = manejo_mato.inserir_manejo(dados)
            if manejo_id:
                flash('Manejo registrado com sucesso!', 'success')
                return redirect(url_for('manejo_mato.listar'))
            else:
                flash('Erro ao registrar manejo.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        return render_template('manejo_mato/novo.html', talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('manejo_mato.listar'))

@manejo_mato_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'data_manejo': request.form.get('data_manejo'),
                'tipo_manejo': request.form.get('tipo_manejo'),
                'produtos': request.form.get('produtos'),
                'dosagem': request.form.get('dosagem'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            if manejo_mato.atualizar_manejo(id, dados):
                flash('Manejo atualizado!', 'success')
                return redirect(url_for('manejo_mato.listar'))
            else:
                flash('Erro ao atualizar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        manejos = manejo_mato.listar_manejos()
        manejo = None
        for m in manejos:
            if m['id'] == id:
                manejo = m
                break
        if not manejo:
            flash('Manejo nao encontrado.', 'warning')
            return redirect(url_for('manejo_mato.listar'))
        return render_template('manejo_mato/editar.html', manejo=manejo, talhoes=talhoes_lista)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
        return redirect(url_for('manejo_mato.listar'))