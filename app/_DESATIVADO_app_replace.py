"""
Arquivo principal do sistema Fazenda Café
CORRIGIDO - Versão estável
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sys
import os
import atexit
from datetime import datetime
# =====================================================
# ROTAS DO MÓDULO DE PULVERIZAÇÃO FOLIAR
# =====================================================

from modules.pulverizacao import (
    listar_periodos, listar_receitas, inserir_receita, buscar_receita_por_id,
    listar_aplicacoes, inserir_aplicacao, buscar_aplicacao_por_id,
    listar_pragas_doencas, registrar_ocorrencia, listar_ocorrencias_por_talhao,
    listar_ocorrencias_por_aplicacao
)
# Adicionar o caminho da pasta config ao PATH do Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config')))

# Importar nosso módulo de banco de dados
from database import (ConexaoBanco, listar_talhoes, buscar_talhao_por_id, 
                     executar_query, inserir_talhao, atualizar_talhao, 
                     excluir_talhao, criar_tabela_talhoes)

app = Flask(__name__)
app.secret_key = 'chave-super-secreta-fazenda-cafe-2026'

# Inicializar conexão com banco ao iniciar o sistema
def init_db():
    """Inicializa o banco de dados"""
    try:
        if ConexaoBanco.inicializar_pool():
            criar_tabela_talhoes()
            print("Banco de dados inicializado com sucesso!")
            return True
        else:
            print("FALHA ao inicializar banco de dados!")
            return False
    except Exception as e:
        print(f"Erro na inicialização do banco: {e}")
        return False

# Inicializar banco na carga do módulo
init_db()

# Garantir que o pool é fechado quando o app terminar
@atexit.register
def cleanup():
    """Garante que o pool é fechado na saída"""
    print("Fechando conexões com o banco de dados...")
    ConexaoBanco.fechar_pool()

# Rota principal - Dashboard Avançado
@app.route('/')
@login_required
def index():
    """Dashboard com gráficos e estatísticas"""
    try:
        # Importar funções do dashboard
        from modules.dashboard import (
            get_resumo_geral, get_atividades_recentes, get_alertas_retorno,
            get_pragas_por_talhao, get_aplicacoes_por_periodo,
            get_aplicacoes_ultimos_6_meses, get_tipos_pragas
        )
        
        # Coletar todos os dados
        resumo = get_resumo_geral()
        atividades = get_atividades_recentes(8)
        alertas = get_alertas_retorno()
        
        # Dados para gráficos
        grafico_pragas_talhao = get_pragas_por_talhao()
        grafico_aplicacoes_periodo = get_aplicacoes_por_periodo()
        grafico_tendencia = get_aplicacoes_ultimos_6_meses()
        grafico_tipos_pragas = get_tipos_pragas()
        
        return render_template('dashboard.html',
                             resumo=resumo,
                             atividades=atividades,
                             alertas=alertas,
                             grafico_pragas_talhao=grafico_pragas_talhao,
                             grafico_aplicacoes_periodo=grafico_aplicacoes_periodo,
                             grafico_tendencia=grafico_tendencia,
                             grafico_tipos_pragas=grafico_tipos_pragas)
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro ao carregar dashboard: {e}"
    
# Rota para listar todos os talhões
@app.route('/talhoes')
@login_required
def listar_talhoes_route():
    """Página com lista de todos os talhões"""
    try:
        talhoes = listar_talhoes()
        return render_template('talhoes/lista.html', talhoes=talhoes)
    except Exception as e:
        print(f"Erro ao listar talhões: {e}")
        return f"Erro ao listar talhões: {e}"

# Rota para ver detalhes de um talhão específico
@app.route('/talhao/<int:id>')
@login_required
def ver_talhao(id):
    """Página de detalhes de um talhão"""
    try:
        talhao = buscar_talhao_por_id(id)
        if talhao:
            return render_template('talhoes/detalhe.html', talhao=talhao)
        else:
            return "Talhão não encontrado", 404
    except Exception as e:
        print(f"Erro ao buscar talhão: {e}")
        return f"Erro ao buscar talhão: {e}"

# Rota para formulário de novo talhão
@app.route('/talhao/novo', methods=['GET', 'POST'])
@login_required
def novo_talhao():
    """Criar um novo talhão"""
    if request.method == 'POST':
        try:
            # Coletar dados do formulário
            dados = {
                'nome': request.form['nome'],
                'area': float(request.form['area']),
                'data_plantio': request.form['data_plantio'] if request.form['data_plantio'] else None,
                'variedade': request.form['variedade'],
                'altitude': float(request.form['altitude']) if request.form['altitude'] else None,
                'observacoes': request.form['observacoes']
            }
            
            # Inserir no banco
            novo_id = inserir_talhao(dados)
            
            if novo_id:
                return redirect(url_for('ver_talhao', id=novo_id))
            else:
                return "Erro ao criar talhão", 500
                
        except Exception as e:
            print(f"Erro ao processar formulário: {e}")
            return f"Erro ao processar formulário: {e}"
    
    # GET: mostrar formulário
    return render_template('talhoes/novo.html')

# Rota para editar talhão
@app.route('/talhao/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_talhao(id):
    """Editar um talhão existente"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.form['nome'],
                'area': float(request.form['area']),
                'data_plantio': request.form['data_plantio'] if request.form['data_plantio'] else None,
                'variedade': request.form['variedade'],
                'altitude': float(request.form['altitude']) if request.form['altitude'] else None,
                'observacoes': request.form['observacoes']
            }
            
            if atualizar_talhao(id, dados):
                return redirect(url_for('ver_talhao', id=id))
            else:
                return "Erro ao atualizar talhão", 500
            
        except Exception as e:
            print(f"Erro ao atualizar: {e}")
            return f"Erro ao atualizar: {e}"
    
    # GET: mostrar formulário preenchido
    talhao = buscar_talhao_por_id(id)
    if talhao:
        return render_template('talhoes/editar.html', talhao=talhao)
    return "Talhão não encontrado", 404

