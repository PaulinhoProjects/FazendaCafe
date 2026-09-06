from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.modules.login_manager import login_required
from config.database import get_config, set_config, executar_query

config_bp = Blueprint('config', __name__, url_prefix='/configuracoes')

def admin_required(f):
    """Decorator que exige que o usuário seja admin."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('tipo') != 'admin':
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@config_bp.route('/')
@login_required
@admin_required
def index():
    configs = {}
    try:
        resultado = executar_query("SELECT chave, valor, descricao FROM configuracoes_sistema ORDER BY chave", fetch_all=True)
        for r in resultado:
            configs[r[0]] = {'valor': r[1], 'descricao': r[2]}
    except Exception:
        pass
    return render_template('config/index.html', configs=configs)

@config_bp.route('/salvar', methods=['POST'])
@login_required
@admin_required
def salvar():
    try:
        chaves = request.form.getlist('chaves')
        for chave in chaves:
            valor = request.form.get(f'valor_{chave}')
            if valor is not None:
                set_config(chave, valor)
        flash('Configurações salvas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao salvar: {e}', 'error')
    return redirect(url_for('config.index'))
