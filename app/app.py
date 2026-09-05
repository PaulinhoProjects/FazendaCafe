"""
Arquivo principal do sistema Fazenda Café
VERSÃO SIMPLES - SEM LOGIN
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sys
import os
import atexit
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file

from werkzeug.utils import secure_filename



app = Flask(__name__)
app.secret_key = 'chave-super-secreta-fazenda-cafe-2026'

# Configurações de upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'analises')
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Adicionar caminhos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config')))

# Importar módulos
from database import (ConexaoBanco, listar_talhoes, buscar_talhao_por_id, 
                     executar_query, inserir_talhao, atualizar_talhao, 
                     excluir_talhao, criar_tabela_talhoes)

from modules.pulverizacao import (
    listar_periodos, listar_receitas, inserir_receita, buscar_receita_por_id,
    listar_aplicacoes, inserir_aplicacao, buscar_aplicacao_por_id,
    listar_pragas_doencas, registrar_ocorrencia, listar_ocorrencias_por_talhao,
    listar_ocorrencias_por_aplicacao, atualizar_aplicacao, excluir_aplicacao,
    atualizar_receita, excluir_receita
)

from modules.estoque import (
    listar_produtos, buscar_produto_por_id, inserir_produto,
    atualizar_produto, excluir_produto, registrar_movimentacao,
    listar_movimentacoes   # sem a função excluir_movimentacao
)

from modules.manejo_mato import (
    listar_manejos, buscar_manejo_por_id, inserir_manejo,
    atualizar_manejo, excluir_manejo
)

from modules.analises import (
    listar_tipos_analise, listar_parametros_por_tipo,
    listar_laboratorios, inserir_laboratorio,
    listar_analises, buscar_analise_por_id, inserir_analise,
    inserir_resultado, listar_resultados_por_analise
)

from modules.adubacao import (
    listar_tipos_adubacao, gerar_recomendacao_automatica,
    inserir_recomendacao, inserir_item_recomendacao,
    listar_recomendacoes, buscar_recomendacao_por_id,
    listar_itens_recomendacao, atualizar_status_recomendacao
)


# Filtro para formatar números sem decimais desnecessários
@app.template_filter('format_quantidade')
def format_quantidade(value):
    """Formata número: 10.0 vira 10, 10.5 continua 10.5"""
    if value is None:
        return '0'
    try:
        # Se for número inteiro (ex: 10.0), mostra sem casas decimais
        if value == int(value):
            return str(int(value))
        # Se tiver casas decimais, mostra com 1 casa (ex: 10.5)
        return f"{value:.1f}".rstrip('0').rstrip('.') if '.' in f"{value:.1f}" else f"{value:.1f}"
    except:
        return str(value)
    
# Inicializar banco de dados
def init_db():
    try:
        if ConexaoBanco.inicializar_pool():
            criar_tabela_talhoes()
            print("Banco de dados inicializado com sucesso!")
            return True
        return False
    except Exception as e:
        print(f"Erro na inicialização: {e}")
        return False

init_db()

@atexit.register
def cleanup():
    print("Fechando conexões com o banco de dados...")
    ConexaoBanco.fechar_pool()

# Configurações de upload - adicione após a configuração existente de UPLOAD_FOLDER
UPLOAD_FOLDER_DEVOLUCOES = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'devolucoes')
app.config['UPLOAD_FOLDER_DEVOLUCOES'] = UPLOAD_FOLDER_DEVOLUCOES
os.makedirs(UPLOAD_FOLDER_DEVOLUCOES, exist_ok=True)

# Configurações de upload (adicione após as existentes)
UPLOAD_FOLDER_NOTAS = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'notas')
app.config['UPLOAD_FOLDER_NOTAS'] = UPLOAD_FOLDER_NOTAS
os.makedirs(UPLOAD_FOLDER_NOTAS, exist_ok=True)

# =====================================================
# ROTAS PRINCIPAIS
# =====================================================

@app.route('/')
def index():
    """Dashboard com gráficos e estatísticas de todos os módulos"""
    try:
        from modules.dashboard import (
            get_resumo_geral, get_atividades_recentes, get_alertas_retorno,
            get_pragas_por_talhao, get_aplicacoes_por_periodo,
            get_aplicacoes_ultimos_6_meses, get_tipos_pragas,
            get_resumo_estoque, get_resumo_analises, get_resumo_pdfs,
            get_produtos_estoque_baixo, get_ultimas_analises, get_ultimos_manejos
        )
        from modules.clima import get_clima_atual, get_previsao
        
        # Resumo geral
        resumo = get_resumo_geral()
        atividades = get_atividades_recentes(8)
        alertas = get_alertas_retorno()
        
        # Gráficos
        grafico_pragas_talhao = get_pragas_por_talhao()
        grafico_aplicacoes_periodo = get_aplicacoes_por_periodo()
        grafico_tendencia = get_aplicacoes_ultimos_6_meses()
        grafico_tipos_pragas = get_tipos_pragas()
        
        # Resumos
        resumo_estoque = get_resumo_estoque()
        resumo_analises = get_resumo_analises()
        resumo_pdfs = get_resumo_pdfs()
        
        # Listas
        produtos_baixo = get_produtos_estoque_baixo(5)
        ultimas_analises = get_ultimas_analises(3)
        ultimos_manejos = get_ultimos_manejos(3)
        
        # Clima
        clima_atual = get_clima_atual()
        previsao = get_previsao()
        
        return render_template('dashboard.html',
                             resumo=resumo,
                             atividades=atividades,
                             alertas=alertas,
                             grafico_pragas_talhao=grafico_pragas_talhao,
                             grafico_aplicacoes_periodo=grafico_aplicacoes_periodo,
                             grafico_tendencia=grafico_tendencia,
                             grafico_tipos_pragas=grafico_tipos_pragas,
                             resumo_estoque=resumo_estoque,
                             resumo_analises=resumo_analises,
                             resumo_pdfs=resumo_pdfs,
                             produtos_baixo=produtos_baixo,
                             ultimas_analises=ultimas_analises,
                             ultimos_manejos=ultimos_manejos,
                             clima_atual=clima_atual,
                             previsao=previsao,
                             data_atual=datetime.now().strftime('%d/%m/%Y'))
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro ao carregar dashboard: {e}"

# =====================================================
# ROTAS DE TALHÕES (ATUALIZADAS COM ESPAÇAMENTO)
# =====================================================

@app.route('/talhoes')
def listar_talhoes_route():
    talhoes = listar_talhoes()
    return render_template('talhoes/lista.html', talhoes=talhoes)

@app.route('/talhao/<int:id>')
def ver_talhao(id):
    talhao = buscar_talhao_por_id(id)
    if talhao:
        from datetime import datetime
        return render_template('talhoes/detalhe.html', talhao=talhao, datetime=datetime)
    return "Talhão não encontrado", 404

@app.route('/talhao/novo', methods=['GET', 'POST'])
def novo_talhao():  # ← APENAS UMA
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'area': float(request.form['area']),
                'data_plantio': request.form.get('data_plantio') or None,
                'variedade': request.form.get('variedade', ''),
                'altitude': float(request.form['altitude']) if request.form.get('altitude') else None,
                'observacoes': request.form.get('observacoes', ''),
                'espacamento': request.form.get('espacamento')
            }
            novo_id = inserir_talhao(dados)
            if novo_id:
                return redirect(url_for('ver_talhao', id=novo_id))
            return "Erro ao criar talhão", 500
        except Exception as e:
            return f"Erro: {e}"
    
    return render_template('talhoes/novo.html')

@app.route('/talhao/<int:id>/editar', methods=['GET', 'POST'])
def editar_talhao(id):  # ← APENAS UMA
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'area': float(request.form['area']),
                'data_plantio': request.form.get('data_plantio') or None,
                'variedade': request.form.get('variedade', ''),
                'altitude': float(request.form['altitude']) if request.form.get('altitude') else None,
                'observacoes': request.form.get('observacoes', ''),
                'espacamento': request.form.get('espacamento')
            }
            if atualizar_talhao(id, dados):
                return redirect(url_for('ver_talhao', id=id))
            return "Erro ao atualizar", 500
        except Exception as e:
            return f"Erro: {e}"
    
    talhao = buscar_talhao_por_id(id)
    return render_template('talhoes/editar.html', talhao=talhao)

@app.route('/talhao/<int:id>/excluir')
def excluir_talhao_route(id):
    if excluir_talhao(id):
        return redirect(url_for('listar_talhoes_route'))
    return "Erro ao excluir", 500

@app.route('/talhoes/pdf')
def exportar_talhoes_pdf():
    """Exporta lista de talhões para PDF"""
    from database import listar_talhoes, gerar_pdf_talhoes
    
    talhoes = listar_talhoes()
    pdf_file = gerar_pdf_talhoes(talhoes)
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'talhoes_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    )

# =====================================================
# ROTAS DE PULVERIZAÇÃO
# =====================================================

@app.route('/pulverizacao')
def pulverizacao_index():
    aplicacoes = listar_aplicacoes()[:10]  # Já limitado a 10
    periodos = listar_periodos()
    pragas = listar_pragas_doencas()
    return render_template('pulverizacao/index.html',
                         aplicacoes=aplicacoes,
                         periodos=periodos,
                         pragas=pragas)

@app.route('/pulverizacao/aplicacoes')
def listar_todas_aplicacoes():
    """Lista todas as pulverizações realizadas"""
    from datetime import datetime, date
    from modules.pulverizacao import listar_aplicacoes
    
    aplicacoes = listar_aplicacoes()
    
    # Formatar datas para string ISO (YYYY-MM-DD) para facilitar no template
    for app in aplicacoes:
        # Converter data_aplicacao
        if hasattr(app['data_aplicacao'], 'strftime'):
            app['data_aplicacao_str'] = app['data_aplicacao'].strftime('%Y-%m-%d')
            app['mes'] = app['data_aplicacao'].strftime('%m')
            app['ano'] = app['data_aplicacao'].strftime('%Y')
        else:
            app['data_aplicacao_str'] = app['data_aplicacao']
            app['mes'] = app['data_aplicacao'][5:7] if len(app['data_aplicacao']) >= 7 else ''
            app['ano'] = app['data_aplicacao'][:4] if len(app['data_aplicacao']) >= 4 else ''
        
        # Converter data_retorno para string se for date object
        if 'data_retorno' in app and app['data_retorno']:
            if hasattr(app['data_retorno'], 'strftime'):
                app['data_retorno_str'] = app['data_retorno'].strftime('%Y-%m-%d')
            else:
                app['data_retorno_str'] = app['data_retorno']
        else:
            app['data_retorno_str'] = None
    
    # Data atual para comparação de retornos
    data_atual = date.today()  # ← Isso retorna um objeto date
    
    return render_template('pulverizacao/aplicacoes.html', 
                         aplicacoes=aplicacoes,
                         data_atual=data_atual)  # ← ISSO É ESSENCIAL!

@app.route('/pulverizacao/aplicacao/<int:id>')
def ver_aplicacao(id):
    aplicacao = buscar_aplicacao_por_id(id)
    pragas = listar_ocorrencias_por_aplicacao(id)
    if aplicacao:
        return render_template('pulverizacao/detalhe_aplicacao.html',
                             aplicacao=aplicacao,
                             pragas=pragas)
    return "Aplicação não encontrada", 404

@app.route('/pulverizacao/nova', methods=['GET', 'POST'])
def nova_pulverizacao():
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': int(request.form['talhao_id']),
                'periodo_id': int(request.form['periodo_id']),
                'receita_id': int(request.form['receita_id']) if request.form.get('receita_id') else None,
                'data_aplicacao': request.form['data_aplicacao'],
                'data_retorno': request.form.get('data_retorno') or None,
                'responsavel': request.form.get('responsavel', ''),
                'condicoes': request.form.get('condicoes', ''),
                'observacoes': request.form.get('observacoes', ''),
                'tipo_aplicacao': request.form.get('tipo_aplicacao', 'Foliar'),
            }
            
            nova_id = inserir_aplicacao(dados)
            if not nova_id:
                return "Erro ao inserir aplicação", 500
            
            pragas_ids = request.form.getlist('pragas_detectadas')
            for praga_id in pragas_ids:
                nivel = request.form.get(f'nivel_{praga_id}', 'medio')
                ocorrencia = {
                    'talhao_id': dados['talhao_id'],
                    'praga_id': int(praga_id),
                    'aplicacao_id': nova_id,
                    'data_deteccao': dados['data_aplicacao'],
                    'nivel': nivel,
                    'tratado': True,
                    'observacoes': "Registrado durante pulverização"
                }
                registrar_ocorrencia(ocorrencia)
            
            return redirect(url_for('ver_aplicacao', id=nova_id))
            
        except Exception as e:
            return f"Erro ao processar: {str(e)}", 500
    
    talhoes = listar_talhoes()
    periodos = listar_periodos()
    receitas = listar_receitas()
    pragas = listar_pragas_doencas()
    data_atual = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('pulverizacao/nova_pulverizacao.html',
                         talhoes=talhoes,
                         periodos=periodos,
                         receitas=receitas,
                         pragas=pragas,
                         data_atual=data_atual)

# =====================================================
# ROTAS PARA EDITAR/EXCLUIR APLICAÇÕES
# =====================================================

@app.route('/pulverizacao/aplicacao/<int:id>/editar', methods=['GET', 'POST'])
def editar_aplicacao(id):
    """Editar uma aplicação existente"""
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': int(request.form['talhao_id']),
                'periodo_id': int(request.form['periodo_id']),
                'receita_id': int(request.form['receita_id']) if request.form.get('receita_id') else None,
                'data_aplicacao': request.form['data_aplicacao'],
                'data_retorno': request.form.get('data_retorno') or None,
                'responsavel': request.form.get('responsavel', ''),
                'condicoes': request.form.get('condicoes', ''),
                'observacoes': request.form.get('observacoes', '')
            }
            
            if atualizar_aplicacao(id, dados):
                return redirect(url_for('ver_aplicacao', id=id))
            else:
                return "Erro ao atualizar aplicação", 500
        except Exception as e:
            return f"Erro: {e}"
    
    # GET: mostrar formulário preenchido
    aplicacao = buscar_aplicacao_por_id(id)
    if not aplicacao:
        return "Aplicação não encontrada", 404
    
    talhoes = listar_talhoes()
    periodos = listar_periodos()
    receitas = listar_receitas()
    pragas = listar_pragas_doencas()
    
    return render_template('pulverizacao/editar_aplicacao.html',
                         aplicacao=aplicacao,
                         talhoes=talhoes,
                         periodos=periodos,
                         receitas=receitas,
                         pragas=pragas,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))


# =====================================================
# ROTAS PARA EDITAR/EXCLUIR RECEITAS
# =====================================================

@app.route('/pulverizacao/receita/<int:id>/editar', methods=['GET', 'POST'])
def editar_receita(id):
    """Editar uma receita existente"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'periodo_id': int(request.form['periodo_id']),
                'descricao': request.form.get('descricao', ''),
                'formula': request.form['formula'],
                'produtos': request.form.get('produtos', ''),
                'observacoes': request.form.get('observacoes', '')
            }
            if atualizar_receita(id, dados):
                return redirect(url_for('listar_receitas_route'))
            else:
                return "Erro ao atualizar receita", 500
        except Exception as e:
            return f"Erro: {e}"
    
    receita = buscar_receita_por_id(id)
    if not receita:
        return "Receita não encontrada", 404
    
    periodos = listar_periodos()
    return render_template('pulverizacao/editar_receita.html', receita=receita, periodos=periodos)