# Rota para excluir talhão
@app.route('/talhao/<int:id>/excluir')
def excluir_talhao_route(id):
    """Exclui um talhão (lógico)"""
    try:
        if excluir_talhao(id):
            return redirect(url_for('listar_talhoes_route'))
        else:
            return "Erro ao excluir talhão", 500
    except Exception as e:
        print(f"Erro na exclusão: {e}")
        return f"Erro: {e}"

# Página principal do módulo de pulverização
@app.route('/pulverizacao')
def pulverizacao_index():
    """Dashboard do módulo de pulverização foliar"""
    try:
        aplicacoes_recentes = listar_aplicacoes()[:10]
        periodos = listar_periodos()
        pragas = listar_pragas_doencas()
        
        return render_template('pulverizacao/index.html',
                             aplicacoes=aplicacoes_recentes,
                             periodos=periodos,
                             pragas=pragas[:5])
    except Exception as e:
        print(f"Erro: {e}")
        return f"Erro ao carregar página: {e}"

# Listar todas as pulverizações
@app.route('/pulverizacao/aplicacoes')
def listar_todas_aplicacoes():
    """Lista todas as pulverizações realizadas"""
    try:
        aplicacoes = listar_aplicacoes()
        return render_template('pulverizacao/aplicacoes.html', aplicacoes=aplicacoes)
    except Exception as e:
        return f"Erro: {e}"

# Ver detalhes de uma aplicação
@app.route('/pulverizacao/aplicacao/<int:id>')
def ver_aplicacao(id):
    """Detalhes de uma pulverização"""
    try:
        aplicacao = buscar_aplicacao_por_id(id)
        pragas_detectadas = listar_ocorrencias_por_aplicacao(id)
        
        if aplicacao:
            return render_template('pulverizacao/detalhe_aplicacao.html',
                                 aplicacao=aplicacao,
                                 pragas=pragas_detectadas)
        return "Aplicação não encontrada", 404
    except Exception as e:
        return f"Erro: {e}"

