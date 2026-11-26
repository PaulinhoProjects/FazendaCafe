from flask import Blueprint, render_template, flash, redirect, request, url_for
from app.modules import cotacoes
from app.modules.login_manager import login_required, admin_required
from app.models import get_logger
from config.database import get_config

logger = get_logger(__name__)
cotacoes_bp = Blueprint('cotacoes', __name__, url_prefix='/cotacoes')


def _paginacao():
    """Página e tamanho da página, definidos em Configurações > Sistema."""
    try:
        por_pagina = max(5, min(100, int(get_config('itens_por_pagina', 20))))
    except (TypeError, ValueError):
        por_pagina = 20
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except (TypeError, ValueError):
        pagina = 1
    return pagina, por_pagina


def _total_paginas(total, por_pagina):
    return max(1, (total + por_pagina - 1) // por_pagina)


@cotacoes_bp.route('/')
@login_required
def index():
    try:
        dados = cotacoes.obter_cotacoes()
        pagina, por_pagina = _paginacao()
        total = cotacoes.contar_historico()
        total_paginas = _total_paginas(total, por_pagina)
        pagina = min(pagina, total_paginas)
        historico = cotacoes.listar_historico(por_pagina, (pagina - 1) * por_pagina)
        return render_template(
            'cotacoes/index.html', cotacoes=dados, historico=historico,
            pagina=pagina, total_paginas=total_paginas, total_registros=total,
            por_pagina=por_pagina,
        )
    except Exception as e:
        logger.error(f"cotacoes_routes.index: {e}")
        flash('Erro ao carregar as cotações.', 'error')
        return render_template(
            'cotacoes/index.html', cotacoes=None, historico=[],
            pagina=1, total_paginas=1, total_registros=0, por_pagina=20,
        )


@cotacoes_bp.route('/atualizar', methods=['POST'])
@login_required
@admin_required
def atualizar():
    try:
        cotacoes.limpar_cache()
        dados = cotacoes.obter_cotacoes(force=True)
        if dados and not dados.get('stale'):
            flash('Cotações atualizadas com sucesso.', 'success')
        else:
            flash('Fontes indisponíveis: exibindo o último snapshot salvo.', 'warning')
    except Exception as e:
        logger.error(f"cotacoes_routes.atualizar: {e}")
        flash('Erro ao atualizar as cotações.', 'error')
    return redirect(request.referrer or url_for('cotacoes.index'))


@cotacoes_bp.route('/saude')
@login_required
@admin_required
def saude():
    """Painel administrativo de integridade das fontes externas."""
    pagina, por_pagina = _paginacao()
    total = cotacoes.contar_saude_eventos()
    total_paginas = _total_paginas(total, por_pagina)
    pagina = min(pagina, total_paginas)
    try:
        estado = cotacoes.verificar_fontes()
    except Exception as e:
        logger.error(f"cotacoes_routes.saude: {e}")
        flash('Não foi possível verificar as fontes agora; exibindo o último registro.', 'warning')
        estado = cotacoes.resumo_saude()
    return render_template(
        'cotacoes/saude.html', saude=estado,
        eventos=cotacoes.listar_saude_eventos(por_pagina, (pagina - 1) * por_pagina),
        pagina=pagina, total_paginas=total_paginas, total_registros=total,
        por_pagina=por_pagina,
    )


@cotacoes_bp.route('/saude/verificar', methods=['POST'])
@login_required
@admin_required
def saude_verificar():
    try:
        estado = cotacoes.verificar_fontes(force=True)
        if estado.get('geral') == 'ok':
            flash('Todas as fontes responderam normalmente.', 'success')
        elif estado.get('geral') == 'aviso':
            flash('Verificação concluída com avisos. Confira os detalhes abaixo.', 'warning')
        else:
            flash('Falha em uma ou mais fontes. Confira os detalhes abaixo.', 'error')
    except Exception as e:
        logger.error(f"cotacoes_routes.saude_verificar: {e}")
        flash('Erro ao verificar as fontes.', 'error')
    return redirect(url_for('cotacoes.saude'))
