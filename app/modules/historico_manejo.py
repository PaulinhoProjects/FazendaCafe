"""
Módulo de Histórico de Manejo — AgroCafé

Reúne as aplicações já concluídas, a eficácia avaliada pelo agronomista e
os produtos usados, permitindo comparar manejo por talhão e por safra/ano.
"""

import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

logger = logging.getLogger(__name__)


def _clausulas(talhao_id=None, ano=None, periodo_id=None):
    condicoes = ["at.ativo = TRUE", "at.status = 'aplicada'"]
    params = []
    if talhao_id:
        condicoes.append('at.talhao_id = %s')
        params.append(talhao_id)
    if ano:
        condicoes.append("EXTRACT(YEAR FROM COALESCE(at.data_aplicacao, at.data_conclusao::date))::int = %s")
        params.append(int(ano))
    if periodo_id:
        condicoes.append('r.periodo_id = %s')
        params.append(periodo_id)
    return ' WHERE ' + ' AND '.join(condicoes), tuple(params)


def anos_disponiveis():
    """Anos com aplicação concluída, do mais recente para o mais antigo."""
    try:
        registros = executar_query("""
            SELECT DISTINCT EXTRACT(YEAR FROM COALESCE(at.data_aplicacao,
                          at.data_conclusao::date))::int AS ano
            FROM aplicacao_tarefas at
            WHERE at.ativo = TRUE AND at.status = 'aplicada'
            ORDER BY ano DESC
        """, fetch_all=True, dict_cursor=True) or []
        return [r['ano'] for r in registros if r['ano'] is not None]
    except Exception as e:
        logger.error(f"historico_manejo.anos_disponiveis: {e}")
        return []


def listar_aplicacoes(talhao_id=None, ano=None, periodo_id=None):
    """Histórico detalhado, já com produtos e avaliação de eficácia."""
    where, params = _clausulas(talhao_id, ano, periodo_id)
    query = """
    SELECT at.id, at.data_aplicacao, at.hora_aplicacao, at.responsavel,
           t.nome AS talhao_nome, r.nome AS receita_nome,
           pl.nome AS periodo_nome,
           EXTRACT(YEAR FROM COALESCE(at.data_aplicacao,
                  at.data_conclusao::date))::int AS ano,
           ae.resultado, ae.nota, ae.data_avaliacao, ae.agronomista,
           ae.observacoes,
           (SELECT STRING_AGG(COALESCE(pe.nome, i.produto_nome), ', ' ORDER BY COALESCE(pe.nome, i.produto_nome))
            FROM aplicacao_tarefa_itens i
            LEFT JOIN produtos_estoque pe ON pe.id = i.produto_id
            WHERE i.tarefa_id = at.id AND i.ativo = TRUE) AS produtos,
           (SELECT SUM(i.quantidade)
            FROM aplicacao_tarefa_itens i
            WHERE i.tarefa_id = at.id AND i.ativo = TRUE) AS quantidade_total
    FROM aplicacao_tarefas at
    JOIN talhoes t ON t.id = at.talhao_id
    JOIN receitas r ON r.id = at.receita_id
    LEFT JOIN periodos_lavoura pl ON pl.id = r.periodo_id
    LEFT JOIN avaliacoes_eficacia ae ON ae.tarefa_id = at.id AND ae.ativo = TRUE
    """ + where + """
    ORDER BY at.data_aplicacao DESC NULLS LAST, at.data_conclusao DESC, at.id DESC
    """
    try:
        registros = executar_query(query, params, fetch_all=True, dict_cursor=True) or []
        return [{
            'id': r['id'],
            'ano': r['ano'],
            'data': r['data_aplicacao'],
            'hora': r['hora_aplicacao'] or '',
            'talhao': r['talhao_nome'],
            'receita': r['receita_nome'],
            'periodo': r['periodo_nome'] or '—',
            'responsavel': r['responsavel'] or '—',
            'produtos': r['produtos'] or '—',
            'quantidade': float(r['quantidade_total'] or 0),
            'resultado': r['resultado'] or '',
            'nota': r['nota'],
            'data_avaliacao': r['data_avaliacao'],
            'agronomista': r['agronomista'] or '',
            'observacoes': r['observacoes'] or '',
        } for r in registros]
    except Exception as e:
        logger.error(f"historico_manejo.listar_aplicacoes: {e}")
        return []


def resumo(aplicacoes):
    """Indicadores calculados a partir do histórico filtrado."""
    avaliadas = [a for a in aplicacoes if a['resultado']]
    eficientes = [a for a in avaliadas if a['resultado'] in ('excelente', 'bom')]
    notas = [a['nota'] for a in avaliadas if a['nota'] is not None]
    return {
        'total': len(aplicacoes),
        'avaliadas': len(avaliadas),
        'eficientes': len(eficientes),
        'taxa_sucesso': round(100 * len(eficientes) / len(avaliadas), 1) if avaliadas else 0,
        'nota_media': round(sum(notas) / len(notas), 1) if notas else 0,
        'talhoes': len({a['talhao'] for a in aplicacoes}),
        'receitas': len({a['receita'] for a in aplicacoes}),
    }


