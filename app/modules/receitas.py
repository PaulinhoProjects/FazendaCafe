"""
Módulo de Receitas Estruturadas — AgroCafé

Liga a receita de pulverização aos produtos do estoque e a vários talhões.
A gravação completa (receita + itens + talhões + produtos novos) acontece
em uma única transação, com rollback se qualquer passo falhar.
"""

import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, transacao
from app.modules import fila_aplicacao

logger = logging.getLogger(__name__)

UNIDADES_PERMITIDAS = ('L', 'kg', 'g', 'ml', 'sc', 'un')


def _numero(valor, nome):
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        raise ValueError(f'{nome} inválido')


def _inteiro_opcional(valor):
    if valor is None or str(valor).strip() == '':
        return None
    return int(valor)


def listar_itens(receita_id):
    """Itens de uma receita com saldo atual do produto no estoque."""
    query = """
    SELECT ri.id, ri.produto_id, ri.produto_nome, ri.dose, ri.unidade,
           ri.observacoes, p.nome AS produto_cadastrado,
           p.quantidade_atual AS saldo
    FROM receita_itens ri
    LEFT JOIN produtos_estoque p ON p.id = ri.produto_id
    WHERE ri.receita_id = %s AND ri.ativo = TRUE
    ORDER BY ri.id
    """
    try:
        registros = executar_query(query, (receita_id,), fetch_all=True, dict_cursor=True)
        itens = []
        for r in registros or []:
            itens.append({
                'id': r['id'],
                'produto_id': r['produto_id'],
                'nome': r['produto_cadastrado'] or r['produto_nome'] or 'Sem nome',
                'dose': float(r['dose']),
                'unidade': r['unidade'],
                'observacoes': r['observacoes'] or '',
                'saldo': float(r['saldo'] or 0),
                'cadastrado': r['produto_id'] is not None,
            })
        return itens
    except Exception as e:
        logger.error(f"receitas.listar_itens: {e}")
        return []


def listar_talhoes(receita_id):
    """Talhões destinatários de uma receita."""
    query = """
    SELECT rt.talhao_id, t.nome, rt.area_hectares, t.latitude, t.longitude
    FROM receita_talhoes rt
    JOIN talhoes t ON t.id = rt.talhao_id
    WHERE rt.receita_id = %s AND rt.ativo = TRUE
    ORDER BY t.nome
    """
    try:
        registros = executar_query(query, (receita_id,), fetch_all=True, dict_cursor=True)
        return [{
            'id': r['talhao_id'],
            'nome': r['nome'],
            'area': float(r['area_hectares']),
            'latitude': float(r['latitude']) if r['latitude'] else None,
            'longitude': float(r['longitude']) if r['longitude'] else None,
        } for r in registros or []]
    except Exception as e:
        logger.error(f"receitas.listar_talhoes: {e}")
        return []


def resumo_compras(receita_id):
    """Compara a necessidade calculada com o saldo atual de cada produto."""
    talhoes = listar_talhoes(receita_id)
    itens = listar_itens(receita_id)
    area_total = sum(t['area'] for t in talhoes)

    resumo = []
    for item in itens:
        necessario = item['dose'] * area_total
        falta = max(0.0, necessario - item['saldo'])
        resumo.append({
            'nome': item['nome'],
            'unidade': item['unidade'],
            'dose': item['dose'],
            'area_total': area_total,
            'necessario': round(necessario, 3),
            'saldo': round(item['saldo'], 3),
            'faltante': round(falta, 3),
            'cadastrado': item['cadastrado'],
        })
    return {
        'area_total': round(area_total, 2),
        'total_talhoes': len(talhoes),
        'itens': resumo,
        'itens_faltantes': sum(1 for i in resumo if i['faltante'] > 0),
    }


def contar_talhoes_por_receita():
    """Mapa receita_id -> (quantidade de talhões, área total) para listagens."""
    query = """
    SELECT receita_id, COUNT(*) AS total, COALESCE(SUM(area_hectares), 0) AS area
    FROM receita_talhoes
    WHERE ativo = TRUE
    GROUP BY receita_id
    """
    try:
        registros = executar_query(query, fetch_all=True, dict_cursor=True)
        return {r['receita_id']: {'total': r['total'], 'area': float(r['area'])}
                for r in registros or []}
    except Exception as e:
        logger.error(f"receitas.contar_talhoes_por_receita: {e}")
        return {}


def _validar(dados, itens, talhao_ids):
    nome = str(dados.get('nome') or '').strip()
    if not nome:
        raise ValueError('Informe o nome da receita.')

    itens_validos = []
    for item in itens or []:
        produto_id = _inteiro_opcional(item.get('produto_id'))
        produto_nome = str(item.get('produto_nome') or '').strip()
        dose = _numero(item.get('dose'), 'Dose')
        unidade = str(item.get('unidade') or 'L').strip()
        if not produto_id and not produto_nome:
            raise ValueError('Informe o nome do produto de cada item.')
        if dose <= 0:
            raise ValueError('A dose deve ser maior que zero.')
        if unidade not in UNIDADES_PERMITIDAS:
            raise ValueError(f'Unidade inválida: {unidade}')
        itens_validos.append({
            'produto_id': produto_id,
            'produto_nome': produto_nome,
            'dose': round(dose, 3),
            'unidade': unidade,
            'observacoes': str(item.get('observacoes') or '').strip(),
        })
    if not itens_validos:
        raise ValueError('Adicione pelo menos um produto à receita.')

    if not talhao_ids:
        raise ValueError('Selecione pelo menos um talhão.')

    ids = []
    for valor in talhao_ids:
        try:
            ids.append(int(valor))
        except (TypeError, ValueError):
            raise ValueError('Talhão inválido na seleção.')
    ids = list(dict.fromkeys(ids))

    consulta = """
    SELECT id, nome, area_hectares FROM talhoes
    WHERE ativo = TRUE AND id = ANY(%s)
    """
    encontrados = executar_query(consulta, (ids,), fetch_all=True, dict_cursor=True) or []
    if len(encontrados) != len(ids):
        raise ValueError('Um ou mais talhões selecionados não estão ativos.')
    talhoes = [{'id': r['id'], 'nome': r['nome'], 'area': float(r['area_hectares'] or 0)}
               for r in encontrados]
    return nome, itens_validos, talhoes