@app.route('/pulverizacao/receitas')
def listar_receitas_route():
    receitas = listar_receitas()
    periodos = {p['id']: p['nome'] for p in listar_periodos()}
    return render_template('pulverizacao/receitas.html', receitas=receitas, periodos=periodos)

@app.route('/pulverizacao/receita/nova', methods=['GET', 'POST'])
def nova_receita():
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'periodo_id': int(request.form['periodo_id']),
                'descricao': request.form['descricao'],
                'formula': request.form['formula'],
                'produtos': request.form['produtos'],
                'observacoes': request.form['observacoes']
            }
            nova_id = inserir_receita(dados)
            if nova_id:
                return redirect(url_for('listar_receitas_route'))
            return "Erro ao criar receita", 500
        except Exception as e:
            return f"Erro: {e}"
    
    periodos = listar_periodos()
    return render_template('pulverizacao/nova_receita.html', periodos=periodos)

@app.route('/talhao/<int:id>/pulverizacoes')
def historico_pulverizacoes_talhao(id):
    talhao = buscar_talhao_por_id(id)
    aplicacoes = listar_aplicacoes(talhao_id=id)
    ocorrencias = listar_ocorrencias_por_talhao(id)
    return render_template('talhoes/pulverizacoes.html',
                         talhao=talhao,
                         aplicacoes=aplicacoes,
                         ocorrencias=ocorrencias)

# =====================================================
# ROTAS DE MANEJO DO MATO
# =====================================================

@app.route('/manejo-mato')
def manejo_mato_index():
    """Página inicial do módulo de manejo do mato"""
    manejos_recentes = listar_manejos()[:10]
    return render_template('manejo_mato/index.html', manejos=manejos_recentes)

@app.route('/manejo-mato/lista')
def listar_todos_manejos():
    """Lista completa de manejos"""
    manejos = listar_manejos()
    return render_template('manejo_mato/lista.html', manejos=manejos)