def por_safra(aplicacoes):
    """Agrupa o histórico por safra/ano para comparar safras diferentes."""
    grupos = {}
    for a in aplicacoes:
        ano = a['ano'] or 'sem data'
        grupo = grupos.setdefault(ano, {
            'ano': ano, 'total': 0, 'avaliadas': 0, 'eficientes': 0,
            'notas': [], 'quantidade': 0.0,
        })
        grupo['total'] += 1
        if a['resultado']:
            grupo['avaliadas'] += 1
            if a['resultado'] in ('excelente', 'bom'):
                grupo['eficientes'] += 1
        if a['nota'] is not None:
            grupo['notas'].append(a['nota'])
        grupo['quantidade'] += a['quantidade']

    resultado = []
    for ano, grupo in sorted(grupos.items(), key=lambda item: str(item[0]), reverse=True):
        resultado.append({
            'ano': ano,
            'total': grupo['total'],
            'avaliadas': grupo['avaliadas'],
            'taxa_sucesso': round(100 * grupo['eficientes'] / grupo['avaliadas'], 1)
                            if grupo['avaliadas'] else 0,
            'nota_media': round(sum(grupo['notas']) / len(grupo['notas']), 1)
                          if grupo['notas'] else 0,
            'quantidade': round(grupo['quantidade'], 2),
        })
    return resultado


def por_produto(talhao_id=None, ano=None, periodo_id=None):
    """Compara Produto x quantidade x eficácia."""
    where, params = _clausulas(talhao_id, ano, periodo_id)
    query = """
    SELECT COALESCE(pe.nome, i.produto_nome) AS produto,
           COUNT(DISTINCT at.id) AS aplicacoes,
           COALESCE(SUM(i.quantidade), 0) AS quantidade,
           COUNT(ae.id) AS avaliadas,
           COUNT(*) FILTER (WHERE ae.resultado IN ('excelente', 'bom')) AS eficientes,
           ROUND(AVG(ae.nota)::numeric, 1) AS nota_media
    FROM aplicacao_tarefas at
    JOIN receitas r ON r.id = at.receita_id
    JOIN aplicacao_tarefa_itens i ON i.tarefa_id = at.id AND i.ativo = TRUE
    LEFT JOIN produtos_estoque pe ON pe.id = i.produto_id
    LEFT JOIN avaliacoes_eficacia ae ON ae.tarefa_id = at.id AND ae.ativo = TRUE
    """ + where + """
    GROUP BY COALESCE(pe.nome, i.produto_nome)
    ORDER BY aplicacoes DESC, produto
    """
    try:
        registros = executar_query(query, params, fetch_all=True, dict_cursor=True) or []
        return [{
            'produto': r['produto'],
            'aplicacoes': r['aplicacoes'],
            'quantidade': float(r['quantidade'] or 0),
            'avaliadas': r['avaliadas'],
            'taxa_sucesso': round(100 * r['eficientes'] / r['avaliadas'], 1) if r['avaliadas'] else 0,
            'nota_media': float(r['nota_media']) if r['nota_media'] is not None else 0,
        } for r in registros]
    except Exception as e:
        logger.error(f"historico_manejo.por_produto: {e}")
        return []


def por_receita(talhao_id=None, ano=None, periodo_id=None):
    """Compara receitas usadas no recorte escolhido."""
    where, params = _clausulas(talhao_id, ano, periodo_id)
    query = """
    SELECT r.nome AS receita,
           COUNT(DISTINCT at.id) AS aplicacoes,
           COUNT(DISTINCT at.talhao_id) AS talhoes,
           COUNT(ae.id) AS avaliadas,
           COUNT(*) FILTER (WHERE ae.resultado IN ('excelente', 'bom')) AS eficientes,
           ROUND(AVG(ae.nota)::numeric, 1) AS nota_media
    FROM aplicacao_tarefas at
    JOIN receitas r ON r.id = at.receita_id
    LEFT JOIN avaliacoes_eficacia ae ON ae.tarefa_id = at.id AND ae.ativo = TRUE
    """ + where + """
    GROUP BY r.nome
    ORDER BY aplicacoes DESC, receita
    """
    try:
        registros = executar_query(query, params, fetch_all=True, dict_cursor=True) or []
        return [{
            'receita': r['receita'],
            'aplicacoes': r['aplicacoes'],
            'talhoes': r['talhoes'],
            'avaliadas': r['avaliadas'],
            'taxa_sucesso': round(100 * r['eficientes'] / r['avaliadas'], 1) if r['avaliadas'] else 0,
            'nota_media': float(r['nota_media']) if r['nota_media'] is not None else 0,
        } for r in registros]
    except Exception as e:
        logger.error(f"historico_manejo.por_receita: {e}")
        return []
