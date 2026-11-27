from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules import auth, seguranca, perfil as perfil_mod
from app.modules.login_manager import login_required
from werkzeug.security import generate_password_hash
from config.database import executar_query
from app.models import get_logger

logger = get_logger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id') and request.method == 'GET':
        return redirect(url_for('dashboard.index'))

    destino = seguranca.destino_seguro(request.values.get('next'))

    if request.method == 'POST':
        usuario = (request.form.get('usuario') or '').strip()
        senha = request.form.get('senha') or ''
        ip = seguranca.ip_do_pedido(request)
        navegador = request.headers.get('User-Agent', '')

        minutos = seguranca.esta_bloqueado(ip, usuario)
        if minutos:
            seguranca.registrar_acesso(usuario, False, 'bloqueado', ip=ip, navegador=navegador)
            logger.warning(f"auth_routes.login: acesso bloqueado para '{usuario}' de {ip}")
            flash(f'Muitas tentativas com senha errada. Tente de novo em {minutos} min.', 'error')
            return render_template('login.html', proximo=destino), 429

        user = auth.validar_usuario(usuario, senha)
        if user:
            seguranca.limpar_falhas(ip, usuario)
            # Sessão nova a cada login (evita reaproveitar um cookie anterior)
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['usuario'] = user['nome']
            session['login'] = user['login']
            session['tipo'] = user.get('tipo', 'user')
            session['ultima_atividade'] = datetime.now().timestamp()
            session['verificado_em'] = datetime.now().timestamp()
            seguranca.registrar_acesso(usuario, True, usuario_id=user['id'], ip=ip, navegador=navegador)
            preferencias = perfil_mod.dados_sessao(user['id'])
            session['foto'] = preferencias['foto']
            session['cor_avatar'] = preferencias['cor_avatar']
            inicial = preferencias['pagina_inicial']
            return redirect(destino or url_for(inicial or 'dashboard.index'))

        restantes = seguranca.registrar_falha(ip, usuario)
        seguranca.registrar_acesso(usuario, False, 'senha ou usuário inválido', ip=ip, navegador=navegador)
        logger.warning(f"auth_routes.login: falha de login para '{usuario}' de {ip}")
        if restantes and restantes <= 2:
            flash(f'Usuário ou senha inválidos. Restam {restantes} tentativa(s) antes do bloqueio.', 'error')
        elif not restantes:
            flash(f'Usuário ou senha inválidos. Acesso bloqueado por {seguranca.bloqueio_minutos()} min.', 'error')
        else:
            flash('Usuário ou senha inválidos.', 'error')
    return render_template('login.html', proximo=destino)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil')
@login_required
def perfil():
    usuario = perfil_mod.buscar(session.get('user_id'))
    if not usuario:
        flash('Não foi possível carregar seu perfil.', 'error')
        return redirect(url_for('dashboard.index'))
    return render_template('perfil.html', usuario=usuario,
                           acessos=perfil_mod.acessos(usuario['id'], usuario['login']),
                           cores=perfil_mod.CORES, paginas=perfil_mod.PAGINAS_INICIAIS,
                           senha_minimo=seguranca.senha_minimo(),
                           resumo_navegador=perfil_mod.resumo_navegador,
                           max_foto_mb=perfil_mod.MAX_FOTO_MB)


def _sincronizar_sessao():
    dados = perfil_mod.dados_sessao(session.get('user_id'))
    session['foto'] = dados['foto']
    session['cor_avatar'] = dados['cor_avatar']


@auth_bp.route('/perfil/dados', methods=['POST'])
@login_required
def perfil_dados():
    try:
        ok, msg = perfil_mod.atualizar_dados(session.get('user_id'), request.form)
        if ok:
            session['usuario'] = (request.form.get('nome') or '').strip()[:100]
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"auth_routes.perfil_dados: {e}")
        flash('Erro ao salvar os dados.', 'error')
    return redirect(url_for('auth.perfil') + '#dados')


@auth_bp.route('/perfil/preferencias', methods=['POST'])
@login_required
def perfil_preferencias():
    try:
        ok, msg = perfil_mod.atualizar_preferencias(session.get('user_id'), request.form)
        if ok:
            _sincronizar_sessao()
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"auth_routes.perfil_preferencias: {e}")
        flash('Erro ao salvar as preferências.', 'error')
    return redirect(url_for('auth.perfil') + '#preferencias')


@auth_bp.route('/perfil/foto', methods=['POST'])
@login_required
def perfil_foto():
    try:
        ok, msg, _nome = perfil_mod.salvar_foto(session.get('user_id'), request.files.get('foto'))
        if ok:
            _sincronizar_sessao()
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"auth_routes.perfil_foto: {e}")
        flash('Erro ao enviar a foto.', 'error')
    return redirect(url_for('auth.perfil'))


@auth_bp.route('/perfil/foto/remover', methods=['POST'])
@login_required
def perfil_foto_remover():
    try:
        ok, msg = perfil_mod.remover_foto(session.get('user_id'))
        if ok:
            _sincronizar_sessao()
        flash(msg, 'success' if ok else 'error')
    except Exception as e:
        logger.error(f"auth_routes.perfil_foto_remover: {e}")
        flash('Erro ao remover a foto.', 'error')
    return redirect(url_for('auth.perfil'))

@auth_bp.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    confirmar = request.form.get('confirmar_senha')

    if not senha_atual or not nova_senha:
        flash('Preencha todos os campos.', 'error')
        return redirect(url_for('auth.perfil') + '#seguranca')

    if nova_senha != confirmar:
        flash('As senhas não coincidem.', 'error')
        return redirect(url_for('auth.perfil') + '#seguranca')

    minimo = seguranca.senha_minimo()
    if len(nova_senha) < minimo:
        flash(f'A nova senha deve ter pelo menos {minimo} caracteres.', 'error')
        return redirect(url_for('auth.perfil') + '#seguranca')

    login = session.get('login')
    if not login:
        flash('Sessão expirada. Faça login novamente.', 'error')
        return redirect(url_for('auth.login'))

    usuario, erro = auth.autenticar_usuario(login, senha_atual)
    if not usuario:
        flash('Senha atual incorreta.', 'error')
        return redirect(url_for('auth.perfil') + '#seguranca')

    novo_hash = generate_password_hash(nova_senha)
    try:
        executar_query(
            "UPDATE usuarios SET senha_hash = %s WHERE login = %s",
            (novo_hash, login)
        )
        flash('Senha alterada com sucesso!', 'success')
    except Exception as e:
        logger.error(f"auth_routes.alterar_senha: {e}")
        flash('Erro ao alterar senha.', 'error')

    return redirect(url_for('auth.perfil') + '#seguranca')