@app.route('/manejo-mato/novo', methods=['GET', 'POST'])
def novo_manejo():
    """Registrar um novo manejo"""
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': int(request.form['talhao_id']),
                'data_manejo': request.form['data_manejo'],
                'tipo_manejo': request.form['tipo_manejo'],
                'produtos': request.form.get('produtos'),
                'dosagem': request.form.get('dosagem'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            novo_id = inserir_manejo(dados)
            if novo_id:
                return redirect(url_for('ver_manejo', id=novo_id))
            else:
                return "Erro ao registrar manejo", 500
        except Exception as e:
            return f"Erro: {e}"

    talhoes = listar_talhoes()
    return render_template('manejo_mato/novo.html', talhoes=talhoes, data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/manejo-mato/<int:id>')
def ver_manejo(id):
    """Detalhes de um manejo"""
    manejo = buscar_manejo_por_id(id)
    if manejo:
        return render_template('manejo_mato/detalhe.html', manejo=manejo)
    return "Manejo não encontrado", 404

@app.route('/manejo-mato/<int:id>/editar', methods=['GET', 'POST'])
def editar_manejo(id):
    """Editar um manejo"""
    if request.method == 'POST':
        try:
            dados = {
                'talhao_id': int(request.form['talhao_id']),
                'data_manejo': request.form['data_manejo'],
                'tipo_manejo': request.form['tipo_manejo'],
                'produtos': request.form.get('produtos'),
                'dosagem': request.form.get('dosagem'),
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            if atualizar_manejo(id, dados):
                return redirect(url_for('ver_manejo', id=id))
            else:
                return "Erro ao atualizar", 500
        except Exception as e:
            return f"Erro: {e}"

    manejo = buscar_manejo_por_id(id)
    talhoes = listar_talhoes()
    return render_template('manejo_mato/editar.html', manejo=manejo, talhoes=talhoes)


# Rota para ver manejos de um talhão específico
@app.route('/talhao/<int:id>/manejos')
def manejos_por_talhao(id):
    """Lista manejos de um talhão"""
    talhao = buscar_talhao_por_id(id)
    manejos = listar_manejos(talhao_id=id)
    return render_template('talhoes/manejos.html', talhao=talhao, manejos=manejos)

# =====================================================
# ROTAS DE ESTOQUE
# =====================================================
from modules.estoque import (
    listar_produtos, buscar_produto_por_id, inserir_produto,
    atualizar_produto, excluir_produto, registrar_movimentacao,
    listar_movimentacoes,
)

@app.route('/estoque')
def estoque_index():
    from modules.estoque import listar_produtos, listar_movimentacoes, get_resumo_estoque
    
    produtos = listar_produtos()
    alertas = [p for p in produtos if p.get('estoque_baixo')]
    movimentacoes_recentes = listar_movimentacoes()[:10]
    resumo = get_resumo_estoque()
    
    return render_template('estoque/index.html', 
                         produtos=produtos[:8], 
                         alertas=alertas,
                         movimentacoes=movimentacoes_recentes,
                         resumo=resumo)

@app.route('/estoque/produtos')
def estoque_listar_produtos():
    produtos = listar_produtos()
    return render_template('estoque/produtos.html', produtos=produtos)

@app.route('/estoque/produto/novo', methods=['GET', 'POST'])
def estoque_novo_produto():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            unidade = request.form.get('unidade')
            estoque_minimo = request.form.get('estoque_minimo')
            observacoes = request.form.get('observacoes')
            if not nome or not unidade:
                return "Nome e unidade são obrigatórios", 400
            try:
                estoque_minimo = float(estoque_minimo) if estoque_minimo else None
            except ValueError:
                return "Estoque mínimo deve ser um número", 400
            dados = {
                'nome': nome,
                'unidade': unidade,
                'estoque_minimo': estoque_minimo,
                'quantidade_atual': 0,
                'observacoes': observacoes
            }
            novo_id = inserir_produto(dados)
            if novo_id:
                return redirect(url_for('estoque_ver_produto', id=novo_id))
            return "Erro ao cadastrar produto", 500
        except Exception as e:
            return f"Erro: {e}"
    return render_template('estoque/novo_produto.html')

@app.route('/estoque/produto/<int:id>')
def estoque_ver_produto(id):
    produto = buscar_produto_por_id(id)
    if not produto:
        return "Produto não encontrado", 404
    movimentacoes = listar_movimentacoes(produto_id=id)
    return render_template('estoque/detalhe_produto.html', produto=produto, movimentacoes=movimentacoes)

@app.route('/estoque/produto/<int:id>/editar', methods=['GET', 'POST'])
def estoque_editar_produto(id):
    from modules.estoque import buscar_produto_por_id, atualizar_produto
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            unidade = request.form.get('unidade')
            categoria = request.form.get('categoria')  # <-- ADICIONADO
            estoque_minimo = request.form.get('estoque_minimo')
            quantidade_atual = request.form.get('quantidade_atual')
            observacoes = request.form.get('observacoes')
            
            if not nome or not unidade:
                return "Nome e unidade são obrigatórios", 400
            
            try:
                estoque_minimo = float(estoque_minimo) if estoque_minimo else None
                quantidade_atual = float(quantidade_atual) if quantidade_atual else 0
            except ValueError:
                return "Valores numéricos inválidos", 400
            
            dados = {
                'nome': nome,
                'unidade': unidade,
                'categoria': categoria,  # <-- ADICIONADO
                'estoque_minimo': estoque_minimo,
                'quantidade_atual': quantidade_atual,
                'observacoes': observacoes
            }
            
            if atualizar_produto(id, dados):
                return redirect(url_for('estoque_ver_produto', id=id))
            return "Erro ao atualizar", 500
        except Exception as e:
            return f"Erro: {e}"
    
    produto = buscar_produto_por_id(id)
    if not produto:
        return "Produto não encontrado", 404
    
    return render_template('estoque/editar_produto.html', produto=produto)

@app.route('/estoque/produto/<int:id>/excluir', methods=['POST'])
def estoque_excluir_produto(id):
    if excluir_produto(id):
        return redirect(url_for('estoque_listar_produtos'))
    return "Erro ao excluir", 500

@app.route('/estoque/movimentacao/nova', methods=['GET', 'POST'])
def estoque_nova_movimentacao():
    if request.method == 'POST':
        try:
            produto_id = request.form.get('produto_id')
            tipo = request.form.get('tipo')
            quantidade = request.form.get('quantidade')
            data_movimento = request.form.get('data_movimento')
            unidade = request.form.get('unidade', '')
            valor_unitario = request.form.get('valor_unitario')
            observacoes = request.form.get('observacoes', '')
            if not produto_id or not tipo or not quantidade or not data_movimento:
                return "Campos obrigatórios não preenchidos", 400
            try:
                produto_id = int(produto_id)
                quantidade = float(quantidade)
                valor = float(valor_unitario) if valor_unitario else None
            except ValueError:
                return "Valores numéricos inválidos", 400
            dados = {
                'produto_id': produto_id,
                'tipo': tipo,
                'quantidade': quantidade,
                'unidade': unidade,
                'data_movimento': data_movimento,
                'valor_unitario': valor,
                'observacoes': observacoes
            }
            nova_id = registrar_movimentacao(dados)
            if nova_id:
                return redirect(url_for('estoque_ver_produto', id=produto_id))
            return "Erro ao registrar movimentação", 500
        except Exception as e:
            return f"Erro: {e}"
    # GET
    tipo = request.args.get('tipo', 'entrada')
    produtos = listar_produtos()
    return render_template('estoque/nova_movimentacao.html', produtos=produtos, tipo=tipo, data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/estoque/movimentacoes')
def estoque_listar_movimentacoes():
    movimentacoes = listar_movimentacoes()
    return render_template('estoque/movimentacoes.html', movimentacoes=movimentacoes)

@app.route('/estoque/movimentacao/<int:id>/editar', methods=['GET', 'POST'])
def editar_movimentacao(id):
    from modules.estoque import buscar_movimentacao_por_id, atualizar_movimentacao, listar_produtos
    
    mov = buscar_movimentacao_por_id(id)
    if not mov:
        return "Movimentação não encontrada", 404
    
    # Se o produto foi removido, não permite editar (a menos que você queira permitir)
    if not mov.get('produto_ativo'):
        return redirect(url_for('estoque_listar_movimentacoes'))
    
    if request.method == 'POST':
        try:
            dados = {
                'produto_id': int(request.form['produto_id']),
                'tipo': request.form['tipo'],
                'quantidade': float(request.form['quantidade']),
                'unidade': request.form.get('unidade'),
                'data_movimento': request.form['data_movimento'],
                'valor_unitario': float(request.form['valor_unitario']) if request.form.get('valor_unitario') else None,
                'observacoes': request.form.get('observacoes')
            }
            if atualizar_movimentacao(id, dados):
                return redirect(url_for('estoque_ver_produto', id=dados['produto_id']))
            return "Erro ao atualizar", 500
        except Exception as e:
            return f"Erro: {e}"
    
    produtos = listar_produtos()
    return render_template('estoque/editar_movimentacao.html', mov=mov, produtos=produtos)

@app.route('/estoque/relatorio', methods=['GET', 'POST'])
def relatorio_estoque():
    from modules.estoque import listar_movimentacoes_por_periodo
    
    if request.method == 'POST':
        data_inicio = request.form['data_inicio']
        data_fim = request.form['data_fim']
        movimentacoes = listar_movimentacoes_por_periodo(data_inicio, data_fim)
        return render_template('estoque/relatorio.html', 
                             movimentacoes=movimentacoes, 
                             data_inicio=data_inicio, 
                             data_fim=data_fim)
    
    return render_template('estoque/relatorio.html')

@app.route('/estoque/relatorio-produtos')
def relatorio_produtos():
    """Relatório completo de produtos em estoque"""
    from modules.estoque import listar_produtos
    produtos = listar_produtos()
    
    # Calcular totais
    total_produtos = len(produtos)
    valor_total = sum(p['quantidade_atual'] * p.get('ultimo_valor', 0) for p in produtos if p.get('ultimo_valor'))
    total_itens = sum(p['quantidade_atual'] for p in produtos)
    
    return render_template('estoque/relatorio_produtos.html',
                         produtos=produtos,
                         total_produtos=total_produtos,
                         valor_total=valor_total,
                         total_itens=total_itens,
                         data_atual=datetime.now().strftime('%d/%m/%Y'))


@app.route('/estoque/relatorio-produtos-simples')
def relatorio_produtos_simples():
    """Relatório super simples de produtos"""
    from modules.estoque import listar_produtos
    produtos = listar_produtos()
    return render_template('estoque/relatorio_produtos_simples.html', produtos=produtos)

@app.route('/estoque/relatorio-produtos/filtros', methods=['GET', 'POST'])
def relatorio_produtos_com_filtros():
    """Relatório de produtos com filtros por categoria e status"""
    from modules.estoque import listar_produtos, gerar_pdf_produtos
    
    if request.method == 'POST':
        # Pegar filtros do formulário
        categoria = request.form.get('categoria')
        status = request.form.get('status')
        termo = request.form.get('termo', '').lower()
        
        # Buscar todos os produtos
        todos_produtos = listar_produtos()
        produtos_filtrados = []
        
        for p in todos_produtos:
            # Filtro por categoria
            if categoria and categoria != 'todas' and p.get('categoria') != categoria:
                continue
            
            # Filtro por status
            if status == 'baixo' and not p.get('estoque_baixo'):
                continue
            if status == 'normal' and p.get('estoque_baixo'):
                continue
            
            # Filtro por nome (busca parcial)
            if termo and termo not in p['nome'].lower():
                continue
            
            produtos_filtrados.append(p)
        
        # Se não houver produtos após filtros
        if not produtos_filtrados:
            flash('Nenhum produto encontrado com os filtros selecionados', 'warning')
            return redirect(url_for('relatorio_produtos_com_filtros'))
        
        # Gerar PDF
        pdf_file = gerar_pdf_produtos(produtos_filtrados)
        
        # Nome do arquivo com filtros aplicados
        nome_base = 'produtos'
        if categoria and categoria != 'todas':
            nome_base += f'_{categoria.lower().replace(" ", "_")}'
        if status and status != 'todos':
            nome_base += f'_{status}'
        if termo:
            # Limitar tamanho do termo no nome do arquivo
            termo_curto = termo[:20].replace(' ', '_')
            nome_base += f'_{termo_curto}'
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{nome_base}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        )
    
    # GET - mostrar página com filtros
    from modules.estoque import listar_produtos
    todos_produtos = listar_produtos()
    
    # Extrair categorias únicas (ignorando None/vazio)
    categorias = sorted(list(set([
        p['categoria'] for p in todos_produtos 
        if p.get('categoria') and p['categoria'].strip()
    ])))
    
    # Contar produtos por categoria para mostrar estatísticas
    stats = {
        'total': len(todos_produtos),
        'baixo': sum(1 for p in todos_produtos if p.get('estoque_baixo')),
        'categorias': len(categorias)
    }
    
    return render_template('estoque/relatorio_produtos_filtros.html',
                         categorias=categorias,
                         stats=stats)

# =====================================================
# ROTAS PARA EXPORTAÇÃO DE RELATÓRIOS
# =====================================================

@app.route('/estoque/relatorio-produtos/excel')
def exportar_produtos_excel():
    """Exporta lista de produtos para Excel"""
    from modules.estoque import listar_produtos, gerar_excel_produtos
    
    produtos = listar_produtos()
    excel_file = gerar_excel_produtos(produtos)
    
    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'produtos_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    )

@app.route('/estoque/relatorio-produtos/pdf')
def exportar_produtos_pdf():
    """Exporta lista de produtos para PDF"""
    from modules.estoque import listar_produtos, gerar_pdf_produtos
    
    produtos = listar_produtos()
    pdf_file = gerar_pdf_produtos(produtos)
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'produtos_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    )

@app.route('/estoque/relatorio-movimentacoes/excel', methods=['POST'])
def exportar_movimentacoes_excel():
    """Exporta movimentações do período para Excel"""
    from modules.estoque import listar_movimentacoes_por_periodo, gerar_excel_movimentacoes
    
    data_inicio = request.form.get('data_inicio')
    data_fim = request.form.get('data_fim')
    
    if not data_inicio or not data_fim:
        return "Período não informado", 400
    
    movimentacoes = listar_movimentacoes_por_periodo(data_inicio, data_fim)
    excel_file = gerar_excel_movimentacoes(movimentacoes, data_inicio, data_fim)
    
    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'movimentacoes_{data_inicio}_a_{data_fim}.xlsx'
    )

@app.route('/estoque/relatorio-movimentacoes/pdf', methods=['POST'])
def exportar_movimentacoes_pdf():
    """Exporta movimentações do período para PDF"""
    from modules.estoque import listar_movimentacoes_por_periodo, gerar_pdf_movimentacoes
    
    data_inicio = request.form.get('data_inicio')
    data_fim = request.form.get('data_fim')
    
    if not data_inicio or not data_fim:
        return "Período não informado", 400
    
    movimentacoes = listar_movimentacoes_por_periodo(data_inicio, data_fim)
    pdf_file = gerar_pdf_movimentacoes(movimentacoes, data_inicio, data_fim)
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'movimentacoes_{data_inicio}_a_{data_fim}.pdf'
    )

# =====================================================
# ROTAS DO MÓDULO DE ANÁLISES
# =====================================================

@app.route('/analises')
def analises_index():
    """Página inicial do módulo de análises"""
    from modules.analises import listar_analises
    analises_recentes = listar_analises()[:10]
    return render_template('analises/index.html', analises=analises_recentes)

@app.route('/analises/lista')
def listar_todas_analises():
    """Lista todas as análises"""
    from modules.analises import listar_analises
    analises = listar_analises()
    return render_template('analises/lista.html', analises=analises)

@app.route('/analises/nova', methods=['GET', 'POST'])
def nova_analise():
    """Registrar uma nova análise com opção de PDF"""
    from modules.analises import listar_tipos_analise, listar_laboratorios, inserir_analise
    from database import listar_talhoes
    
    if request.method == 'POST':
        try:
            # Tratar campos que podem vir vazios
            laboratorio_id = request.form.get('laboratorio_id')
            data_resultado = request.form.get('data_resultado')
            numero_protocolo = request.form.get('numero_protocolo')
            responsavel = request.form.get('responsavel')
            observacoes = request.form.get('observacoes')
            
            # Processar upload do PDF
            import time
            arquivo_pdf = None
            pdf_opcao = request.form.get('pdf_opcao', 'novo')
            
            if pdf_opcao == 'novo' and 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    nome_unico = f"{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_unico))
                    arquivo_pdf = nome_unico
            elif pdf_opcao == 'existente':
                arquivo_pdf = request.form.get('pdf_existente')
            
            # Montar dicionário de dados
            dados = {
                'talhao_id': int(request.form['talhao_id']),
                'tipo_id': int(request.form['tipo_id']),
                'laboratorio_id': int(laboratorio_id) if laboratorio_id else None,
                'data_coleta': request.form['data_coleta'],
                'data_resultado': data_resultado if data_resultado else None,
                'numero_protocolo': numero_protocolo if numero_protocolo else None,
                'responsavel': responsavel if responsavel else None,
                'observacoes': observacoes if observacoes else None,
                'arquivo_pdf': arquivo_pdf
            }
            
            nova_id = inserir_analise(dados)
            if nova_id:
                return redirect(url_for('ver_analise', id=nova_id))
            return "Erro ao registrar análise", 500
            
        except Exception as e:
            print(f"Erro detalhado: {e}")
            import traceback
            traceback.print_exc()
            return f"Erro: {str(e)}", 500
    
    # GET - exibir formulário
    talhoes = listar_talhoes()
    if talhoes is None:
        talhoes = []
    
    tipos = listar_tipos_analise()
    if tipos is None:
        tipos = []
    
    laboratorios = listar_laboratorios()
    if laboratorios is None:
        laboratorios = []
    
    tipo_selecionado = request.args.get('tipo')
    
    # Listar PDFs existentes para opção de reutilizar
    pdfs_existentes = []
    import os
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        pdfs_existentes = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.pdf')]
    
    return render_template('analises/nova_analise.html',
                         talhoes=talhoes,
                         tipos=tipos,
                         laboratorios=laboratorios,
                         tipo_selecionado=tipo_selecionado,
                         data_atual=datetime.now().strftime('%Y-%m-%d'),
                         pdfs_existentes=pdfs_existentes)


@app.route('/analises/<int:id>')
def ver_analise(id):
    """Detalhes de uma análise com resultados"""
    from modules.analises import buscar_analise_por_id, listar_resultados_por_analise
    
    analise = buscar_analise_por_id(id)
    if not analise:
        return "Análise não encontrada", 404
    
    resultados = listar_resultados_por_analise(id)
    return render_template('analises/detalhe_analise.html',
                         analise=analise,
                         resultados=resultados)

@app.route('/analises/<int:id>/resultados/novo', methods=['GET', 'POST'])
def adicionar_resultados(id):
    from modules.analises import (
        buscar_analise_por_id, listar_parametros_por_tipo,
        inserir_resultado, listar_resultados_por_analise,
        atualizar_data_resultado  # <-- NOVA IMPORTAÇÃO
    )
    
    analise = buscar_analise_por_id(id)
    if not analise:
        return "Análise não encontrada", 404
    
    if request.method == 'POST':
        try:
            # Processar cada parâmetro enviado
            parametros = request.form.getlist('parametro_id')
            for i, param_id in enumerate(parametros):
                valor = request.form.get(f'valor_{param_id}')
                if valor:  # só insere se tiver valor
                    dados = {
                        'analise_id': id,
                        'parametro_id': int(param_id),
                        'valor': float(valor) if valor else None,
                        'interpretacao': request.form.get(f'interpretacao_{param_id}'),
                        'observacoes': request.form.get(f'obs_{param_id}')
                    }
                    inserir_resultado(dados)
            
            # Atualizar data do resultado
            atualizar_data_resultado(id)
            
            return redirect(url_for('ver_analise', id=id))
        except Exception as e:
            return f"Erro ao salvar resultados: {e}"
    
    # GET - exibir formulário de resultados
    parametros = listar_parametros_por_tipo(analise['tipo_id'])
    resultados_existentes = listar_resultados_por_analise(id)
    
    # Marcar quais já foram preenchidos
    ids_preenchidos = [r['id'] for r in resultados_existentes]
    
    return render_template('analises/resultados.html',
                         analise=analise,
                         parametros=parametros,
                         resultados_existentes=resultados_existentes,
                         ids_preenchidos=ids_preenchidos)

# =====================================================
# ROTAS PARA LABORATÓRIOS
# =====================================================

@app.route('/analises/laboratorios')
def listar_laboratorios_route():
    """Lista todos os laboratórios"""
    from modules.analises import listar_laboratorios
    laboratorios = listar_laboratorios()
    return render_template('analises/laboratorios.html', laboratorios=laboratorios)

@app.route('/analises/laboratorio/novo', methods=['GET', 'POST'])
def novo_laboratorio():
    """Cadastrar novo laboratório"""
    from modules.analises import inserir_laboratorio
    
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'responsavel': request.form.get('responsavel'),
                'telefone': request.form.get('telefone'),
                'email': request.form.get('email'),
                'endereco': request.form.get('endereco'),
                'observacoes': request.form.get('observacoes')
            }
            novo_id = inserir_laboratorio(dados)
            if novo_id:
                return redirect(url_for('listar_laboratorios_route'))
            return "Erro ao cadastrar", 500
        except Exception as e:
            return f"Erro: {e}"
    
    return render_template('analises/novo_laboratorio.html')

