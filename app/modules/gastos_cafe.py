"""
Gastos do manejo do café: mão de obra (diária, produção, empreita) e serviços.

Valor total:
- diária:   pessoas × dias × valor da diária
- produção: quantidade (latas, medidas, sacos) × valor por unidade
- empreita: valor fechado informado
"""
import os
import sys
from datetime import date, datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query  # noqa: E402
from app.models import get_logger  # noqa: E402
from app.modules import calendario_cafe  # noqa: E402

logger = get_logger(__name__)

CATEGORIAS = [
    'Desbrota', 'Panha manual', 'Varrição', 'Arruação', 'Capina / roçada', 'Poda',
    'Adubação (mão de obra)', 'Pulverização (mão de obra)', 'Secagem / terreiro',
    'Transporte', 'Outros',
]
FORMAS = {
    'diaria': 'Diária',
    'producao': 'Por produção',
    'empreita': 'Empreita',
}
UNIDADES_PRODUCAO = ['lata', 'medida', 'saco', 'balaio', 'kg']


def _numero(valor, padrao=None):
    if valor is None or str(valor).strip() == '':
        return padrao
    texto = str(valor).strip().replace(' ', '')
    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.') if texto.rfind(',') > texto.rfind('.') else texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return float(texto)
    except (TypeError, ValueError):
        return padrao


def _data(valor):
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def calcular_total(forma, pessoas, quantidade, valor_unitario, valor_total=None):
    if forma == 'diaria':
        return round((pessoas or 1) * (quantidade or 0) * (valor_unitario or 0), 2)
    if forma == 'producao':
        return round((quantidade or 0) * (valor_unitario or 0), 2)
    return round(valor_total or 0, 2)


def _validar(dados):
    categoria = dados.get('categoria')
    if categoria not in CATEGORIAS:
        return None, 'Escolha a categoria do gasto.'
    forma = dados.get('forma_pagamento')
    if forma not in FORMAS:
        return None, 'Escolha a forma de pagamento.'
    data_gasto = _data(dados.get('data_gasto')) or date.today()
    pessoas = int(_numero(dados.get('pessoas'), 1) or 1) if forma == 'diaria' else 1
    if forma == 'diaria':
        quantidade = _numero(dados.get('dias'), 0)
        unidade = 'diária'
        valor_unitario = _numero(dados.get('valor_diaria'), 0)
    elif forma == 'producao':
        quantidade = _numero(dados.get('quantidade'), 0)
        unidade = dados.get('unidade') if dados.get('unidade') in UNIDADES_PRODUCAO else 'lata'
        valor_unitario = _numero(dados.get('valor_unidade'), 0)
    else:
        quantidade, unidade, valor_unitario = 1, 'serviço', None
    if pessoas < 1:
        return None, 'Informe ao menos 1 pessoa.'
    if forma != 'empreita' and (not quantidade or quantidade <= 0 or not valor_unitario or valor_unitario <= 0):
        return None, 'Informe a quantidade e o valor por unidade.'
    total = calcular_total(forma, pessoas, quantidade, valor_unitario, _numero(dados.get('valor_total'), 0))
    if total <= 0:
        return None, 'O valor total precisa ser maior que zero.'
    try:
        talhao_id = int(dados.get('talhao_id')) if dados.get('talhao_id') else None
    except (TypeError, ValueError):
        talhao_id = None
    return {
        'data_gasto': data_gasto,
        'safra': calendario_cafe.safra_de(data_gasto),
        'categoria': categoria,
        'descricao': (dados.get('descricao') or '').strip()[:200] or None,
        'forma_pagamento': forma,
        'talhao_id': talhao_id,
        'trabalhador': (dados.get('trabalhador') or '').strip()[:150] or None,
        'pessoas': pessoas,
        'quantidade': quantidade,
        'unidade': unidade,
        'valor_unitario': valor_unitario,
        'valor_total': total,
        'pago': str(dados.get('pago') or '').lower() in ('on', '1', 'true', 'sim'),
        'observacoes': (dados.get('observacoes') or '').strip() or None,
    }, None


def salvar(gasto_id, dados, usuario=None):
    valores, erro = _validar(dados)
    if erro:
        return False, erro
    campos = ['data_gasto', 'safra', 'categoria', 'descricao', 'forma_pagamento', 'talhao_id',
              'trabalhador', 'pessoas', 'quantidade', 'unidade', 'valor_unitario', 'valor_total',
              'pago', 'observacoes']
    params = tuple(valores[c] for c in campos)
    try:
        if gasto_id:
            executar_query(
                "UPDATE cafe_gastos SET " + ", ".join(f"{c} = %s" for c in campos)
                + " WHERE id = %s AND ativo = TRUE",
                params + (gasto_id,))
            return True, 'Gasto atualizado.'
        executar_query(
            "INSERT INTO cafe_gastos (" + ", ".join(campos) + ", usuario) VALUES ("
            + ", ".join(['%s'] * (len(campos) + 1)) + ")",
            params + (usuario,))
        return True, 'Gasto registrado.'
    except Exception as e:
        logger.error(f"gastos_cafe.salvar: {e}")
        return False, 'Não foi possível salvar o gasto.'