# Nova pulverização
# Nova pulverização
@app.route('/pulverizacao/nova', methods=['GET', 'POST'])
def nova_pulverizacao():
    """Registra uma nova pulverização"""
    if request.method == 'POST':
        try:
            # Validar campos obrigatórios
            if not request.form.get('talhao_id') or not request.form.get('periodo_id') or not request.form.get('data_aplicacao'):
                return "Campos obrigatórios não preenchidos", 400
            
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
            
            # Inserir a aplicação
            nova_id = inserir_aplicacao(dados)
            
            if not nova_id:
                return "Erro ao inserir aplicação no banco de dados", 500
            
            # Registrar pragas detectadas (se houver)
            pragas_ids = request.form.getlist('pragas_detectadas')
            if pragas_ids:
                for praga_id in pragas_ids:
                    nivel = request.form.get(f'nivel_{praga_id}', 'medio')
                    ocorrencia = {
                        'talhao_id': dados['talhao_id'],
                        'praga_id': int(praga_id),
                        'aplicacao_id': nova_id,
                        'data_deteccao': dados['data_aplicacao'],
                        'nivel': nivel,
                        'tratado': True,
                        'observacoes': f"Detectado na pulverização de {dados['data_aplicacao']}"
                    }
                    registrar_ocorrencia(ocorrencia)
            
            # Redirecionar para a página da aplicação recém-criada
            return redirect(url_for('ver_aplicacao', id=nova_id))
            
        except Exception as e:
            print(f"Erro detalhado: {e}")
            import traceback
            traceback.print_exc()
            return f"Erro ao processar: {str(e)}", 500
    
    # GET - mostrar formulário
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

# Listar receitas
@app.route('/pulverizacao/receitas')
def listar_receitas_route():
    """Lista todas as receitas cadastradas"""
    try:
        receitas = listar_receitas()
        periodos = {p['id']: p['nome'] for p in listar_periodos()}
        return render_template('pulverizacao/receitas.html', receitas=receitas, periodos=periodos)
    except Exception as e:
        return f"Erro: {e}"

# Nova receita
@app.route('/pulverizacao/receita/nova', methods=['GET', 'POST'])
def nova_receita():
    """Cadastra uma nova receita"""
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
            return redirect(url_for('listar_receitas_route'))
            
        except Exception as e:
            return f"Erro: {e}"
    
    periodos = listar_periodos()
    return render_template('pulverizacao/nova_receita.html', periodos=periodos)

# Histórico de pulverizações de um talhão
@app.route('/talhao/<int:id>/pulverizacoes')
def historico_pulverizacoes_talhao(id):
    """Histórico de pulverizações de um talhão"""
    try:
        talhao = buscar_talhao_por_id(id)
        aplicacoes = listar_aplicacoes(talhao_id=id)
        ocorrencias = listar_ocorrencias_por_talhao(id)
        
        return render_template('talhoes/pulverizacoes.html',
                             talhao=talhao,
                             aplicacoes=aplicacoes,
                             ocorrencias=ocorrencias)
    except Exception as e:
        return f"Erro: {e}"