# =====================================================
# ROTAS PARA EXCLUIR LABORATÓRIOS E ANÁLISES
# =====================================================

@app.route('/analises/laboratorio/<int:id>/editar', methods=['GET', 'POST'])
def editar_laboratorio(id):
    """Editar um laboratório"""
    from modules.analises import buscar_laboratorio_por_id, atualizar_laboratorio
    
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'responsavel': request.form.get('responsavel'),
                'telefone': request.form.get('telefone'),
                'email': request.form.get('email'),
                'endereco': request.form.get('endereco'),
                'observacoes': request.form.get('observacoes')
            }
            if atualizar_laboratorio(id, dados):
                return redirect(url_for('listar_laboratorios_route'))
            return "Erro ao atualizar", 500
        except Exception as e:
            return f"Erro: {e}"
    
    from modules.analises import buscar_laboratorio_por_id
    lab = buscar_laboratorio_por_id(id)
    if not lab:
        return "Laboratório não encontrado", 404
    return render_template('analises/editar_laboratorio.html', lab=lab)

@app.route('/pdfs')
def listar_pdfs():
    """Lista todos os PDFs upados no sistema com opção de filtro"""
    import os
    from modules.analises import listar_analises
    from database import listar_talhoes  # <-- IMPORTANTE: importar a função de talhões
    from datetime import datetime
    
    # Pegar filtros da URL
    talhao_filtro = request.args.get('talhao', '')
    ano_filtro = request.args.get('ano', '')
    mes_filtro = request.args.get('mes', '')
    
    # Buscar TODOS os talhões do sistema
    todos_talhoes = listar_talhoes()
    talhoes_lista = []
    for t in todos_talhoes:
        # t é um dicionário, então acessamos pela chave 'nome'
        talhoes_lista.append(t['nome'])
    
    # Pasta de uploads
    pdf_folder = app.config['UPLOAD_FOLDER']
    pdfs = []
    
    if os.path.exists(pdf_folder):
        # Listar todos os arquivos PDF
        for arquivo in os.listdir(pdf_folder):
            if arquivo.endswith('.pdf'):
                # Buscar a análise associada a este PDF (se existir)
                analise_associada = None
                analises = listar_analises()
                for a in analises:
                    if a.get('arquivo_pdf') == arquivo:
                        analise_associada = a
                        break
                
                # Informações do arquivo
                caminho_completo = os.path.join(pdf_folder, arquivo)
                stats = os.stat(caminho_completo)
                data_mod = datetime.fromtimestamp(stats.st_mtime)
                
                pdf_info = {
                    'nome': arquivo,
                    'caminho': arquivo,
                    'tamanho': stats.st_size,
                    'data': data_mod.strftime('%d/%m/%Y %H:%M'),
                    'data_obj': data_mod,
                    'ano': data_mod.strftime('%Y'),
                    'mes': data_mod.strftime('%m'),
                    'analise': analise_associada,
                    'talhao_nome': analise_associada['talhao_nome'] if analise_associada else 'Sem talhão'
                }
                
                # Aplicar filtros
                incluir = True
                if talhao_filtro:
                    talhao_pdf = pdf_info['talhao_nome']
                    if talhao_filtro != talhao_pdf:
                        incluir = False
                if ano_filtro and pdf_info['ano'] != ano_filtro:
                    incluir = False
                if mes_filtro and pdf_info['mes'] != mes_filtro:
                    incluir = False
                
                if incluir:
                    pdfs.append(pdf_info)
    
    # Ordenar por data
    pdfs.sort(key=lambda x: x['data_obj'], reverse=True)
    
    # Listas para os filtros
    anos_disponiveis = sorted(list(set([p['ano'] for p in pdfs])), reverse=True)
    meses = [
        {'num': '01', 'nome': 'Janeiro'},
        {'num': '02', 'nome': 'Fevereiro'},
        {'num': '03', 'nome': 'Março'},
        {'num': '04', 'nome': 'Abril'},
        {'num': '05', 'nome': 'Maio'},
        {'num': '06', 'nome': 'Junho'},
        {'num': '07', 'nome': 'Julho'},
        {'num': '08', 'nome': 'Agosto'},
        {'num': '09', 'nome': 'Setembro'},
        {'num': '10', 'nome': 'Outubro'},
        {'num': '11', 'nome': 'Novembro'},
        {'num': '12', 'nome': 'Dezembro'},
    ]
    
    return render_template('pdfs/lista.html', 
                         pdfs=pdfs,
                         talhoes=talhoes_lista,
                         anos=anos_disponiveis,
                         meses=meses,
                         talhao_filtro=talhao_filtro,
                         ano_filtro=ano_filtro,
                         mes_filtro=mes_filtro)