def excluir(gasto_id):
    try:
        executar_query("UPDATE cafe_gastos SET ativo = FALSE WHERE id = %s", (gasto_id,))
        return True, 'Gasto removido.'
    except Exception as e:
        logger.error(f"gastos_cafe.excluir: {e}")
        return False, 'Não foi possível remover o gasto.'


def marcar_pago(gasto_id):
    try:
        executar_query("UPDATE cafe_gastos SET pago = TRUE WHERE id = %s AND ativo = TRUE", (gasto_id,))
        return True, 'Pagamento registrado.'
    except Exception as e:
        logger.error(f"gastos_cafe.marcar_pago: {e}")
        return False, 'Não foi possível registrar o pagamento.'


def _filtros(safra=None, categoria=None, talhao_id=None):
    condicoes, params = ['g.ativo = TRUE'], []
    if safra:
        condicoes.append('g.safra = %s')
        params.append(safra)
    if categoria:
        condicoes.append('g.categoria = %s')
        params.append(categoria)
    if talhao_id == 'geral':
        condicoes.append('g.talhao_id IS NULL')
    elif talhao_id:
        condicoes.append('g.talhao_id = %s')
        params.append(talhao_id)
    return ' AND '.join(condicoes), params


def listar(safra=None, categoria=None, talhao_id=None):
    where, params = _filtros(safra, categoria, talhao_id)
    try:
        return executar_query(f"""
            SELECT g.id, g.data_gasto, g.safra, g.categoria, g.descricao, g.forma_pagamento,
                   g.talhao_id, t.nome AS talhao_nome, g.trabalhador, g.pessoas, g.quantidade,
                   g.unidade, g.valor_unitario, g.valor_total, g.pago, g.observacoes
            FROM cafe_gastos g
            LEFT JOIN talhoes t ON t.id = g.talhao_id
            WHERE {where}
            ORDER BY g.data_gasto DESC, g.id DESC
        """, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"gastos_cafe.listar: {e}")
        return []


def buscar(gasto_id):
    try:
        return executar_query("""
            SELECT id, data_gasto, safra, categoria, descricao, forma_pagamento, talhao_id,
                   trabalhador, pessoas, quantidade, unidade, valor_unitario, valor_total, pago, observacoes
            FROM cafe_gastos WHERE id = %s AND ativo = TRUE
        """, (gasto_id,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"gastos_cafe.buscar: {e}")
        return None


def resumo(safra=None, categoria=None, talhao_id=None):
    where, params = _filtros(safra, categoria, talhao_id)
    vazio = {'total': 0, 'lancamentos': 0, 'a_pagar': 0, 'pendentes': 0, 'mes_atual': 0,
             'por_categoria': [], 'por_talhao': [], 'area_total': 0}
    try:
        linha = executar_query(f"""
            SELECT COALESCE(SUM(g.valor_total), 0) AS total, COUNT(*) AS lancamentos,
                   COALESCE(SUM(CASE WHEN NOT g.pago THEN g.valor_total ELSE 0 END), 0) AS a_pagar,
                   COALESCE(SUM(CASE WHEN NOT g.pago THEN 1 ELSE 0 END), 0) AS pendentes,
                   COALESCE(SUM(CASE WHEN g.data_gasto >= date_trunc('month', CURRENT_DATE)
                                     THEN g.valor_total ELSE 0 END), 0) AS mes_atual
            FROM cafe_gastos g WHERE {where}
        """, tuple(params), fetch_one=True, dict_cursor=True) or {}
        por_categoria = executar_query(f"""
            SELECT g.categoria, SUM(g.valor_total) AS total, COUNT(*) AS quantidade
            FROM cafe_gastos g WHERE {where}
            GROUP BY g.categoria ORDER BY total DESC
        """, tuple(params), fetch_all=True, dict_cursor=True) or []
        por_talhao = executar_query(f"""
            SELECT g.talhao_id, COALESCE(t.nome, 'Geral (sem talhão)') AS nome,
                   t.area_hectares AS area, SUM(g.valor_total) AS total
            FROM cafe_gastos g LEFT JOIN talhoes t ON t.id = g.talhao_id
            WHERE {where}
            GROUP BY g.talhao_id, t.nome, t.area_hectares ORDER BY total DESC
        """, tuple(params), fetch_all=True, dict_cursor=True) or []
        return {
            'total': float(linha.get('total') or 0),
            'lancamentos': int(linha.get('lancamentos') or 0),
            'a_pagar': float(linha.get('a_pagar') or 0),
            'pendentes': int(linha.get('pendentes') or 0),
            'mes_atual': float(linha.get('mes_atual') or 0),
            'por_categoria': [{'categoria': r['categoria'], 'total': float(r['total'] or 0),
                               'quantidade': int(r['quantidade'] or 0)} for r in por_categoria],
            'por_talhao': [{'talhao_id': r['talhao_id'], 'nome': r['nome'],
                            'area': float(r['area'] or 0), 'total': float(r['total'] or 0),
                            'por_ha': (float(r['total'] or 0) / float(r['area'])) if r['area'] else None}
                           for r in por_talhao],
        }
    except Exception as e:
        logger.error(f"gastos_cafe.resumo: {e}")
        return vazio