# =====================================================
# ROTAS DE AUTENTICAÇÃO
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        login_input = request.form['login']
        senha = request.form['senha']
        
        usuario_dados, erro = autenticar_usuario(login_input, senha)
        
        if usuario_dados:
            # Criar objeto de usuário para a sessão
            usuario = Usuario(
                usuario_dados['id'],
                usuario_dados['nome'],
                usuario_dados['login'],
                usuario_dados['nivel_acesso']
            )
            login_user(usuario)
            
            # Registrar log
            registrar_log(
                usuario.id, 
                'LOGIN', 
                'auth',
                ip=request.remote_addr
            )
            
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro=erro)
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Fazer logout"""
    registrar_log(current_user.id, 'LOGOUT', 'auth', ip=request.remote_addr)
    logout_user()
    return redirect(url_for('login'))

@app.route('/usuarios')
@login_required
def listar_usuarios_route():
    """Lista todos os usuários (apenas admin)"""
    if not current_user.is_admin():
        return "Acesso negado", 403
    
    usuarios = listar_usuarios()
    return render_template('usuarios/lista.html', usuarios=usuarios)

@app.route('/usuario/novo', methods=['GET', 'POST'])
@login_required
def novo_usuario():
    """Cria um novo usuário (apenas admin)"""
    if not current_user.is_admin():
        return "Acesso negado", 403
    
    if request.method == 'POST':
        nome = request.form['nome']
        login = request.form['login']
        senha = request.form['senha']
        nivel = request.form['nivel']
        
        sucesso, resultado = criar_usuario(nome, login, senha, nivel)
        
        if sucesso:
            registrar_log(
                current_user.id,
                'CRIAR_USUARIO',
                'auth',
                registro_id=resultado,
                dados_novos=f"Nome: {nome}, Login: {login}, Nível: {nivel}",
                ip=request.remote_addr
            )
            return redirect(url_for('listar_usuarios_route'))
        else:
            return render_template('usuarios/novo.html', erro=resultado)
    
    return render_template('usuarios/novo.html')

@app.route('/usuario/<int:id>/desativar')
@login_required
def desativar_usuario_route(id):
    """Desativa um usuário (apenas admin)"""
    if not current_user.is_admin():
        return "Acesso negado", 403
    
    if id == current_user.id:
        return "Não é possível desativar seu próprio usuário", 400
    
    sucesso, msg = desativar_usuario(id, current_user.id)
    if sucesso:
        registrar_log(
            current_user.id,
            'DESATIVAR_USUARIO',
            'auth',
            registro_id=id,
            ip=request.remote_addr
        )
    return redirect(url_for('listar_usuarios_route'))

@app.route('/usuario/<int:id>/alterar-nivel/<nivel>')
@login_required
def alterar_nivel_route(id, nivel):
    """Altera nível de acesso (apenas admin)"""
    if not current_user.is_admin():
        return "Acesso negado", 403
    
    if nivel not in ['admin', 'usuario']:
        return "Nível inválido", 400
    
    sucesso, msg = alterar_nivel_usuario(id, nivel, current_user.id)
    if sucesso:
        registrar_log(
            current_user.id,
            'ALTERAR_NIVEL',
            'auth',
            registro_id=id,
            dados_novos=f"Novo nível: {nivel}",
            ip=request.remote_addr
        )
    return redirect(url_for('listar_usuarios_route'))

@app.route('/minha-conta')
@login_required
def minha_conta():
    """Página do usuário logado"""
    return render_template('usuarios/conta.html') 
   
# Rota de teste para verificar conexão
@app.route('/teste-db')
def teste_db():
    """Rota para testar se o banco está funcionando"""
    try:
        # Tentar uma consulta simples
        resultado = executar_query("SELECT count(*) FROM talhoes", fetch_one=True)
        total = resultado[0] if resultado else 0
        return f"Banco de dados OK! Total de talhões: {total}"
    except Exception as e:
        return f"Erro no banco de dados: {e}"

if __name__ == '__main__':
    # Criar pastas de templates se não existirem
    os.makedirs('templates/talhoes', exist_ok=True)
    
    print("="*50)
    print("Sistema Fazenda Café iniciando...")
    print(f"Acesse localmente: http://localhost:5000")
    print(f"Acesse na rede: http://192.168.0.24:5000")
    print("="*50)
    
    # Iniciar servidor
    app.run(host='0.0.0.0', port=5000, debug=True)