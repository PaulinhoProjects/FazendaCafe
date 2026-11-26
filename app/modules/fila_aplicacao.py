"""
Módulo da Fila de Aplicação — AgroCafé

Transforma cada talhão de uma receita em uma tarefa de campo. A marcação
como aplicada captura data, hora e clima e desconta o estoque em UMA
transação, com rollback se qualquer passo falhar.
"""

import logging
import math
import os
import sys
from datetime import datetime, date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, transacao

logger = logging.getLogger(__name__)

STATUS_PENDENTE = 'pendente'
STATUS_APLICADA = 'aplicada'


class SaldoInsuficienteError(ValueError):
    """Saldo do estoque menor que o consumo da tarefa."""


_FATORES_UNIDADE = {
    ('ml', 'l'): 0.001,
    ('l', 'ml'): 1000.0,
    ('g', 'kg'): 0.001,
    ('kg', 'g'): 1000.0,
}


def _fator_para(origem, destino):
    """Converte a quantidade da unidade da dose para a unidade do estoque."""
    origem = _texto(origem).lower()
    destino = _texto(destino).lower()
    if origem == destino:
        return 1.0
    fator = _FATORES_UNIDADE.get((origem, destino))
    if fator is None:
        raise ValueError(
            f"Unidades incompatíveis: a receita usa {origem or '—'} e o estoque usa {destino or '—'}."
        )
    return fator


def _formatar_numero(valor, casas=3):
    texto = f'{float(valor or 0):.{casas}f}'.rstrip('0').rstrip('.')
    return (texto or '0').replace('.', ',')


def desativar_pendentes(cursor, receita_id, selecionados=None):
    """Desativa tarefas pendentes. Se receber uma lista, preserva só esses talhões."""
    query = """
        SELECT id FROM aplicacao_tarefas
        WHERE receita_id = %s AND ativo = TRUE AND status = %s
    """
    params = [receita_id, STATUS_PENDENTE]
    if selecionados is not None:
        if not selecionados:
            return
        query += " AND NOT (talhao_id = ANY(%s))"
        params.append(selecionados)
    cursor.execute(query, tuple(params))
    for r in cursor.fetchall():
        cursor.execute("UPDATE aplicacao_tarefa_itens SET ativo = FALSE WHERE tarefa_id = %s",
                       (r['id'],))
        cursor.execute("UPDATE aplicacao_tarefas SET ativo = FALSE WHERE id = %s", (r['id'],))


def _texto(valor):
    return str(valor or '').strip()


