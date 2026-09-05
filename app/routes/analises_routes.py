from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.modules import analises
from app.modules.login_manager import login_required

analises_bp = Blueprint('analises', __name__, url_prefix='/analises')

@analises_bp.route('/')
@login_required
def dashboard():
    try:
        lista = analises.listar_analises()
        laboratorios = analises.listar_laboratorios()
        tipos = analises.listar_tipos_analise()
        return render_template('analises/dashboard.html',
                             analises=lista[:10], total=len(lista),
                             total_labs=len(laboratorios), tipos=tipos)
    except Exception as e:
        flash('Erro ao carregar painel.', 'error')
        return render_template('analises/dashboard.html',
                             analises=[], total=0, total_labs=0, tipos=[])

@analises_bp.route('/lista')
@login_required
def listar():
    try:
        lista = analises.listar_analises()
        return render_template('analises/lista.html', analises=lista)
    except Exception as e:
        flash('Erro ao carregar analises.', 'error')
        return render_template('analises/lista.html', analises=[])

@analises_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': request.form.get('talhao_id'),
                'tipo_id': request.form.get('tipo_id'),
                'laboratorio_id': request.form.get('laboratorio_id') or None,
                'data_coleta': request.form.get('data_coleta'),
                'data_resultado': request.form.get('data_resultado') or None,
                'numero_protocolo': request.form.get('numero_protocolo'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            analise_id = analises.inserir_analise(dados)
            if analise_id:
                flash('Analise registrada!', 'success')
                return redirect(url_for('analises.detalhe', id=analise_id))
            else:
                flash('Erro ao registrar.', 'error')
        except Exception as e:
            flash(f'Erro: {e}', 'error')

    try:
        from app.modules import talhoes
        talhoes_lista = talhoes.listar_talhoes()
        tipos = analises.listar_tipos_analise()
        laboratorios = analises.listar_laboratorios()
        return render_template('analises/nova.html',
                             talhoes=talhoes_lista, tipos=tipos, laboratorios=laboratorios)
    except Exception as e:
        flash('Erro ao carregar formulario.', 'error')
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
        parametros = analises.listar_parametros_por_tipo(analise['tipo_analise_id'])
        return render_template('analises/detalhe.html',
                             analise=analise, resultados=resultados, parametros=parametros)
    except Exception as e:
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
        flash('Erro.', 'error')
    return redirect(url_for('analises.detalhe', id=id))

@analises_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    try:
        sucesso, msg = analises.excluir_analise(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro ao excluir.', 'error')
    return redirect(url_for('analises.listar'))

@analises_bp.route('/laboratorios')
@login_required
def listar_laboratorios():
    try:
        laboratorios = analises.listar_laboratorios()
        return render_template('analises/laboratorios.html', laboratorios=laboratorios)
    except Exception as e:
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
            flash(f'Erro: {e}', 'error')
    return render_template('analises/novo_laboratorio.html')

@analises_bp.route('/laboratorios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_laboratorio(id):
    try:
        sucesso, msg = analises.excluir_laboratorio(id)
        flash(msg, 'success' if sucesso else 'warning')
    except Exception as e:
        flash('Erro.', 'error')
    return redirect(url_for('analises.listar_laboratorios'))