def salvar_receita(dados, itens, talhao_ids, receita_id=None):
    """
    Grava receita, itens, talhões e produtos novos em UMA transação.
    Retorna (receita_id, resumo).
    """
    nome, itens_validos, talhoes = _validar(dados, itens, talhao_ids)
    periodo_id = _inteiro_opcional(dados.get('periodo_id'))
    descricao = str(dados.get('descricao') or '').strip()
    observacoes = str(dados.get('observacoes') or '').strip()
    area_total = sum(t['area'] for t in talhoes)

    texto_produtos = '; '.join(
        f"{i['produto_nome'] or i['produto_id']} {i['dose']} {i['unidade']}/ha"
        for i in itens_validos
    )
    texto_formula = f"{texto_produtos} — {area_total:.2f} ha em {len(talhoes)} talhão(ões)"

    def operacao(cursor):
        rid = receita_id
        # Produtos indicados na receita mas ausentes no estoque entram com saldo zero.
        resolvidos = []
        for item in itens_validos:
            produto_id = item['produto_id']
            produto_nome = item['produto_nome']
            if not produto_id:
                cursor.execute(
                    "SELECT id, unidade FROM produtos_estoque WHERE LOWER(nome) = LOWER(%s) LIMIT 1",
                    (produto_nome,)
                )
                existente = cursor.fetchone()
                if existente:
                    produto_id = existente['id']
                else:
                    cursor.execute("""
                        INSERT INTO produtos_estoque
                            (nome, unidade, estoque_minimo, quantidade_atual, observacoes, categoria)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (produto_nome, item['unidade'], 0, 0,
                          'Criado automaticamente a partir de uma receita de pulverização.', 'Outros'))
                    produto_id = cursor.fetchone()['id']
            resolvidos.append((produto_id, produto_nome, item))

        if rid:
            cursor.execute("""
                UPDATE receitas SET nome = %s, periodo_id = %s, descricao = %s,
                    formula_completa = %s, produtos = %s, observacoes = %s
                WHERE id = %s AND ativo = TRUE
            """, (nome, periodo_id, descricao, texto_formula, texto_produtos, observacoes, rid))
            if cursor.rowcount == 0:
                raise ValueError('Receita não encontrada para edição.')
            cursor.execute("UPDATE receita_itens SET ativo = FALSE WHERE receita_id = %s", (rid,))
            cursor.execute("UPDATE receita_talhoes SET ativo = FALSE WHERE receita_id = %s", (rid,))
        else:
            cursor.execute("""
                INSERT INTO receitas
                    (nome, periodo_id, descricao, formula_completa, produtos, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (nome, periodo_id, descricao, texto_formula, texto_produtos, observacoes))
            rid = cursor.fetchone()['id']

        for produto_id, produto_nome, item in resolvidos:
            cursor.execute("""
                INSERT INTO receita_itens
                    (receita_id, produto_id, produto_nome, dose, unidade, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (rid, produto_id, produto_nome, item['dose'],
                  item['unidade'], item['observacoes']))

        for talhao in talhoes:
            cursor.execute("""
                INSERT INTO receita_talhoes (receita_id, talhao_id, area_hectares)
                VALUES (%s, %s, %s)
                ON CONFLICT (receita_id, talhao_id)
                DO UPDATE SET area_hectares = EXCLUDED.area_hectares, ativo = TRUE
            """, (rid, talhao['id'], talhao['area']))

        # Cada talhão vira uma tarefa da fila, na mesma transação da receita.
        fila_aplicacao.sincronizar_tarefas(
            cursor, rid, resolvidos, talhoes, dados.get('_usuario')
        )

        return rid

    try:
        with transacao() as cursor:
            receita_id = operacao(cursor)
    except Exception as e:
        logger.error(f"receitas.salvar_receita: {e}")
        raise

    return receita_id, resumo_compras(receita_id)


def desativar_detalhes(receita_id):
    """Desativa itens e talhões junto com a receita (exclusão lógica)."""
    try:
        with transacao() as cursor:
            cursor.execute("UPDATE receita_itens SET ativo = FALSE WHERE receita_id = %s", (receita_id,))
            cursor.execute("UPDATE receita_talhoes SET ativo = FALSE WHERE receita_id = %s", (receita_id,))
            fila_aplicacao.desativar_pendentes(cursor, receita_id)
        return True
    except Exception as e:
        logger.error(f"receitas.desativar_detalhes: {e}")
        return False
