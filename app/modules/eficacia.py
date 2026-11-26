"""
Módulo de Eficácia — AgroCafé

Registra a avaliação do agronomista sobre o resultado do manejo aplicado.
A avaliação fica ligada à tarefa, ao talhão e à receita para alimentar
o histórico comparativo por safra.
"""

import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, transacao

logger = logging.getLogger(__name__)

RESULTADOS = {
    'excelente': 'Excelente',
    'bom': 'Bom',
    'regular': 'Regular',
    'ineficaz': 'Ineficaz',
}

CORES = {
    'excelente': 'success',
    'bom': 'primary',
    'regular': 'warning',
    'ineficaz': 'danger',
}


def _texto(valor):
    return str(valor or '').strip()


def buscar_avaliacao(tarefa_id):
    try:
        r = executar_query("""
            SELECT id, tarefa_id, talhao_id, receita_id, agronomista,
                   data_avaliacao, resultado, nota, observacoes
            FROM avaliacoes_eficacia
            WHERE tarefa_id = %s AND ativo = TRUE
        """, (tarefa_id,), fetch_one=True, dict_cursor=True)
        if not r:
            return None
        return {
            'id': r['id'],
            'tarefa_id': r['tarefa_id'],
            'resultado': r['resultado'],
            'rotulo': RESULTADOS.get(r['resultado'], r['resultado']),
            'cor': CORES.get(r['resultado'], 'secondary'),
            'nota': r['nota'],
            'observacoes': r['observacoes'] or '',
            'agronomista': r['agronomista'] or '',
            'data_avaliacao': r['data_avaliacao'],
        }
    except Exception as e:
        logger.error(f"eficacia.buscar_avaliacao: {e}")
        return None


def salvar_avaliacao(tarefa_id, dados, usuario):
    """Grava ou atualiza a avaliação em uma única transação."""
    resultado = _texto(dados.get('resultado')).lower()
    if resultado not in RESULTADOS:
        raise ValueError('Escolha um resultado para a eficácia.')

    nota = dados.get('nota')
    if nota not in (None, ''):
        try:
            nota = int(nota)
        except (TypeError, ValueError):
            raise ValueError('A nota deve ser um número inteiro.')
        if nota < 0 or nota > 10:
            raise ValueError('A nota deve estar entre 0 e 10.')
    else:
        nota = None

    data_avaliacao = _texto(dados.get('data_avaliacao'))
    if not data_avaliacao:
        raise ValueError('Informe a data da avaliação.')

    observacoes = _texto(dados.get('observacoes'))

    def operacao(cursor):
        cursor.execute("""
            SELECT at.id, at.status, at.talhao_id, at.receita_id,
                   t.nome AS talhao_nome
            FROM aplicacao_tarefas at
            JOIN talhoes t ON t.id = at.talhao_id
            WHERE at.id = %s AND at.ativo = TRUE
            FOR UPDATE OF at
        """, (tarefa_id,))
        tarefa = cursor.fetchone()
        if not tarefa:
            raise ValueError('Tarefa não encontrada.')
        if tarefa['status'] != 'aplicada':
            raise ValueError('Só é possível avaliar uma aplicação já concluída.')

        cursor.execute("""
            INSERT INTO avaliacoes_eficacia
                (tarefa_id, talhao_id, receita_id, agronomista, data_avaliacao,
                 resultado, nota, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tarefa_id) DO UPDATE SET
                agronomista = EXCLUDED.agronomista,
                data_avaliacao = EXCLUDED.data_avaliacao,
                resultado = EXCLUDED.resultado,
                nota = EXCLUDED.nota,
                observacoes = EXCLUDED.observacoes,
                ativo = TRUE,
                data_atualizacao = CURRENT_TIMESTAMP
        """, (tarefa_id, tarefa['talhao_id'], tarefa['receita_id'],
              _texto(usuario) or None, data_avaliacao, resultado, nota,
              observacoes or None))

        detalhes = (
            f"Eficácia registrada em {tarefa['talhao_nome']}: "
            f"{RESULTADOS[resultado]}" + (f" ({nota}/10)." if nota is not None else ".")
        )
        cursor.execute("""
            INSERT INTO aplicacao_tarefa_log (tarefa_id, acao, detalhes, usuario)
            VALUES (%s, %s, %s, %s)
        """, (tarefa_id, 'eficacia', detalhes, _texto(usuario) or None))
        return tarefa_id

    try:
        with transacao() as cursor:
            return operacao(cursor)
    except Exception as e:
        logger.error(f"eficacia.salvar_avaliacao: {e}")
        raise