@app.route('/pdfs/<path:nome>/excluir', methods=['POST'])
def excluir_pdf(nome):
    """Exclui um arquivo PDF"""
    import os
    from werkzeug.utils import secure_filename
    
    # Segurança: garantir que o nome é seguro
    nome_seguro = secure_filename(nome)
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
    
    try:
        if os.path.exists(caminho):
            os.remove(caminho)
            flash('PDF excluído com sucesso!', 'success')
        else:
            flash('Arquivo não encontrado!', 'danger')
    except Exception as e:
        flash(f'Erro ao excluir: {e}', 'danger')
    
    return redirect(url_for('listar_pdfs'))

# =====================================================
# ROTAS DO MÓDULO DE ADUBAÇÃO
# =====================================================

@app.route('/adubacao')
def adubacao_index():
    """Página inicial do módulo de adubação"""
    from modules.adubacao import listar_recomendacoes
    recomendacoes_recentes = listar_recomendacoes()[:10]
    return render_template('adubacao/index.html', recomendacoes=recomendacoes_recentes)

@app.route('/adubacao/recomendacoes')
def listar_recomendacoes_route():
    """Lista todas as recomendações e adubações"""
    from modules.adubacao import listar_recomendacoes, listar_adubacoes
    recomendacoes = listar_recomendacoes()
    adubacoes = listar_adubacoes()
    return render_template('adubacao/recomendacoes.html', 
                         recomendacoes=recomendacoes,
                         adubacoes=adubacoes)

@app.route('/adubacao/recomendacao/nova', methods=['GET', 'POST'])
def nova_recomendacao():
    """Criar uma nova recomendação de adubação"""
    from modules.adubacao import listar_tipos_adubacao, inserir_recomendacao, inserir_item_recomendacao
    from modules.analises import listar_analises
    from database import listar_talhoes
    
    if request.method == 'POST':
        try:
            # Tratar campos que podem vir vazios
            talhao_id = request.form.get('talhao_id')
            analise_id = request.form.get('analise_id')
            data_recomendacao = request.form.get('data_recomendacao')
            data_validade = request.form.get('data_validade')
            responsavel = request.form.get('responsavel')
            observacoes = request.form.get('observacoes')
            status = request.form.get('status', 'Pendente')
            
            # Validar campos obrigatórios
            if not talhao_id or not data_recomendacao:
                return "Talhão e data são obrigatórios", 400
            
            # Dados básicos da recomendação (tratando campos vazios)
            dados = {
                'talhao_id': int(talhao_id),
                'analise_id': int(analise_id) if analise_id else None,
                'data_recomendacao': data_recomendacao,
                'data_validade': data_validade if data_validade else None,  # <-- CORRIGIDO
                'responsavel': responsavel if responsavel else None,
                'observacoes': observacoes if observacoes else None,
                'status': status
            }
            
            # Inserir recomendação
            nova_id = inserir_recomendacao(dados)
            
            if nova_id:
                # Inserir itens da recomendação
                nutrientes = request.form.getlist('nutriente')
                for i, nutriente in enumerate(nutrientes):
                    if nutriente and nutriente.strip():  # só insere se tiver nome
                        quantidade = request.form.getlist('quantidade')[i] if i < len(request.form.getlist('quantidade')) else ''
                        unidade = request.form.getlist('unidade')[i] if i < len(request.form.getlist('unidade')) else ''
                        fonte = request.form.getlist('fonte')[i] if i < len(request.form.getlist('fonte')) else ''
                        obs_item = request.form.getlist('obs_item')[i] if i < len(request.form.getlist('obs_item')) else ''
                        
                        item_dados = {
                            'recomendacao_id': nova_id,
                            'nutriente': nutriente,
                            'quantidade': float(quantidade) if quantidade else None,
                            'unidade': unidade,
                            'fonte': fonte if fonte else None,
                            'observacoes': obs_item if obs_item else None
                        }
                        inserir_item_recomendacao(item_dados)
                
                return redirect(url_for('ver_recomendacao', id=nova_id))
            
            return "Erro ao criar recomendação", 500
            
        except Exception as e:
            print(f"Erro detalhado: {e}")
            import traceback
            traceback.print_exc()
            return f"Erro: {str(e)}", 500
    
    # GET - exibir formulário
    talhoes = listar_talhoes()
    analises = listar_analises()
    return render_template('adubacao/nova_recomendacao.html',
                         talhoes=talhoes,
                         analises=analises,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))


@app.route('/adubacao/recomendacao/<int:id>')
def ver_recomendacao(id):
    """Visualizar uma recomendação específica"""
    from modules.adubacao import buscar_recomendacao_por_id, listar_itens_recomendacao
    
    recomendacao = buscar_recomendacao_por_id(id)
    if not recomendacao:
        return "Recomendação não encontrada", 404
    
    itens = listar_itens_recomendacao(id)
    return render_template('adubacao/detalhe_recomendacao.html',
                         recomendacao=recomendacao,
                         itens=itens)

@app.route('/adubacao/recomendacao/<int:id>/gerar-de-analise/<int:analise_id>')
def gerar_recomendacao_de_analise(id, analise_id):
    """Gera recomendação automática baseada em uma análise"""
    from modules.adubacao import gerar_recomendacao_automatica, inserir_item_recomendacao
    from modules.analises import buscar_analise_por_id
    
    analise = buscar_analise_por_id(analise_id)
    if not analise:
        return "Análise não encontrada", 404
    
    recomendacoes, erro = gerar_recomendacao_automatica(analise_id)
    
    if erro:
        return f"Erro ao gerar recomendação: {erro}", 500
    
    # Inserir itens na recomendação
    for item in recomendacoes:
        item['recomendacao_id'] = id
        inserir_item_recomendacao(item)
    
    return redirect(url_for('ver_recomendacao', id=id))