def sincronizar_tarefas(cursor, receita_id, produtos_resolvidos, talhoes, usuario):
    """
    Cria ou atualiza as tarefas de uma receita. Deve ser chamada DENTRO da
    transação que grava a receita. Tarefas já aplicadas nunca são reescritas.
    """
    for talhao in talhoes:
        cursor.execute("""
            SELECT id, status FROM aplicacao_tarefas
            WHERE receita_id = %s AND talhao_id = %s
        """, (receita_id, talhao['id']))
        atual = cursor.fetchone()

        if atual and atual['status'] == STATUS_APLICADA:
            continue

        if atual:
            tarefa_id = atual['id']
            cursor.execute("""
                UPDATE aplicacao_tarefas
                SET area_hectares = %s, responsavel = COALESCE(responsavel, %s), ativo = TRUE
                WHERE id = %s
            """, (talhao['area'], _texto(usuario) or None, tarefa_id))
            cursor.execute("UPDATE aplicacao_tarefa_itens SET ativo = FALSE WHERE tarefa_id = %s",
                           (tarefa_id,))
        else:
            cursor.execute("""
                INSERT INTO aplicacao_tarefas
                    (receita_id, talhao_id, status, area_hectares, criado_por)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (receita_id, talhao['id'], STATUS_PENDENTE,
                  talhao['area'], _texto(usuario) or None))
            tarefa_id = cursor.fetchone()['id']

        for produto_id, produto_nome, item in produtos_resolvidos:
            quantidade = float(item['dose']) * float(talhao['area'])
            cursor.execute("""
                INSERT INTO aplicacao_tarefa_itens
                    (tarefa_id, produto_id, produto_nome, dose, unidade, quantidade, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (tarefa_id, produto_id, produto_nome, item['dose'],
                  item['unidade'], round(quantidade, 3), item.get('observacoes') or None))

        cursor.execute("""
            INSERT INTO aplicacao_tarefa_log (tarefa_id, acao, detalhes, usuario)
            VALUES (%s, %s, %s, %s)
        """, (tarefa_id, 'sincronizada', 'Indicação atualizada pela receita.', _texto(usuario) or None))

    # Talhões retirados da receita saem da fila; os já aplicados ficam no histórico.
    desativar_pendentes(cursor, receita_id, [t['id'] for t in talhoes])


def _consulta_base():
    return """
    SELECT at.id, at.receita_id, at.talhao_id, at.status, at.responsavel,
           at.area_hectares, at.data_aplicacao, at.hora_aplicacao,
           at.clima_temperatura, at.clima_umidade, at.clima_descricao,
           at.clima_vento, at.clima_fonte, at.clima_atualizado,
           at.observacoes, at.concluido_por, at.data_conclusao, at.ativo,
           r.nome AS receita_nome, t.nome AS talhao_nome,
           (SELECT COUNT(*) FROM aplicacao_tarefa_itens i
            WHERE i.tarefa_id = at.id AND i.ativo = TRUE) AS total_itens
    FROM aplicacao_tarefas at
    JOIN receitas r ON r.id = at.receita_id
    JOIN talhoes t ON t.id = at.talhao_id
    """


def listar_tarefas(status=None, talhao_id=None, receita_id=None):
    """Tarefas da fila, agrupáveis por receita; pendentes primeiro."""
    query = _consulta_base()
    condicoes = ['at.ativo = TRUE']
    params = []
    if status:
        condicoes.append('at.status = %s')
        params.append(status)
    if talhao_id:
        condicoes.append('at.talhao_id = %s')
        params.append(talhao_id)
    if receita_id:
        condicoes.append('at.receita_id = %s')
        params.append(receita_id)
    query += ' WHERE ' + ' AND '.join(condicoes)
    query += (" ORDER BY r.nome, at.receita_id,"
              " CASE WHEN at.status = 'pendente' THEN 0 ELSE 1 END, t.nome, at.id")

    try:
        registros = executar_query(query, tuple(params) if params else None,
                                   fetch_all=True, dict_cursor=True)
        return [{
            'id': r['id'],
            'receita_id': r['receita_id'],
            'talhao_id': r['talhao_id'],
            'status': r['status'],
            'responsavel': r['responsavel'] or '',
            'area': float(r['area_hectares'] or 0),
            'data_aplicacao': r['data_aplicacao'],
            'hora_aplicacao': r['hora_aplicacao'] or '',
            'receita_nome': r['receita_nome'],
            'talhao_nome': r['talhao_nome'],
            'total_itens': r['total_itens'],
            'concluido_por': r['concluido_por'] or '',
        } for r in registros or []]
    except Exception as e:
        logger.error(f"fila_aplicacao.listar_tarefas: {e}")
        return []


def buscar_tarefa(tarefa_id):
    query = _consulta_base() + """
    WHERE at.id = %s AND at.ativo = TRUE
    """
    try:
        r = executar_query(query, (tarefa_id,), fetch_one=True, dict_cursor=True)
        if not r:
            return None
        return {
            'id': r['id'],
            'receita_id': r['receita_id'],
            'talhao_id': r['talhao_id'],
            'status': r['status'],
            'responsavel': r['responsavel'] or '',
            'area': float(r['area_hectares'] or 0),
            'data_aplicacao': r['data_aplicacao'],
            'hora_aplicacao': r['hora_aplicacao'] or '',
            'temperatura': float(r['clima_temperatura']) if r['clima_temperatura'] is not None else None,
            'umidade': r['clima_umidade'],
            'descricao_clima': r['clima_descricao'] or '',
            'vento': float(r['clima_vento']) if r['clima_vento'] is not None else None,
            'fonte_clima': r['clima_fonte'] or '',
            'atualizacao_clima': r['clima_atualizado'] or '',
            'observacoes': r['observacoes'] or '',
            'concluido_por': r['concluido_por'] or '',
            'data_conclusao': r['data_conclusao'],
            'receita_nome': r['receita_nome'],
            'talhao_nome': r['talhao_nome'],
        }
    except Exception as e:
        logger.error(f"fila_aplicacao.buscar_tarefa: {e}")
        return None


def listar_itens_tarefa(tarefa_id):
    query = """
    SELECT i.id, i.produto_id, i.produto_nome, i.dose, i.unidade,
           i.quantidade, i.saldo_anterior, i.saldo_posterior,
           p.nome AS produto_cadastrado, p.quantidade_atual AS saldo
    FROM aplicacao_tarefa_itens i
    LEFT JOIN produtos_estoque p ON p.id = i.produto_id
    WHERE i.tarefa_id = %s AND i.ativo = TRUE
    ORDER BY i.id
    """
    try:
        registros = executar_query(query, (tarefa_id,), fetch_all=True, dict_cursor=True)
        itens = []
        for r in registros or []:
            saldo = float(r['saldo'] or 0) if r['saldo'] is not None else None
            itens.append({
                'id': r['id'],
                'produto_id': r['produto_id'],
                'nome': r['produto_cadastrado'] or r['produto_nome'] or 'Sem nome',
                'dose': float(r['dose']),
                'unidade': r['unidade'],
                'quantidade': float(r['quantidade']),
                'saldo': saldo,
                'saldo_anterior': float(r['saldo_anterior']) if r['saldo_anterior'] is not None else None,
                'saldo_posterior': float(r['saldo_posterior']) if r['saldo_posterior'] is not None else None,
            })
        return itens
    except Exception as e:
        logger.error(f"fila_aplicacao.listar_itens_tarefa: {e}")
        return []


def opcoes_filtro_fila():
    """Receitas e talhões que têm tarefas na fila, com a contagem por situação."""
    vazio = {'receitas': [], 'talhoes': []}
    try:
        receitas = executar_query("""
            SELECT r.id, r.nome, r.data_cadastro,
                   SUM(CASE WHEN at.status = %s THEN 1 ELSE 0 END) AS pendentes,
                   SUM(CASE WHEN at.status = %s THEN 1 ELSE 0 END) AS aplicadas
            FROM aplicacao_tarefas at
            JOIN receitas r ON r.id = at.receita_id
            WHERE at.ativo = TRUE
            GROUP BY r.id, r.nome, r.data_cadastro
            ORDER BY SUM(CASE WHEN at.status = %s THEN 1 ELSE 0 END) > 0 DESC, r.nome
        """, (STATUS_PENDENTE, STATUS_APLICADA, STATUS_PENDENTE),
            fetch_all=True, dict_cursor=True) or []
        talhoes = executar_query("""
            SELECT DISTINCT t.id, t.nome
            FROM aplicacao_tarefas at
            JOIN talhoes t ON t.id = at.talhao_id
            WHERE at.ativo = TRUE
            ORDER BY t.nome
        """, fetch_all=True, dict_cursor=True) or []
        return {
            'receitas': [{
                'id': r['id'], 'nome': r['nome'], 'data_cadastro': r['data_cadastro'],
                'pendentes': int(r['pendentes'] or 0), 'aplicadas': int(r['aplicadas'] or 0),
            } for r in receitas],
            'talhoes': [{'id': t['id'], 'nome': t['nome']} for t in talhoes],
        }
    except Exception as e:
        logger.error(f"fila_aplicacao.opcoes_filtro_fila: {e}")
        return vazio


def contar_tarefas():
    try:
        registros = executar_query("""
            SELECT status, COUNT(*) AS total FROM aplicacao_tarefas
            WHERE ativo = TRUE GROUP BY status
        """, fetch_all=True, dict_cursor=True) or []
        contagem = {STATUS_PENDENTE: 0, STATUS_APLICADA: 0}
        for r in registros:
            contagem[r['status']] = r['total']
        return contagem
    except Exception as e:
        logger.error(f"fila_aplicacao.contar_tarefas: {e}")
        return {STATUS_PENDENTE: 0, STATUS_APLICADA: 0}


def listar_log(tarefa_id):
    try:
        registros = executar_query("""
            SELECT acao, detalhes, usuario, data_hora
            FROM aplicacao_tarefa_log
            WHERE tarefa_id = %s
            ORDER BY data_hora DESC, id DESC
            LIMIT 20
        """, (tarefa_id,), fetch_all=True, dict_cursor=True) or []
        return [{
            'acao': r['acao'], 'detalhes': r['detalhes'] or '',
            'usuario': r['usuario'] or '—', 'data_hora': r['data_hora'],
        } for r in registros]
    except Exception as e:
        logger.error(f"fila_aplicacao.listar_log: {e}")
        return []


def marcar_aplicada(tarefa_id, responsavel, observacoes, usuario, clima_atual=None):
    """
    Marca a tarefa como aplicada, registra clima/hora e desconta o estoque.
    Tudo acontece em UMA transação com rollback.
    """
    hoje = date.today().isoformat()
    agora = datetime.now().strftime('%H:%M')
    clima = clima_atual or {}

    def operacao(cursor):
        cursor.execute("""
            SELECT at.*, r.nome AS receita_nome, t.nome AS talhao_nome
            FROM aplicacao_tarefas at
            JOIN receitas r ON r.id = at.receita_id
            JOIN talhoes t ON t.id = at.talhao_id
            WHERE at.id = %s AND at.ativo = TRUE
            FOR UPDATE OF at
        """, (tarefa_id,))
        tarefa = cursor.fetchone()
        if not tarefa:
            raise ValueError('Tarefa não encontrada.')
        if tarefa['status'] != STATUS_PENDENTE:
            raise ValueError('Esta tarefa já foi marcada como aplicada.')

        cursor.execute("""
            SELECT id, produto_id, produto_nome, quantidade, unidade
            FROM aplicacao_tarefa_itens
            WHERE tarefa_id = %s AND ativo = TRUE
            ORDER BY id
        """, (tarefa_id,))
        itens = cursor.fetchall()

        for item in itens:
            if not item['produto_id']:
                raise ValueError(
                    f"O produto {item['produto_nome']} não está vinculado ao estoque."
                )
            quantidade = float(item['quantidade'] or 0)
            cursor.execute("""
                SELECT quantidade_atual, unidade FROM produtos_estoque
                WHERE id = %s AND ativo = TRUE FOR UPDATE
            """, (item['produto_id'],))
            produto = cursor.fetchone()
            if not produto:
                raise ValueError(f"Produto {item['produto_nome']} não está ativo no estoque.")
            unidade_estoque = produto['unidade'] or item['unidade']
            quantidade_estoque = quantidade * _fator_para(item['unidade'], unidade_estoque)
            if quantidade_estoque <= 0:
                raise ValueError(f"Quantidade inválida para {item['produto_nome']}.")

            saldo_anterior = float(produto['quantidade_atual'] or 0)
            if saldo_anterior + 0.000001 < quantidade_estoque:
                raise SaldoInsuficienteError(
                    f"Saldo insuficiente de {item['produto_nome']}: "
                    f"precisa de {_formatar_numero(quantidade_estoque)} {unidade_estoque} e "
                    f"há {_formatar_numero(saldo_anterior)} {unidade_estoque}. "
                    "Faça a entrada rápida antes de confirmar."
                )
            saldo_posterior = saldo_anterior - quantidade_estoque

            cursor.execute("""
                UPDATE produtos_estoque SET quantidade_atual = %s WHERE id = %s
            """, (saldo_posterior, item['produto_id']))

            detalhe_unidade = (
                '' if _texto(item['unidade']).lower() == _texto(unidade_estoque).lower()
                else f" ({_formatar_numero(quantidade)} {item['unidade']})"
            )
            cursor.execute("""
                INSERT INTO movimentacoes_estoque
                    (produto_id, tipo, quantidade, unidade, data_movimento, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (item['produto_id'], 'saída', quantidade_estoque, unidade_estoque, hoje,
                  f"Consumo da tarefa #{tarefa_id} — {tarefa['receita_nome']} / "
                  f"{tarefa['talhao_nome']}{detalhe_unidade}"))

            cursor.execute("""
                UPDATE aplicacao_tarefa_itens
                SET saldo_anterior = %s, saldo_posterior = %s
                WHERE id = %s
            """, (saldo_anterior, saldo_posterior, item['id']))

        descricao_clima = _texto(clima.get('descricao'))
        temperatura = clima.get('temperatura')
        umidade = clima.get('umidade')
        vento = clima.get('vento_velocidade')
        cursor.execute("""
            UPDATE aplicacao_tarefas SET
                status = %s,
                responsavel = %s,
                data_aplicacao = %s,
                hora_aplicacao = %s,
                clima_temperatura = %s,
                clima_umidade = %s,
                clima_descricao = %s,
                clima_vento = %s,
                clima_fonte = %s,
                clima_atualizado = %s,
                observacoes = %s,
                concluido_por = %s,
                data_conclusao = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (STATUS_APLICADA, _texto(responsavel) or _texto(usuario) or None,
              hoje, agora, temperatura, umidade, descricao_clima or None,
              vento, _texto(clima.get('fonte')) or None,
              _texto(clima.get('atualizacao')) or None,
              _texto(observacoes) or None, _texto(usuario) or None, tarefa_id))

        detalhes = (
            f"Marcada como aplicada em {hoje} às {agora}. "
            f"Clima: {descricao_clima or 'não informado'}, "
            f"{temperatura if temperatura is not None else '—'}°C, "
            f"umidade {umidade if umidade is not None else '—'}%. "
            f"Responsável: {_texto(responsavel) or _texto(usuario) or '—'}."
        )
        cursor.execute("""
            INSERT INTO aplicacao_tarefa_log (tarefa_id, acao, detalhes, usuario)
            VALUES (%s, %s, %s, %s)
        """, (tarefa_id, 'aplicada', detalhes, _texto(usuario) or None))
        return tarefa_id

    try:
        with transacao() as cursor:
            return operacao(cursor)
    except Exception as e:
        logger.error(f"fila_aplicacao.marcar_aplicada: {e}")
        raise


CAMPOS_EDITAVEIS = (
    'responsavel', 'observacoes', 'data_aplicacao', 'hora_aplicacao',
    'clima_temperatura', 'clima_umidade', 'clima_descricao', 'clima_vento',
)


def atualizar_tarefa(tarefa_id, dados, usuario):
    """Edita campos permitidos e registra cada alteração no log."""
    try:
        with transacao() as cursor:
            cursor.execute("""
                SELECT responsavel, observacoes, data_aplicacao, hora_aplicacao,
                       clima_temperatura, clima_umidade, clima_descricao, clima_vento
                FROM aplicacao_tarefas WHERE id = %s AND ativo = TRUE
            """, (tarefa_id,))
            anterior = cursor.fetchone()
            if not anterior:
                raise ValueError('Tarefa não encontrada.')

            colunas = []
            valores = []
            mudancas = []
            for campo in CAMPOS_EDITAVEIS:
                if campo not in dados:
                    continue
                valor = dados.get(campo)
                valor = valor.strip() if isinstance(valor, str) else valor
                antigo = anterior[campo]
                if valor == '' or valor is None:
                    valor = None
                if campo in ('clima_temperatura', 'clima_umidade', 'clima_vento'):
                    if valor is not None:
                        try:
                            valor = float(valor)
                        except (TypeError, ValueError):
                            raise ValueError(f'Valor inválido para {campo}.')
                if valor != antigo:
                    colunas.append(f'{campo} = %s')
                    valores.append(valor)
                    mudancas.append(f'{campo}: {antigo or "—"} → {valor or "—"}')

            if mudancas:
                valores.append(tarefa_id)
                cursor.execute(
                    'UPDATE aplicacao_tarefas SET ' + ', '.join(colunas) + ' WHERE id = %s',
                    tuple(valores)
                )
                cursor.execute("""
                    INSERT INTO aplicacao_tarefa_log (tarefa_id, acao, detalhes, usuario)
                    VALUES (%s, %s, %s, %s)
                """, (tarefa_id, 'edicao', '; '.join(mudancas), _texto(usuario) or None))
            return True
    except Exception as e:
        logger.error(f"fila_aplicacao.atualizar_tarefa: {e}")
        raise


def produtos_para_entrada_rapida(tarefa_id):
    """Produtos da tarefa cujo saldo não cobre o consumo, já na unidade do estoque."""
    try:
        registros = executar_query("""
            SELECT i.produto_id, i.produto_nome, i.quantidade, i.unidade AS unidade_item,
                   p.nome AS nome_produto, p.unidade AS unidade_produto,
                   p.quantidade_atual AS saldo
            FROM aplicacao_tarefa_itens i
            JOIN produtos_estoque p ON p.id = i.produto_id AND p.ativo = TRUE
            WHERE i.tarefa_id = %s AND i.ativo = TRUE
            ORDER BY i.id
        """, (tarefa_id,), fetch_all=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"fila_aplicacao.produtos_para_entrada_rapida: {e}")
        return []

    faltantes = []
    for r in registros or []:
        try:
            unidade = r['unidade_produto'] or r['unidade_item']
            necessario = float(r['quantidade'] or 0) * _fator_para(r['unidade_item'], unidade)
        except ValueError:
            continue
        saldo = float(r['saldo'] or 0)
        falta = max(0.0, necessario - saldo)
        if falta <= 0.000001:
            continue
        sugerido = math.ceil(falta * 100) / 100
        faltantes.append({
            'produto_id': r['produto_id'],
            'nome': r['nome_produto'] or r['produto_nome'] or 'Sem nome',
            'unidade': unidade,
            'saldo_txt': _formatar_numero(saldo),
            'necessario_txt': _formatar_numero(necessario),
            'falta_txt': _formatar_numero(falta),
            'sugerido_txt': _formatar_numero(sugerido, 2),
            'sugerido_input': f'{sugerido:.2f}',
        })
    return faltantes


def registrar_entrada_rapida(tarefa_id, entradas, nome_confirmado, login_confirmado, usuario_sessao):
    """
    Entra com produtos faltantes em UMA transação, exige confirmação validada
    na rota e registra tudo no histórico da tarefa.
    """
    login = _texto(login_confirmado)
    nome = _texto(nome_confirmado) or login
    if not login:
        raise ValueError('Informe o login para confirmar a entrada.')

    soma = {}
    for produto_id, quantidade in entradas or []:
        try:
            pid = int(produto_id)
            qtd = float(str(quantidade).strip().replace(',', '.'))
        except (TypeError, ValueError):
            raise ValueError('Quantidade inválida na entrada rápida.')
        if not math.isfinite(qtd) or qtd <= 0 or qtd > 999999999.99:
            raise ValueError('A quantidade deve estar entre 0,01 e 999999999,99.')
        if round(qtd, 2) != qtd:
            raise ValueError('A quantidade deve ter no máximo 2 casas decimais.')
        soma[pid] = soma.get(pid, 0.0) + qtd
    if not soma:
        raise ValueError('Selecione pelo menos um produto para a entrada rápida.')

    def operacao(cursor):
        cursor.execute("""
            SELECT at.status, t.nome AS talhao_nome
            FROM aplicacao_tarefas at
            JOIN talhoes t ON t.id = at.talhao_id
            WHERE at.id = %s AND at.ativo = TRUE FOR UPDATE OF at
        """, (tarefa_id,))
        tarefa = cursor.fetchone()
        if not tarefa:
            raise ValueError('Tarefa não encontrada.')
        if tarefa['status'] != STATUS_PENDENTE:
            raise ValueError('Esta tarefa já foi marcada como aplicada.')

        detalhes_itens = []
        for produto_id, quantidade in soma.items():
            cursor.execute("""
                SELECT nome, unidade FROM produtos_estoque
                WHERE id = %s AND ativo = TRUE FOR UPDATE
            """, (produto_id,))
            produto = cursor.fetchone()
            if not produto:
                raise ValueError('Um dos produtos não está ativo no estoque.')
            unidade = produto['unidade'] or ''
            cursor.execute("""
                INSERT INTO movimentacoes_estoque
                    (produto_id, tipo, quantidade, unidade, data_movimento, observacoes,
                     origem, confirmado_por, tarefa_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (produto_id, 'entrada', quantidade, unidade, date.today().isoformat(),
                  f"Entrada rápida — confirmada por {nome} ({login}) — "
                  f"tarefa #{tarefa_id} / {tarefa['talhao_nome']}",
                  'entrada_rapida', login, tarefa_id))
            cursor.execute("""
                UPDATE produtos_estoque
                SET quantidade_atual = quantidade_atual + %s WHERE id = %s
            """, (quantidade, produto_id))
            detalhes_itens.append(
                f"{produto['nome']}: +{_formatar_numero(quantidade, 2)} {unidade}"
            )

        detalhes = (
            f"Entrada rápida confirmada por {nome} ({login})"
            f" — tarefa #{tarefa_id} / {tarefa['talhao_nome']}: "
            + '; '.join(detalhes_itens)
            + ". Pendente de vínculo com nota fiscal."
        )
        cursor.execute("""
            INSERT INTO aplicacao_tarefa_log (tarefa_id, acao, detalhes, usuario)
            VALUES (%s, %s, %s, %s)
        """, (tarefa_id, 'entrada_rapida', detalhes, login or _texto(usuario_sessao) or None))
        return detalhes_itens

    try:
        with transacao() as cursor:
            return operacao(cursor)
    except Exception as e:
        logger.error(f"fila_aplicacao.registrar_entrada_rapida: {e}")
        raise