@app.route('/adubacao/recomendacao/<int:id>/status/<status>')
def atualizar_status_recomendacao_route(id, status):
    """Atualiza o status de uma recomendação"""
    from modules.adubacao import atualizar_status_recomendacao
    
    if status not in ['Pendente', 'Aplicada', 'Cancelada']:
        return "Status inválido", 400
    
    if atualizar_status_recomendacao(id, status):
        return redirect(url_for('ver_recomendacao', id=id))
    return "Erro ao atualizar status", 500

@app.route('/adubacao/recomendacao/<int:id>/aplicar', methods=['GET', 'POST'])
def aplicar_recomendacao(id):
    """Registrar a aplicação de uma recomendação"""
    from modules.adubacao import buscar_recomendacao_por_id, listar_itens_recomendacao, atualizar_status_recomendacao
    from modules.estoque import listar_produtos
    from database import listar_talhoes
    
    recomendacao = buscar_recomendacao_por_id(id)
    if not recomendacao:
        return "Recomendação não encontrada", 404
    
    if request.method == 'POST':
        try:
            # Registrar adubação
            from modules.adubacao import inserir_adubacao, inserir_produto_adubacao, inserir_nutriente_aplicado
            
            dados_adubacao = {
                'talhao_id': recomendacao['talhao_id'],
                'recomendacao_id': id,
                'tipo_adubacao_id': int(request.form['tipo_adubacao_id']),
                'data_aplicacao': request.form['data_aplicacao'],
                'responsavel': request.form.get('responsavel'),
                'observacoes': request.form.get('observacoes')
            }
            
            adubacao_id = inserir_adubacao(dados_adubacao)
            
            if adubacao_id:
                # Registrar produtos usados
                produtos = request.form.getlist('produto_id')
                for i, prod_id in enumerate(produtos):
                    if prod_id:
                        produto_dados = {
                            'adubacao_id': adubacao_id,
                            'produto_nome': request.form.getlist('produto_nome')[i],
                            'quantidade': float(request.form.getlist('qtd_produto')[i]) if request.form.getlist('qtd_produto')[i] else 0,
                            'unidade': request.form.getlist('unidade_produto')[i],
                            'custo_unitario': float(request.form.getlist('custo')[i]) if request.form.getlist('custo')[i] else None,
                            'fornecedor': request.form.getlist('fornecedor')[i],
                            'observacoes': request.form.getlist('obs_produto')[i]
                        }
                        inserir_produto_adubacao(produto_dados)
                
                # Registrar nutrientes aplicados (baseado nos itens da recomendação)
                itens = listar_itens_recomendacao(id)
                for item in itens:
                    nutriente_dados = {
                        'adubacao_id': adubacao_id,
                        'nutriente': item['nutriente'],
                        'quantidade_aplicada': item['quantidade'],
                        'unidade': item['unidade']
                    }
                    inserir_nutriente_aplicado(nutriente_dados)
                
                # Atualizar status da recomendação
                atualizar_status_recomendacao(id, 'Aplicada')
                
                return redirect(url_for('ver_adubacao', id=adubacao_id))
            
        except Exception as e:
            return f"Erro ao registrar aplicação: {e}"
    
    # GET - mostrar formulário
    from modules.adubacao import listar_tipos_adubacao
    itens = listar_itens_recomendacao(id)
    tipos = listar_tipos_adubacao()
    produtos = listar_produtos()
    
    return render_template('adubacao/aplicar_recomendacao.html',
                         recomendacao=recomendacao,
                         itens=itens,
                         tipos=tipos,
                         produtos=produtos,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/adubacao/adubacao/<int:id>')
def ver_adubacao(id):
    """Visualizar uma adubação realizada"""
    from modules.adubacao import buscar_adubacao_por_id, listar_produtos_adubacao, listar_nutrientes_aplicados
    
    adubacao = buscar_adubacao_por_id(id)
    if not adubacao:
        return "Adubação não encontrada", 404
    
    produtos = listar_produtos_adubacao(id)
    nutrientes = listar_nutrientes_aplicados(id)
    
    return render_template('adubacao/ver_adubacao.html',
                         adubacao=adubacao,
                         produtos=produtos,
                         nutrientes=nutrientes)

# =====================================================
# ROTAS DE EXCLUSÃO - ADUBAÇÃO
# =====================================================

@app.route('/adubacao/recomendacao/<int:id>/excluir', methods=['POST'])
def excluir_recomendacao_route(id):
    """Excluir uma recomendação"""
    from modules.adubacao import excluir_recomendacao
    sucesso, mensagem = excluir_recomendacao(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_recomendacoes_route'))

@app.route('/adubacao/adubacao/<int:id>/excluir', methods=['POST'])
def excluir_adubacao_route(id):
    """Excluir uma adubação"""
    from modules.adubacao import excluir_adubacao
    sucesso, mensagem = excluir_adubacao(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_recomendacoes_route'))

# =====================================================
# ROTAS DE EXCLUSÃO - ANÁLISES
# =====================================================

@app.route('/analises/<int:id>/excluir', methods=['POST'])
def excluir_analise_route(id):
    """Excluir (desativar) uma análise"""
    from modules.analises import excluir_analise
    sucesso, mensagem = excluir_analise(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_todas_analises'))

@app.route('/analises/laboratorio/<int:id>/excluir', methods=['POST'])
def excluir_laboratorio_route(id):
    """Excluir (desativar) um laboratório"""
    from modules.analises import excluir_laboratorio
    sucesso, mensagem = excluir_laboratorio(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_laboratorios_route'))

@app.route('/analises/parametro/<int:id>/excluir', methods=['POST'])
def excluir_parametro_route(id):
    """Excluir um parâmetro de análise"""
    from modules.analises import excluir_parametro
    sucesso, mensagem = excluir_parametro(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_parametros_route'))

@app.route('/analises/tipo/<int:id>/excluir', methods=['POST'])
def excluir_tipo_analise_route(id):
    """Excluir um tipo de análise"""
    from modules.analises import excluir_tipo_analise
    sucesso, mensagem = excluir_tipo_analise(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_tipos_route'))

# =====================================================
# ROTAS DE EXCLUSÃO - PULVERIZAÇÃO
# =====================================================

@app.route('/pulverizacao/receita/<int:id>/excluir', methods=['POST'])
def excluir_receita_route(id):
    """Excluir uma receita"""
    from modules.pulverizacao import excluir_receita
    sucesso, mensagem = excluir_receita(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_receitas_route'))

@app.route('/pulverizacao/periodo/<int:id>/excluir', methods=['POST'])
def excluir_periodo_route(id):
    """Excluir um período da lavoura"""
    from modules.pulverizacao import excluir_periodo
    sucesso, mensagem = excluir_periodo(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_periodos_route'))

@app.route('/pulverizacao/praga/<int:id>/excluir', methods=['POST'])
def excluir_praga_route(id):
    """Excluir uma praga/doença"""
    from modules.pulverizacao import excluir_praga
    sucesso, mensagem = excluir_praga(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_pragas_route'))

@app.route('/pulverizacao/aplicacao/<int:id>/excluir', methods=['POST'])
def excluir_aplicacao_route(id):
    """Excluir uma aplicação"""
    from modules.pulverizacao import excluir_aplicacao
    sucesso, mensagem = excluir_aplicacao(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_todas_aplicacoes'))

# =====================================================
# ROTAS DE EXCLUSÃO - ESTOQUE
# =====================================================

@app.route('/estoque/produto/<int:id>/excluir', methods=['POST'])
def excluir_produto_route(id):
    """Excluir um produto"""
    from modules.estoque import excluir_produto
    sucesso, mensagem = excluir_produto(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('estoque_listar_produtos'))

@app.route('/estoque/movimentacao/<int:id>/excluir', methods=['POST'])
def excluir_movimentacao_route(id):
    """Excluir uma movimentação"""
    from modules.estoque import excluir_movimentacao
    sucesso, mensagem = excluir_movimentacao(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('estoque_listar_movimentacoes'))

# =====================================================
# ROTAS DE EXCLUSÃO - MANEJO DO MATO
# =====================================================

@app.route('/manejo-mato/<int:id>/excluir', methods=['POST'])
def excluir_manejo_route(id):
    """Excluir um manejo"""
    from modules.manejo_mato import excluir_manejo
    sucesso, mensagem = excluir_manejo(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_todos_manejos'))

@app.route('/manejo-mato/planta/<int:id>/excluir', methods=['POST'])
def excluir_planta_route(id):
    """Excluir uma planta daninha"""
    from modules.manejo_mato import excluir_planta
    sucesso, mensagem = excluir_planta(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    return redirect(url_for('listar_plantas_route'))


@app.context_processor
def utility_processor():
    from modules.clima import get_icone_clima
    return dict(get_icone_clima=get_icone_clima)

@app.route('/pulverizacao/relatorio', methods=['GET', 'POST'])
def relatorio_pulverizacoes():
    """Página de relatório de pulverizações com filtros"""
    from modules.pulverizacao import listar_aplicacoes, gerar_pdf_pulverizacoes
    from datetime import datetime
    
    if request.method == 'POST':
        # Se for POST, gerar PDF
        data_inicio_str = request.form.get('data_inicio')
        data_fim_str = request.form.get('data_fim')
        
        # Converter strings para objetos date para comparação
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        
        # Filtrar aplicações pelo período
        todas_aplicacoes = listar_aplicacoes()
        aplicacoes_filtradas = []
        
        for app in todas_aplicacoes:
            # Converter a data da aplicação (pode vir como string ou date)
            if isinstance(app['data_aplicacao'], str):
                app_data = datetime.strptime(app['data_aplicacao'], '%Y-%m-%d').date()
            else:
                app_data = app['data_aplicacao']
            
            if app_data >= data_inicio and app_data <= data_fim:
                aplicacoes_filtradas.append(app)
        
        pdf_file = gerar_pdf_pulverizacoes(aplicacoes_filtradas, data_inicio_str, data_fim_str)
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'pulverizacoes_{data_inicio_str}_a_{data_fim_str}.pdf'
        )
    
    # GET - mostrar página com filtros
    return render_template('pulverizacao/relatorio.html')

@app.route('/pulverizacao/receitas/pdf')
def exportar_receitas_pdf():
    """Exporta lista de receitas para PDF"""
    from modules.pulverizacao import listar_receitas, gerar_pdf_receitas
    from modules.pulverizacao import listar_periodos
    
    receitas = listar_receitas()
    periodos = {p['id']: p['nome'] for p in listar_periodos()}
    
    # Adicionar nome do período em cada receita
    for r in receitas:
        r['periodo_nome'] = periodos.get(r['periodo_id'], 'Desconhecido')
    
    pdf_file = gerar_pdf_receitas(receitas)
    
    return send_file(
        pdf_file,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'receitas_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    )

@app.route('/pulverizacao/receitas/relatorio', methods=['GET', 'POST'])
def relatorio_receitas():
    """Página de relatório de receitas com filtros"""
    from modules.pulverizacao import listar_receitas, listar_periodos, gerar_pdf_receitas
    from datetime import datetime
    
    periodos = listar_periodos()
    periodos_dict = {p['id']: p['nome'] for p in periodos}
    
    if request.method == 'POST':
        # Pegar filtros
        periodo_id = request.form.get('periodo_id')
        mes = request.form.get('mes')
        ano = request.form.get('ano')
        termo = request.form.get('termo', '')
        
        # Filtrar receitas
        todas_receitas = listar_receitas()
        receitas_filtradas = []
        
        # Nota: Como receitas não têm data, o filtro mês/ano não se aplica diretamente
        # Mas mantemos a estrutura para consistência com outros módulos
        
        for r in todas_receitas:
            # Adicionar nome do período
            r['periodo_nome'] = periodos_dict.get(r['periodo_id'], 'Desconhecido')
            
            # Filtrar por período
            if periodo_id and str(r['periodo_id']) != periodo_id:
                continue
            
            # Filtrar por termo de busca
            if termo:
                termo_lower = termo.lower()
                if termo_lower not in r['nome'].lower() and termo_lower not in (r.get('descricao') or '').lower() and termo_lower not in (r.get('formula') or '').lower():
                    continue
            
            receitas_filtradas.append(r)
        
        # Gerar PDF
        pdf_file = gerar_pdf_receitas(receitas_filtradas, periodo_id, mes, ano, termo)
        
        # Nome do arquivo
        nome_arquivo = 'receitas'
        if periodo_id:
            nome_periodo = periodos_dict.get(int(periodo_id), 'filtrado').lower().replace(' ', '_')
            nome_arquivo += f'_{nome_periodo}'
        if mes and ano:
            nome_arquivo += f'_{mes}_{ano}'
        elif ano:
            nome_arquivo += f'_{ano}'
        if termo:
            nome_arquivo += f'_{termo[:20]}'.replace(' ', '_')
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{nome_arquivo}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        )
    
    # GET - mostrar página com filtros
    anos = list(range(2020, datetime.now().year + 2))
    meses = [
        {'num': '01', 'nome': 'Janeiro'},
        {'num': '02', 'nome': 'Fevereiro'},
        {'num': '03', 'nome': 'Março'},
        {'num': '04', 'nome': 'Abril'},
        {'num': '05', 'nome': 'Maio'},
        {'num': '06', 'nome': 'Junho'},
        {'num': '07', 'nome': 'Julho'},
        {'num': '08', 'nome': 'Agosto'},
        {'num': '09', 'nome': 'Setembro'},
        {'num': '10', 'nome': 'Outubro'},
        {'num': '11', 'nome': 'Novembro'},
        {'num': '12', 'nome': 'Dezembro'},
    ]
    
    return render_template('pulverizacao/relatorio_receitas.html', 
                         periodos=periodos,
                         meses=meses,
                         anos=anos)

# =====================================================
# ROTAS PARA DEVOLUÇÃO DE EMBALAGENS (SIMPLIFICADO)
# =====================================================

@app.route('/estoque/devolucoes')
def listar_devolucoes():
    """Lista todas as devoluções de embalagens"""
    from modules.devolucao_embalagens import listar_devolucoes, get_resumo_devolucoes
    
    # Pegar filtros da URL
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    devolucoes = listar_devolucoes(data_inicio, data_fim)
    resumo = get_resumo_devolucoes()
    
    return render_template('estoque/devolucoes/lista.html',
                         devolucoes=devolucoes,
                         resumo=resumo,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@app.route('/estoque/devolucoes/nova', methods=['GET', 'POST'])
def nova_devolucao():
    """Registrar uma nova devolução de embalagem (simplificado)"""
    from modules.devolucao_embalagens import inserir_devolucao
    from datetime import datetime
    
    if request.method == 'POST':
        try:
            # Processar dados do formulário
            data_devolucao = request.form.get('data_devolucao')
            local_devolucao = request.form.get('local_devolucao')
            quantidade = request.form.get('quantidade_embalagens')
            nome_responsavel = request.form.get('nome_responsavel')
            numero_comprovante = request.form.get('numero_comprovante')
            observacoes = request.form.get('observacoes')
            
            # Validar campos obrigatórios
            if not data_devolucao or not local_devolucao or not quantidade:
                return "Data, local e quantidade são obrigatórios", 400
            
            # Processar upload do PDF
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename and allowed_file(file.filename):
                    from werkzeug.utils import secure_filename
                    import time
                    
                    filename = secure_filename(file.filename)
                    nome_unico = f"devolucao_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER_DEVOLUCOES'], nome_unico))
                    arquivo_pdf = nome_unico
            
            # Montar dados
            dados = {
                'data_devolucao': data_devolucao,
                'local_devolucao': local_devolucao,
                'quantidade_embalagens': int(quantidade),
                'nome_responsavel': nome_responsavel,
                'numero_comprovante': numero_comprovante,
                'observacoes': observacoes
            }
            
            # Inserir no banco
            nova_id = inserir_devolucao(dados, arquivo_pdf)
            
            if nova_id:
                flash('Devolução registrada com sucesso!', 'success')
                return redirect(url_for('ver_devolucao', id=nova_id))
            else:
                return "Erro ao registrar devolução", 500
                
        except Exception as e:
            print(f"Erro: {e}")
            return f"Erro ao processar: {str(e)}", 500
    
    # GET - mostrar formulário
    return render_template('estoque/devolucoes/nova.html',
                         data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/estoque/devolucoes/<int:id>')
def ver_devolucao(id):
    """Visualizar detalhes de uma devolução"""
    from modules.devolucao_embalagens import buscar_devolucao_por_id
    
    devolucao = buscar_devolucao_por_id(id)
    if not devolucao:
        return "Devolução não encontrada", 404
    
    return render_template('estoque/devolucoes/detalhe.html', devolucao=devolucao)

@app.route('/estoque/devolucoes/<int:id>/pdf')
def ver_pdf_devolucao(id):
    """Visualizar/download do PDF comprovante"""
    from modules.devolucao_embalagens import buscar_devolucao_por_id
    import os
    
    devolucao = buscar_devolucao_por_id(id)
    if not devolucao or not devolucao.get('arquivo_pdf'):
        return "PDF não encontrado", 404
    
    caminho_pdf = os.path.join(app.config['UPLOAD_FOLDER_DEVOLUCOES'], devolucao['arquivo_pdf'])
    
    if not os.path.exists(caminho_pdf):
        return "Arquivo não encontrado no servidor", 404
    
    return send_file(
        caminho_pdf,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"devolucao_{devolucao['data_devolucao']}.pdf"
    )

@app.route('/estoque/devolucoes/<int:id>/excluir', methods=['POST'])
def excluir_devolucao(id):
    """Excluir (desativar) uma devolução"""
    from modules.devolucao_embalagens import excluir_devolucao
    
    sucesso, mensagem = excluir_devolucao(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    
    return redirect(url_for('listar_devolucoes'))

# =====================================================
# ROTAS PARA NOTAS FISCAIS
# =====================================================

@app.route('/estoque/notas')
def listar_notas():
    """Lista todas as notas fiscais"""
    from modules.notas_fiscais import listar_notas, get_resumo_notas
    
    # Pegar filtros da URL
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    fornecedor = request.args.get('fornecedor')
    
    notas = listar_notas(data_inicio, data_fim, fornecedor)
    resumo = get_resumo_notas()
    
    return render_template('estoque/notas/lista.html',
                         notas=notas,
                         resumo=resumo,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         fornecedor=fornecedor)

@app.route('/estoque/notas/nova', methods=['GET', 'POST'])
def nova_nota():
    """Registrar uma nova nota fiscal"""
    from modules.notas_fiscais import inserir_nota_fiscal
    from modules.estoque import listar_produtos
    from datetime import datetime
    
    if request.method == 'POST':
        try:
            # Processar dados da nota
            numero_nota = request.form.get('numero_nota')
            serie = request.form.get('serie')
            data_emissao = request.form.get('data_emissao')
            data_recebimento = request.form.get('data_recebimento')
            fornecedor = request.form.get('fornecedor')
            cnpj = request.form.get('cnpj_fornecedor')
            valor_total = request.form.get('valor_total')
            observacoes = request.form.get('observacoes')
            
            # Validar campos obrigatórios
            if not numero_nota or not data_emissao or not data_recebimento or not fornecedor:
                return "Campos obrigatórios não preenchidos", 400
            
            # Processar upload do PDF
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename and allowed_file(file.filename):
                    from werkzeug.utils import secure_filename
                    import time
                    
                    filename = secure_filename(file.filename)
                    nome_unico = f"nota_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER_NOTAS'], nome_unico))
                    arquivo_pdf = nome_unico
            
            # Montar dados da nota
            dados_nota = {
                'numero_nota': numero_nota,
                'serie': serie,
                'data_emissao': data_emissao,
                'data_recebimento': data_recebimento,
                'fornecedor': fornecedor,
                'cnpj_fornecedor': cnpj,
                'valor_total': float(valor_total) if valor_total else None,
                'observacoes': observacoes
            }
            
            # Inserir nota
            nota_id = inserir_nota_fiscal(dados_nota, arquivo_pdf)
            
            if nota_id:
                flash('Nota fiscal registrada com sucesso!', 'success')
                return redirect(url_for('ver_nota', id=nota_id))
            else:
                return "Erro ao registrar nota fiscal", 500
                
        except Exception as e:
            print(f"Erro: {e}")
            return f"Erro ao processar: {str(e)}", 500
    
    # GET - mostrar formulário
    return render_template('estoque/notas/nova.html',
                         data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/estoque/notas/<int:id>')
def ver_nota(id):
    """Visualizar detalhes de uma nota fiscal"""
    from modules.notas_fiscais import buscar_nota_por_id, listar_movimentacoes_por_nota
    
    nota = buscar_nota_por_id(id)
    if not nota:
        return "Nota fiscal não encontrada", 404
    
    produtos = listar_movimentacoes_por_nota(id)
    
    return render_template('estoque/notas/detalhe.html',
                         nota=nota,
                         produtos=produtos)

@app.route('/estoque/notas/<int:id>/pdf')
def ver_pdf_nota(id):
    """Visualizar/download do PDF da nota fiscal"""
    from modules.notas_fiscais import buscar_nota_por_id
    import os
    
    nota = buscar_nota_por_id(id)
    if not nota or not nota.get('arquivo_pdf'):
        return "PDF não encontrado", 404
    
    caminho_pdf = os.path.join(app.config['UPLOAD_FOLDER_NOTAS'], nota['arquivo_pdf'])
    
    if not os.path.exists(caminho_pdf):
        return "Arquivo não encontrado no servidor", 404
    
    return send_file(
        caminho_pdf,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"nota_{nota['numero_nota']}.pdf"
    )

@app.route('/estoque/notas/<int:id>/excluir', methods=['POST'])
def excluir_nota(id):
    """Excluir (desativar) uma nota fiscal"""
    from modules.notas_fiscais import excluir_nota_fiscal
    
    sucesso, mensagem = excluir_nota_fiscal(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    
    return redirect(url_for('listar_notas'))

@app.route('/estoque/movimentacao/nova-com-nota', methods=['GET', 'POST'])
def nova_movimentacao_com_nota():
    """
    Registrar entrada de múltiplos produtos com uma única nota fiscal
    """
    from modules.estoque import listar_produtos, registrar_movimentacao
    from modules.notas_fiscais import inserir_nota_fiscal, vincular_movimentacao_nota
    from datetime import datetime
    
    if request.method == 'POST':
        try:
            # 1. Processar dados da nota fiscal
            numero_nota = request.form.get('numero_nota')
            serie = request.form.get('serie')
            data_emissao = request.form.get('data_emissao')
            data_recebimento = request.form.get('data_recebimento')
            fornecedor = request.form.get('fornecedor')
            cnpj = request.form.get('cnpj_fornecedor')
            valor_total = request.form.get('valor_total')
            
            # Validar campos obrigatórios da nota
            if not numero_nota or not data_emissao or not data_recebimento or not fornecedor:
                return "Dados da nota fiscal incompletos", 400
            
            # Processar upload do PDF
            arquivo_pdf = None
            if 'arquivo_pdf' in request.files:
                file = request.files['arquivo_pdf']
                if file and file.filename and allowed_file(file.filename):
                    from werkzeug.utils import secure_filename
                    import time
                    
                    filename = secure_filename(file.filename)
                    nome_unico = f"nota_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER_NOTAS'], nome_unico))
                    arquivo_pdf = nome_unico
            
            # Inserir nota fiscal
            dados_nota = {
                'numero_nota': numero_nota,
                'serie': serie,
                'data_emissao': data_emissao,
                'data_recebimento': data_recebimento,
                'fornecedor': fornecedor,
                'cnpj_fornecedor': cnpj,
                'valor_total': float(valor_total) if valor_total else None,
                'observacoes': request.form.get('observacoes_nota')
            }
            
            nota_id = inserir_nota_fiscal(dados_nota, arquivo_pdf)
            
            if not nota_id:
                return "Erro ao registrar nota fiscal", 500
            
            # 2. Processar os produtos da nota
            produtos_ids = request.form.getlist('produto_id[]')
            quantidades = request.form.getlist('quantidade[]')
            valores = request.form.getlist('valor_unitario[]')
            observacoes = request.form.getlist('observacoes[]')
            
            movimentacoes_criadas = 0
            
            for i in range(len(produtos_ids)):
                if produtos_ids[i] and quantidades[i]:
                    dados_mov = {
                        'produto_id': int(produtos_ids[i]),
                        'tipo': 'entrada',
                        'quantidade': float(quantidades[i]),
                        'unidade': '',  # A unidade virá do produto
                        'data_movimento': data_recebimento,
                        'valor_unitario': float(valores[i]) if valores[i] else None,
                        'observacoes': observacoes[i] if i < len(observacoes) else ''
                    }
                    
                    mov_id = registrar_movimentacao(dados_mov)
                    
                    if mov_id:
                        # Vincular movimentação à nota
                        vincular_movimentacao_nota(mov_id, nota_id)
                        movimentacoes_criadas += 1
            
            if movimentacoes_criadas > 0:
                flash(f'Nota fiscal e {movimentacoes_criadas} produto(s) registrados com sucesso!', 'success')
                return redirect(url_for('ver_nota', id=nota_id))
            else:
                return "Nenhum produto foi registrado", 400
                
        except Exception as e:
            print(f"Erro: {e}")
            return f"Erro ao processar: {str(e)}", 500
    
    # GET - mostrar formulário
    produtos = listar_produtos()
    return render_template('estoque/notas/movimentacao_com_nota.html',
                         produtos=produtos,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))


@app.route('/pulverizacao/aplicacao/<int:id>/retorno', methods=['GET', 'POST'])
def registrar_retorno(id):
    """Registrar o retorno de uma pulverização"""
    from modules.pulverizacao import buscar_aplicacao_por_id, atualizar_retorno
    from datetime import datetime
    
    aplicacao = buscar_aplicacao_por_id(id)
    if not aplicacao:
        return "Aplicação não encontrada", 404
    
    if request.method == 'POST':
        try:
            status = request.form.get('status_retorno')
            observacoes = request.form.get('observacoes_retorno')
            
            dados = {
                'status_retorno': status,
                'observacoes_retorno': observacoes,
                'data_retorno_realizado': datetime.now().strftime('%Y-%m-%d')
            }
            
            if atualizar_retorno(id, dados):
                flash('Retorno registrado com sucesso!', 'success')
                return redirect(url_for('ver_aplicacao', id=id))
            else:
                return "Erro ao registrar retorno", 500
                
        except Exception as e:
            return f"Erro: {e}"
    
    # GET - mostrar formulário
    return render_template('pulverizacao/registrar_retorno.html', 
                         aplicacao=aplicacao,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/pulverizacao/aplicacao/<int:id>/retorno/editar', methods=['GET', 'POST'])
def editar_retorno(id):
    """Editar um retorno já registrado"""
    from modules.pulverizacao import buscar_aplicacao_por_id, buscar_retorno_por_aplicacao, atualizar_retorno
    from datetime import datetime
    
    aplicacao = buscar_aplicacao_por_id(id)
    if not aplicacao:
        return "Aplicação não encontrada", 404
    
    retorno = buscar_retorno_por_aplicacao(id)
    
    if request.method == 'POST':
        try:
            status = request.form.get('status_retorno')
            observacoes = request.form.get('observacoes_retorno')
            data_realizado = request.form.get('data_retorno_realizado')
            
            dados = {
                'status_retorno': status,
                'observacoes_retorno': observacoes,
                'data_retorno_realizado': data_realizado
            }
            
            if atualizar_retorno(id, dados):
                flash('Retorno atualizado com sucesso!', 'success')
                return redirect(url_for('ver_aplicacao', id=id))
            else:
                return "Erro ao atualizar retorno", 500
                
        except Exception as e:
            return f"Erro: {e}"
    
    # GET - mostrar formulário preenchido
    return render_template('pulverizacao/editar_retorno.html', 
                         aplicacao=aplicacao,
                         retorno=retorno,
                         data_atual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/pulverizacao/aplicacao/<int:id>/retorno/excluir', methods=['POST'])
def excluir_retorno(id):
    """Remove completamente o registro de retorno"""
    from modules.pulverizacao import limpar_retorno
    
    sucesso, mensagem = limpar_retorno(id)
    if sucesso:
        flash(mensagem, 'success')
    else:
        flash(mensagem, 'danger')
    
    return redirect(url_for('ver_aplicacao', id=id))
# =====================================================
# ROTA DE TESTE
# =====================================================
@app.route('/teste-db')
def teste_db():
    try:
        resultado = executar_query("SELECT count(*) FROM talhoes", fetch_one=True)
        total = resultado[0] if resultado else 0
        return f"Banco de dados OK! Total de talhões: {total}"
    except Exception as e:
        return f"Erro no banco de dados: {e}"

# =====================================================
# INICIALIZAÇÃO
# =====================================================
if __name__ == '__main__':
    os.makedirs('templates/talhoes', exist_ok=True)
    os.makedirs('templates/pulverizacao', exist_ok=True)
    
    print("="*50)
    print("Sistema Fazenda Café - Versão Simples")
    print(f"Acesse: http://localhost:5000")
    print("="*50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)