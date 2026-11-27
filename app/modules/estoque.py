"""
Módulo de Controle de Estoque de Insumos
Versão completa com categorias e relatórios
"""

import math
import sys
import os
import pandas as pd
import re
import unicodedata
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from app.modules.relatorios import moldura_kaldi, COR_PRIMARIA, COR_LINHA
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_query_dict, executar_transacao, transacao

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

EPS = 0.0005               # metade da menor quantidade registrável (3 casas)
TIPOS_MOVIMENTO = ('entrada', 'saida')


def _arred(valor):
    return round(float(valor or 0), 3)


def _numero_br(valor, casas=2):
    texto = f"{float(valor or 0):,.{casas}f}"
    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


def normalizar_tipo(tipo):
    """'Saída', 'saída' e 'saida' viram 'saida'; 'Entrada' vira 'entrada'."""
    t = normalizar_nome(tipo)
    return t if t in TIPOS_MOVIMENTO else (t or '')


def get_ultimo_valor_produto(produto_id):
    """Retorna o último valor unitário registrado para o produto"""
    query = """
    SELECT valor_unitario FROM movimentacoes_estoque
    WHERE produto_id = %s AND valor_unitario IS NOT NULL AND ativo = TRUE
    ORDER BY data_movimento DESC, id DESC
    LIMIT 1
    """
    try:
        resultado = executar_query(query, (produto_id,), fetch_one=True, dict_cursor=True)
        return float(resultado['valor_unitario']) if resultado and resultado['valor_unitario'] else None
    except Exception as e:
        print(f"Erro ao buscar último valor: {e}")
        return None

def normalizar_nome(nome):
    """Remove acentos, caixa e espaços repetidos para comparar produtos iguais."""
    if not nome:
        return ''
    texto = unicodedata.normalize('NFKD', str(nome))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', texto).strip().lower()


def historico_precos(produto_id):
    """Compras do produto com preço, para acompanhar alta e baixa."""
    query = """
    SELECT m.id, m.data_movimento, m.quantidade, m.unidade, m.valor_unitario,
           m.preco_unitario_base, m.embalagens_quantidade,
           COALESCE(n.fornecedor, '—') AS fornecedor,
           COALESCE(n.numero_nota, '—') AS numero_nota,
           e.descricao AS embalagem_descricao
    FROM movimentacoes_estoque m
    LEFT JOIN notas_fiscais n ON n.id = m.nota_fiscal_id
    LEFT JOIN produto_embalagens e ON e.id = m.embalagem_id
    WHERE m.produto_id = %s AND m.tipo = 'entrada' AND m.ativo = TRUE
      AND m.valor_unitario IS NOT NULL
    ORDER BY m.data_movimento DESC, m.id DESC
    """
    registros = executar_query(query, (produto_id,), fetch_all=True, dict_cursor=True) or []
    historico = []
    precos = []
    for r in registros:
        preco = float(r['preco_unitario_base'] or r['valor_unitario'] or 0)
        if preco > 0:
            precos.append(preco)
        historico.append({
            'id': r['id'],
            'data': r['data_movimento'],
            'quantidade': float(r['quantidade'] or 0),
            'unidade': r['unidade'] or '',
            'valor_unitario': float(r['valor_unitario'] or 0),
            'preco_base': preco,
            'fornecedor': r['fornecedor'],
            'numero_nota': r['numero_nota'],
            'embalagem': r['embalagem_descricao'] or '—',
            'embalagens': r['embalagens_quantidade'],
        })
    return {
        'itens': historico,
        'ultimo': precos[0] if precos else None,
        'menor': min(precos) if precos else None,
        'maior': max(precos) if precos else None,
        'medio': sum(precos) / len(precos) if precos else None,
    }


def listar_produtos_parecidos(nome, excluir_id=None):
    """Produtos já cadastrados com nome idêntico ou parecido."""
    alvo = normalizar_nome(nome)
    if not alvo:
        return []
    produtos = executar_query(
        "SELECT id, nome, unidade, quantidade_atual FROM produtos_estoque WHERE ativo = TRUE",
        fetch_all=True, dict_cursor=True) or []
    exatos, parecidos = [], []
    for p in produtos:
        if excluir_id and p['id'] == excluir_id:
            continue
        atual = normalizar_nome(p['nome'])
        item = {
            'id': p['id'], 'nome': p['nome'], 'unidade': p['unidade'] or '',
            'quantidade_atual': float(p['quantidade_atual'] or 0),
        }
        if atual == alvo:
            exatos.append(item)
        elif alvo in atual or atual in alvo:
            parecidos.append(item)
    return exatos + parecidos


def listar_duplicados():
    """Grupos de produtos ativos com o mesmo nome normalizado."""
    produtos = executar_query(
        "SELECT id, nome, unidade, quantidade_atual FROM produtos_estoque WHERE ativo = TRUE ORDER BY id",
        fetch_all=True, dict_cursor=True) or []
    grupos = {}
    for p in produtos:
        chave = normalizar_nome(p['nome'])
        grupos.setdefault(chave, []).append({
            'id': p['id'], 'nome': p['nome'], 'unidade': p['unidade'] or '',
            'quantidade_atual': float(p['quantidade_atual'] or 0),
        })
    return [grupos[k] for k in sorted(grupos) if len(grupos[k]) > 1]


def _mesma_unidade(a, b):
    a = (a or '').strip().lower()
    b = (b or '').strip().lower()
    if a == b:
        return True
    try:
        return fator_para_base(a, b) == 1
    except ValueError:
        return False


def mesclar_produtos(principal_id, ids_secundarios):
    """Soma saldo e move movimentações para o produto principal, em uma transação."""
    if not ids_secundarios:
        raise ValueError('Selecione ao menos um produto duplicado.')
    if principal_id in ids_secundarios:
        raise ValueError('O produto principal não pode também ser secundário.')

    def operacao(cursor):
        cursor.execute("SELECT nome, unidade, quantidade_atual FROM produtos_estoque WHERE id = %s AND ativo = TRUE FOR UPDATE", (principal_id,))
        principal = cursor.fetchone()
        if not principal:
            raise ValueError('Produto principal não encontrado.')
        soma = float(principal['quantidade_atual'] or 0)
        nomes = []
        for secundario in ids_secundarios:
            cursor.execute("SELECT nome, unidade, quantidade_atual FROM produtos_estoque WHERE id = %s AND ativo = TRUE FOR UPDATE", (secundario,))
            r = cursor.fetchone()
            if not r:
                raise ValueError(f'Produto #{secundario} não encontrado.')
            if normalizar_nome(principal['nome']) != normalizar_nome(r['nome']):
                raise ValueError(f'Os produtos precisam ter o mesmo nome para mesclar.')
            if not _mesma_unidade(principal['unidade'], r['unidade']):
                raise ValueError(
                    f"Unidades diferentes: {r['nome']} está em {r['unidade'] or '—'} e o principal em "
                    f"{principal['unidade'] or '—'}. Ajuste a unidade antes de mesclar.")
            soma += float(r['quantidade_atual'] or 0)
            nomes.append(r['nome'])
            cursor.execute("UPDATE movimentacoes_estoque SET produto_id = %s WHERE produto_id = %s", (principal_id, secundario))
            cursor.execute("UPDATE produto_embalagens SET produto_id = %s WHERE produto_id = %s", (principal_id, secundario))
            # Receitas e tarefas da fila continuam apontando para um produto ativo
            cursor.execute("UPDATE receita_itens SET produto_id = %s WHERE produto_id = %s", (principal_id, secundario))
            cursor.execute("UPDATE aplicacao_tarefa_itens SET produto_id = %s WHERE produto_id = %s", (principal_id, secundario))
            cursor.execute("UPDATE produtos_estoque SET ativo = FALSE, quantidade_atual = 0 WHERE id = %s", (secundario,))
        cursor.execute("UPDATE produtos_estoque SET quantidade_atual = %s WHERE id = %s", (_arred(soma), principal_id))
        return soma, nomes

    return executar_transacao(operacao)


# =====================================================
# FUNÇÕES DE PRODUTOS
# =====================================================

def listar_produtos(ativos=True):
    """Retorna lista de produtos com categoria e último valor"""
    query = """
    SELECT id, nome, unidade, estoque_minimo, quantidade_atual, observacoes, ativo, categoria
    FROM produtos_estoque
    WHERE ativo = %s
    ORDER BY nome
    """
    try:
        resultado = executar_query(query, (ativos,), fetch_all=True, dict_cursor=True)
        produtos = []
        for r in resultado:
            estoque_minimo = r['estoque_minimo'] if r['estoque_minimo'] is not None else 0
            quantidade_atual = float(r['quantidade_atual']) if r['quantidade_atual'] is not None else 0
            ultimo_valor = get_ultimo_valor_produto(r['id'])

            produtos.append({
                'id': r['id'],
                'nome': r['nome'],
                'unidade': r['unidade'],
                'estoque_minimo': estoque_minimo,
                'quantidade_atual': quantidade_atual,
                'observacoes': r['observacoes'],
                'ativo': r['ativo'],
                'categoria': r['categoria'],
                'ultimo_valor': ultimo_valor,
                'valor_total': quantidade_atual * (ultimo_valor or 0),
                'estoque_baixo': quantidade_atual <= estoque_minimo if estoque_minimo > 0 else False
            })
        return produtos
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return []

def buscar_produto_por_id(id):
    """Busca um produto pelo ID"""
    query = """
    SELECT id, nome, unidade, estoque_minimo, quantidade_atual, observacoes, ativo, categoria
    FROM produtos_estoque
    WHERE id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            return {
                'id': r['id'],
                'nome': r['nome'],
                'unidade': r['unidade'],
                'estoque_minimo': r['estoque_minimo'],
                'quantidade_atual': r['quantidade_atual'],
                'observacoes': r['observacoes'],
                'ativo': r['ativo'],
                'categoria': r['categoria'],
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar produto: {e}")
        return None

def inserir_produto(dados):
    """Insere um novo produto"""
    query = """
    INSERT INTO produtos_estoque (nome, unidade, estoque_minimo, quantidade_atual, observacoes, categoria)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['nome'], dados['unidade'], dados.get('estoque_minimo'),
             dados.get('quantidade_atual', 0), dados.get('observacoes'),
             dados.get('categoria')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir produto: {e}")
        return None

def atualizar_produto(id, dados):
    """Atualiza um produto"""
    query = """
    UPDATE produtos_estoque
    SET nome=%s, unidade=%s, estoque_minimo=%s, quantidade_atual=%s, observacoes=%s, categoria=%s
    WHERE id=%s
    """
    try:
        executar_query(query,
            (dados['nome'], dados['unidade'], dados.get('estoque_minimo'),
             dados.get('quantidade_atual', 0), dados.get('observacoes'),
             dados.get('categoria'), id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar produto: {e}")
        return False

def excluir_produto(id):
    """Exclusão lógica. Histórico de movimentações e embalagens é preservado."""
    try:
        executar_query(
            "UPDATE produtos_estoque SET ativo = FALSE, quantidade_atual = 0 WHERE id = %s",
            (id,))
        return True, "Produto excluído. O histórico de movimentações foi mantido."
    except Exception as e:
        print(f"Erro ao excluir produto: {e}")
        return False, f"Erro ao excluir: {str(e)}"


# =====================================================
# EMBALAGENS
# =====================================================

def fator_para_base(unidade, unidade_base):
    """Converte L/ml e kg/g para a unidade de estoque do produto."""
    origem = (unidade or '').strip().lower().replace('mililitros', 'ml')
    destino = (unidade_base or '').strip().lower()
    fatores = {'l': 1, 'ml': 0.001, 'kg': 1, 'g': 0.001, 'un': 1}
    if origem not in fatores or destino not in fatores:
        raise ValueError(f'Unidades incompatíveis: {unidade} e {unidade_base}.')
    if origem == destino:
        return 1
    if {origem, destino} == {'l', 'ml'} or {origem, destino} == {'kg', 'g'}:
        return fatores[origem] / fatores[destino]
    raise ValueError(f'Unidades incompatíveis: {unidade} e {unidade_base}.')


def listar_embalagens(produto_id):
    query = """
    SELECT id, descricao, capacidade, unidade, preco, quantidade_total,
           quantidade_fechada, volume_aberta,
           (SELECT unidade FROM produtos_estoque WHERE id = %s) AS unidade_base
    FROM produto_embalagens
    WHERE produto_id = %s AND ativo = TRUE
    ORDER BY descricao, capacidade
    """
    return executar_query(query, (produto_id, produto_id), fetch_all=True, dict_cursor=True) or []


def registrar_embalagens(cursor, produto_id, dados):
    """Cria ou reaproveita a embalagem e devolve os dados para a movimentação."""
    descricao = (dados.get('descricao') or '').strip()
    capacidade = float(dados.get('capacidade') or 0)
    unidade = (dados.get('unidade') or 'L').strip()
    quantidade = int(dados.get('quantidade') or 0)
    preco = float(dados.get('preco') or 0) if dados.get('preco') else 0
    if not descricao or capacidade <= 0 or quantidade <= 0:
        raise ValueError('Preencha descrição, capacidade e quantidade da embalagem.')
    cursor.execute("SELECT unidade FROM produtos_estoque WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()
    fator = fator_para_base(unidade, produto['unidade'])
    cursor.execute("""
        SELECT id, quantidade_total, quantidade_fechada, volume_aberta
        FROM produto_embalagens
        WHERE produto_id = %s AND LOWER(descricao) = LOWER(%s)
          AND capacidade = %s AND unidade = %s AND ativo = TRUE
        FOR UPDATE
    """, (produto_id, descricao, capacidade, unidade))
    existing = cursor.fetchone()
    if existing:
        embalagem_id = existing['id']
        total = existing['quantidade_total'] + quantidade
        fechadas = existing['quantidade_fechada'] + quantidade
        volume = float(existing['volume_aberta'] or 0)
        cursor.execute("SELECT nota_fiscal_id, ativo FROM produto_embalagens WHERE id = %s", (embalagem_id,))
        emb_atual = cursor.fetchone()
        if emb_atual['ativo'] and emb_atual['nota_fiscal_id'] is None:
            cursor.execute("UPDATE produto_embalagens SET nota_fiscal_id = %s WHERE id = %s",
                           (dados.get('nota_fiscal_id'), embalagem_id))
        cursor.execute("""
            UPDATE produto_embalagens
            SET quantidade_total = %s, quantidade_fechada = %s,
                preco = COALESCE(%s, preco)
            WHERE id = %s
        """, (total, fechadas, preco or None, embalagem_id))
    else:
        cursor.execute("""
            INSERT INTO produto_embalagens
                (produto_id, descricao, capacidade, unidade, preco, nota_fiscal_id,
                 quantidade_total, quantidade_fechada, volume_aberta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0) RETURNING id
        """, (produto_id, descricao, capacidade, unidade, preco or None,
              dados.get('nota_fiscal_id'), quantidade, quantidade))
        embalagem_id = cursor.fetchone()['id']
        total, fechadas, volume = quantidade, quantidade, 0
    return {
        'id': embalagem_id,
        'descricao': descricao,
        'capacidade': capacidade,
        'unidade': unidade,
        'quantidade': quantidade,
        'volume_base': capacidade * fator * quantidade,
        'preco': preco,
        'preco_base': preco / (capacidade * fator) if capacidade * fator > 0 else 0,
        'total_fechadas': fechadas,
        'total_volume_aberta': volume,
    }


def baixar_embalagens(cursor, produto_id, quantidade_base, embalagens, movimento_id=None):
    """Retira o volume das embalagens (abertas primeiro) e registra o que saiu de cada uma.

    Grava em movimento_embalagens o volume realmente retirado e quantas embalagens
    fechadas foram abertas. Devolve o volume que não tinha embalagem controlada.
    """
    restante = float(quantidade_base)
    for emb in embalagens:
        if restante <= EPS:
            break
        capacidade_base = float(emb['capacidade']) * fator_para_base(emb['unidade'] or 'L', emb['unidade_base'])
        if capacidade_base <= 0:
            continue
        aberta = float(emb['volume_aberta'] or 0)
        fechadas = int(emb['quantidade_fechada'] or 0)
        retirado, abertas = 0.0, 0
        if aberta > EPS:
            parte = min(restante, aberta)
            aberta -= parte
            restante -= parte
            retirado += parte
        while restante > EPS and fechadas > 0:
            fechadas -= 1
            abertas += 1
            aberta = capacidade_base
            parte = min(restante, aberta)
            aberta -= parte
            restante -= parte
            retirado += parte
        if retirado <= EPS:
            continue
        aberta = 0 if aberta <= EPS else aberta
        emb['quantidade_fechada'] = fechadas
        emb['volume_aberta'] = aberta
        cursor.execute("""
            UPDATE produto_embalagens SET quantidade_fechada = %s, volume_aberta = %s
            WHERE id = %s
        """, (fechadas, _arred(aberta), emb['id']))
        cursor.execute("""
            INSERT INTO movimento_embalagens
                (movimento_id, embalagem_id, tipo, quantidade, litros, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (movimento_id, emb['id'], 'abertura' if abertas else 'uso', abertas, _arred(retirado),
              f'Retirada de {_arred(retirado)} da embalagem {emb["descricao"]}'))
    return _arred(max(restante, 0))


def _embalagens_para_baixa(cursor, produto_id):
    """Embalagens ativas do produto, travadas para a baixa (abertas primeiro, depois as mais antigas)."""
    cursor.execute("""
        SELECT e.id, e.descricao, e.capacidade, e.unidade, e.quantidade_total,
               e.quantidade_fechada, e.volume_aberta, p.unidade AS unidade_base
        FROM produto_embalagens e
        JOIN produtos_estoque p ON p.id = e.produto_id
        WHERE e.produto_id = %s AND e.ativo = TRUE
        ORDER BY (COALESCE(e.volume_aberta, 0) > 0) DESC, e.id
        FOR UPDATE OF e
    """, (produto_id,))
    return cursor.fetchall()


def _restaurar_embalagens_da_saida(cursor, movimento_id):
    """Devolve às embalagens o volume que uma saída tinha retirado (estorno ou edição)."""
    cursor.execute("""
        SELECT me.id, me.litros, e.id AS embalagem_id, e.capacidade, e.unidade,
               e.quantidade_total, e.quantidade_fechada, e.volume_aberta, e.ativo,
               p.unidade AS unidade_base
        FROM movimento_embalagens me
        JOIN produto_embalagens e ON e.id = me.embalagem_id
        JOIN produtos_estoque p ON p.id = e.produto_id
        WHERE me.movimento_id = %s AND COALESCE(me.ativo, TRUE) = TRUE
          AND me.tipo IN ('abertura', 'uso')
        FOR UPDATE OF me, e
    """, (movimento_id,))
    for r in cursor.fetchall():
        if r['ativo']:
            capacidade_base = float(r['capacidade']) * fator_para_base(r['unidade'] or 'L', r['unidade_base'])
            aberta = float(r['volume_aberta'] or 0) + float(r['litros'] or 0)
            fechadas = int(r['quantidade_fechada'] or 0)
            while capacidade_base > 0 and aberta >= capacidade_base - EPS and fechadas < int(r['quantidade_total'] or 0):
                aberta -= capacidade_base
                fechadas += 1
            aberta = 0 if aberta <= EPS else min(aberta, capacidade_base)
            cursor.execute("UPDATE produto_embalagens SET quantidade_fechada = %s, volume_aberta = %s WHERE id = %s",
                           (fechadas, _arred(aberta), r['embalagem_id']))
        cursor.execute("UPDATE movimento_embalagens SET ativo = FALSE WHERE id = %s", (r['id'],))


def estornar_embalagens_da_entrada(cursor, movimentacao):
    """Tira do controle só as embalagens desta compra, preservando as de outras compras."""
    embalagem_id = movimentacao.get('embalagem_id')
    if not embalagem_id:
        return
    cursor.execute("""
        SELECT e.id, e.capacidade, e.unidade, e.quantidade_total, e.quantidade_fechada,
               e.volume_aberta, e.ativo, p.unidade AS unidade_base
        FROM produto_embalagens e JOIN produtos_estoque p ON p.id = e.produto_id
        WHERE e.id = %s FOR UPDATE OF e
    """, (embalagem_id,))
    emb = cursor.fetchone()
    if not emb or not emb['ativo']:
        return
    quantidade = movimentacao.get('embalagens_quantidade')
    if not quantidade:
        capacidade_base = float(emb['capacidade']) * fator_para_base(emb['unidade'] or 'L', emb['unidade_base'])
        quantidade = round(float(movimentacao['quantidade'] or 0) / capacidade_base) if capacidade_base else 0
    quantidade = int(quantidade or 0)
    if quantidade <= 0:
        return
    if int(emb['quantidade_fechada'] or 0) < quantidade:
        raise ValueError('As embalagens desta compra já foram abertas. Registre uma saída de ajuste '
                         'em vez de estornar a entrada.')
    total = int(emb['quantidade_total'] or 0) - quantidade
    fechadas = int(emb['quantidade_fechada'] or 0) - quantidade
    ainda_ativa = total > 0 or float(emb['volume_aberta'] or 0) > EPS
    cursor.execute("""
        UPDATE produto_embalagens
        SET quantidade_total = %s, quantidade_fechada = %s, ativo = %s
        WHERE id = %s
    """, (max(total, 0), max(fechadas, 0), ainda_ativa, embalagem_id))


def _travar_produto(cursor, produto_id, exigir_ativo=True):
    cursor.execute("SELECT id, nome, unidade, quantidade_atual, ativo FROM produtos_estoque WHERE id = %s FOR UPDATE",
                   (produto_id,))
    produto = cursor.fetchone()
    if not produto or (exigir_ativo and not produto['ativo']):
        raise ValueError('Produto não encontrado ou inativo.')
    return produto


def _somar_saldo(cursor, produto, delta, motivo):
    """Aplica o delta ao saldo já travado; nunca deixa o estoque negativo."""
    novo = float(produto['quantidade_atual'] or 0) + float(delta)
    if novo < -EPS:
        raise ValueError(f'{motivo} Saldo de {produto["nome"]}: '
                         f'{_numero_br(produto["quantidade_atual"])} {produto["unidade"] or ""}.'.strip())
    novo = 0 if abs(novo) <= EPS else novo
    cursor.execute("UPDATE produtos_estoque SET quantidade_atual = %s WHERE id = %s", (_arred(novo), produto['id']))
    produto['quantidade_atual'] = novo


def _reverter_efeito(cursor, mov, produtos):
    """Desfaz no saldo (e nas embalagens) o efeito de uma movimentação ativa e travada."""
    if not mov['produto_id']:
        return
    produto = produtos[mov['produto_id']]
    quantidade = float(mov['quantidade'] or 0)
    if normalizar_tipo(mov['tipo']) == 'saida':
        _restaurar_embalagens_da_saida(cursor, mov['id'])
        _somar_saldo(cursor, produto, quantidade, '')
    else:
        estornar_embalagens_da_entrada(cursor, mov)
        _somar_saldo(cursor, produto, -quantidade,
                     'Não é possível desfazer esta entrada: parte dela já foi consumida.')


def _aplicar_efeito(cursor, produto, tipo, total, movimento_id):
    """Aplica uma entrada/saída ao saldo; saídas também baixam as embalagens."""
    if tipo == 'saida':
        _somar_saldo(cursor, produto, -total, 'Saldo insuficiente para esta saída.')
        embalagens = _embalagens_para_baixa(cursor, produto['id'])
        if embalagens:
            sem_embalagem = baixar_embalagens(cursor, produto['id'], total, embalagens, movimento_id)
            if sem_embalagem > EPS:
                cursor.execute("""
                    UPDATE movimentacoes_estoque
                    SET observacoes = COALESCE(observacoes, '') || %s
                    WHERE id = %s
                """, (f' | Atenção: {_numero_br(sem_embalagem, 3)} {produto["unidade"] or ""} '
                      f'sem embalagem controlada', movimento_id))
    else:
        _somar_saldo(cursor, produto, total, '')


def _validar_dados_movimento(dados):
    tipo = normalizar_tipo(dados.get('tipo'))
    if tipo not in TIPOS_MOVIMENTO:
        raise ValueError('Tipo de movimentação inválido. Use entrada ou saída.')
    try:
        quantidade = float(str(dados.get('quantidade') or '').replace(',', '.'))
    except (TypeError, ValueError):
        raise ValueError('Informe uma quantidade válida.')
    if not math.isfinite(quantidade) or quantidade <= 0:
        raise ValueError('A quantidade deve ser maior que zero.')
    try:
        produto_id = int(dados.get('produto_id'))
    except (TypeError, ValueError):
        raise ValueError('Selecione o produto.')
    valor = dados.get('valor_unitario')
    try:
        valor = float(str(valor).replace(',', '.')) if valor not in (None, '') else None
    except ValueError:
        raise ValueError('Valor unitário inválido.')
    if valor is not None and (not math.isfinite(valor) or valor < 0):
        raise ValueError('Valor unitário inválido.')
    return tipo, quantidade, produto_id, valor


def _converter_para_base(quantidade, unidade, produto):
    fator = fator_para_base(unidade, produto['unidade']) if unidade and produto['unidade'] else 1
    total = _arred(quantidade * fator)
    if total <= 0:
        raise ValueError(f'Quantidade muito pequena: o estoque registra até 0,001 {produto["unidade"] or ""}.'.strip())
    return total


# =====================================================
# FUNÇÕES DE MOVIMENTAÇÕES
# =====================================================

def registrar_movimentacao(dados):
    """Registra entrada/saída, abre embalagens quando preciso e nunca deixa saldo negativo."""
    tipo, quantidade, produto_id, valor = _validar_dados_movimento(dados)
    try:
        with transacao() as cur:
            produto = _travar_produto(cur, produto_id)
            total = _converter_para_base(quantidade, dados.get('unidade'), produto)
            cur.execute("""
            INSERT INTO movimentacoes_estoque
                (produto_id, tipo, quantidade, unidade, data_movimento, valor_unitario, observacoes)
            VALUES (%s, %s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s) RETURNING id
            """, (produto_id, tipo, total, produto['unidade'],
                  dados.get('data_movimento') or None, valor, dados.get('observacoes')))
            mov_id = cur.fetchone()['id']
            _aplicar_efeito(cur, produto, tipo, total, mov_id)
        return mov_id
    except Exception as e:
        print(f"Erro ao registrar movimentação: {e}")
        raise


def listar_movimentacoes(produto_id=None, data_inicio=None, data_fim=None, limite=100):
    """Movimentações ativas. Com período, o filtro vai ao banco e não há limite de linhas."""
    condicoes, params = ['m.ativo = TRUE'], []
    if produto_id:
        condicoes.append('m.produto_id = %s')
        params.append(produto_id)
    if data_inicio:
        condicoes.append('m.data_movimento >= %s')
        params.append(data_inicio)
    if data_fim:
        condicoes.append('m.data_movimento <= %s')
        params.append(data_fim)
    query = f"""
        SELECT m.id,
               COALESCE(p.nome, '🚫 Produto removido') as produto_nome,
               m.tipo, m.quantidade,
               m.unidade, m.data_movimento, m.valor_unitario, m.observacoes,
               p.ativo, m.nota_fiscal_id
        FROM movimentacoes_estoque m
        LEFT JOIN produtos_estoque p ON p.id = m.produto_id
        WHERE {' AND '.join(condicoes)}
        ORDER BY m.data_movimento DESC, m.id DESC
    """
    if not produto_id and not data_inicio and not data_fim and limite:
        query += " LIMIT %s"
        params.append(limite)

    try:
        resultado = executar_query(query, tuple(params) if params else None, fetch_all=True, dict_cursor=True)
        movs = []
        for r in resultado or []:
            movs.append({
                'id': r['id'],
                'produto_nome': r['produto_nome'],
                'tipo': normalizar_tipo(r['tipo']),
                'quantidade': float(r['quantidade']) if r['quantidade'] else 0,
                'unidade': r['unidade'],
                'data_movimento': r['data_movimento'],
                'valor_unitario': float(r['valor_unitario']) if r['valor_unitario'] else None,
                'observacoes': r['observacoes'],
                'produto_ativo': r['ativo'],
                'nota_fiscal_id': r['nota_fiscal_id']
            })
        return movs
    except Exception as e:
        print(f"Erro ao listar movimentações: {e}")
        return []

def buscar_movimentacao_por_id(id):
    """Busca uma movimentação ativa pelo ID, incluindo dados do produto (mesmo excluído)"""
    query = """
    SELECT m.id, m.produto_id,
           COALESCE(p.nome, '🚫 Produto removido') as produto_nome,
           m.tipo, m.quantidade,
           m.unidade, m.data_movimento, m.valor_unitario, m.observacoes,
           p.ativo, m.nota_fiscal_id, m.embalagem_id
    FROM movimentacoes_estoque m
    LEFT JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.id = %s AND m.ativo = TRUE
    """
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            return {
                'id': r['id'],
                'produto_id': r['produto_id'],
                'produto_nome': r['produto_nome'],
                'tipo': normalizar_tipo(r['tipo']),
                'quantidade': float(r['quantidade']) if r['quantidade'] else 0,
                'unidade': r['unidade'],
                'data_movimento': r['data_movimento'],
                'valor_unitario': float(r['valor_unitario']) if r['valor_unitario'] else None,
                'observacoes': r['observacoes'],
                'produto_ativo': r['ativo'],
                'nota_fiscal_id': r['nota_fiscal_id'],
                'vinculada_a_embalagem': bool(r['nota_fiscal_id'] or r['embalagem_id']),
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar movimentação: {e}")
        return None

def atualizar_movimentacao(id, dados_novos):
    """Edita a movimentação: lê e trava o registro ativo, desfaz o efeito antigo e aplica o novo
    com a mesma conversão de unidade e validação de saldo da criação. Retorna (ok, mensagem)."""
    try:
        tipo, quantidade, produto_novo_id, valor = _validar_dados_movimento(dados_novos)
        with transacao() as cur:
            cur.execute("""
                SELECT id, produto_id, tipo, quantidade, nota_fiscal_id, embalagem_id, embalagens_quantidade
                FROM movimentacoes_estoque WHERE id = %s AND ativo = TRUE FOR UPDATE
            """, (id,))
            mov = cur.fetchone()
            if not mov:
                raise ValueError('Movimentação não encontrada ou já excluída.')
            produtos = {}
            for pid in sorted({p for p in (mov['produto_id'], produto_novo_id) if p}):
                produtos[pid] = _travar_produto(cur, pid, exigir_ativo=(pid == produto_novo_id))
            produto_novo = produtos[produto_novo_id]
            total = _converter_para_base(quantidade, dados_novos.get('unidade'), produto_novo)

            muda_estoque = (produto_novo_id != mov['produto_id']
                            or tipo != normalizar_tipo(mov['tipo'])
                            or abs(total - float(mov['quantidade'] or 0)) > EPS)
            if muda_estoque:
                if mov['nota_fiscal_id'] or mov['embalagem_id']:
                    raise ValueError('Esta entrada veio de nota fiscal/embalagem. Para mudar produto, tipo ou '
                                     'quantidade, remova o item na nota e lance de novo.')
                _reverter_efeito(cur, mov, produtos)
                _aplicar_efeito(cur, produto_novo, tipo, total, id)

            cur.execute("""
                UPDATE movimentacoes_estoque
                SET produto_id=%s, tipo=%s, quantidade=%s, unidade=%s,
                    data_movimento=COALESCE(%s::date, data_movimento), valor_unitario=%s, observacoes=%s
                WHERE id=%s
            """, (produto_novo_id, tipo, total, produto_novo['unidade'],
                  dados_novos.get('data_movimento') or None, valor, dados_novos.get('observacoes'), id))
        return True, 'Movimentação atualizada e saldo reajustado.'
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        print(f"Erro ao atualizar movimentação: {e}")
        return False, 'Erro ao atualizar a movimentação.'

def excluir_movimentacao(id):
    """Exclui logicamente a movimentação e reverte saldo e embalagens na mesma transação."""
    try:
        with transacao() as cur:
            cur.execute("""
                SELECT id, produto_id, tipo, quantidade, nota_fiscal_id, embalagem_id, embalagens_quantidade
                FROM movimentacoes_estoque WHERE id = %s AND ativo = TRUE FOR UPDATE
            """, (id,))
            mov = cur.fetchone()
            if not mov:
                return False, "Movimentação não encontrada ou já excluída."
            produtos = {}
            if mov['produto_id']:
                produtos[mov['produto_id']] = _travar_produto(cur, mov['produto_id'], exigir_ativo=False)
            _reverter_efeito(cur, mov, produtos)
            cur.execute("UPDATE movimentacoes_estoque SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Movimentação excluída e saldo reajustado."
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        print(f"Erro ao excluir movimentação {id}: {e}")
        return False, "Erro ao excluir a movimentação."

# =====================================================
# FUNÇÕES DE RESUMO
# =====================================================

def get_resumo_estoque():
    """Retorna resumo estatístico do estoque"""
    try:
        # Total de produtos
        r = executar_query("SELECT COUNT(*) AS total FROM produtos_estoque WHERE ativo = TRUE", fetch_one=True, dict_cursor=True)
        total_produtos = r['total']

        # Valor total em estoque
        query_valor = """
        SELECT COALESCE(SUM(p.quantidade_atual * COALESCE((
            SELECT valor_unitario FROM movimentacoes_estoque
            WHERE produto_id = p.id AND valor_unitario IS NOT NULL AND ativo = TRUE
            ORDER BY data_movimento DESC, id DESC LIMIT 1
        ), 0)), 0) AS total
        FROM produtos_estoque p
        WHERE p.ativo = TRUE
        """
        r = executar_query(query_valor, fetch_one=True, dict_cursor=True)
        valor_total = r['total']

        # Produtos com estoque baixo
        r = executar_query("""
            SELECT COUNT(*) AS total FROM produtos_estoque
            WHERE ativo = TRUE AND quantidade_atual <= COALESCE(estoque_minimo, 0)
        """, fetch_one=True, dict_cursor=True)
        estoque_baixo = r['total']

        # Movimentações no mês
        r = executar_query("""
            SELECT COUNT(*) AS total FROM movimentacoes_estoque
            WHERE ativo = TRUE AND date_trunc('month', data_movimento) = date_trunc('month', CURRENT_DATE)
        """, fetch_one=True, dict_cursor=True)
        mov_mes = r['total']

        return {
            'total_produtos': total_produtos or 0,
            'valor_total': float(valor_total) if valor_total else 0,
            'estoque_baixo': estoque_baixo or 0,
            'movimentacoes_mes': mov_mes or 0
        }
    except Exception as e:
        print(f"Erro ao obter resumo: {e}")
        return {
            'total_produtos': 0,
            'valor_total': 0,
            'estoque_baixo': 0,
            'movimentacoes_mes': 0
        }

# =====================================================
# FUNÇÕES DE RELATÓRIOS (PDF/EXCEL)
# =====================================================

def gerar_excel_produtos(produtos):
    """Gera arquivo Excel com a lista de produtos"""
    data = []
    for p in produtos:
        data.append({
            'ID': p['id'],
            'Produto': p['nome'],
            'Categoria': p.get('categoria', ''),
            'Unidade': p['unidade'],
            'Quantidade': p['quantidade_atual'],
            'Estoque Mínimo': p['estoque_minimo'] if p['estoque_minimo'] else 0,
            'Status': 'Baixo' if p.get('estoque_baixo') else 'Normal',
            'Observações': p['observacoes'] or ''
        })

    df = pd.DataFrame(data)
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Produtos', index=False)
        worksheet = writer.sheets['Produtos']
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            col_idx = df.columns.get_loc(column)
            worksheet.column_dimensions[chr(65 + col_idx)].width = min(column_width, 30)

    output.seek(0)
    return output

def gerar_pdf_produtos(produtos):
    """Gera arquivo PDF com a lista de produtos"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2.4*cm, bottomMargin=1.8*cm)

    elements = []
    styles = getSampleStyleSheet()

    titulo = Paragraph(f"Relatório de Produtos - {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 0.5*cm))

    data = [['ID', 'Produto', 'Categoria', 'Unidade', 'Quantidade', 'Estoque Mínimo', 'Status']]

    for p in produtos:
        status = 'Baixo' if p.get('estoque_baixo') else 'Normal'
        data.append([
            str(p['id']),
            p['nome'],
            p.get('categoria', ''),
            p['unidade'],
            f"{p['quantidade_atual']:.2f}",
            f"{p['estoque_minimo']:.2f}" if p['estoque_minimo'] else '-',
            status
        ])

    table = Table(data, colWidths=[2*cm, 5*cm, 3*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.4, COR_LINHA)
    ])

    for i, p in enumerate(produtos, start=1):
        if p.get('estoque_baixo'):
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightcoral)

    table.setStyle(style)
    elements.append(table)

    elements.append(Spacer(1, 1*cm))
    total_produtos = len(produtos)
    total_baixo = sum(1 for p in produtos if p.get('estoque_baixo'))
    rodape = Paragraph(f"Total de produtos: {total_produtos} | Produtos com estoque baixo: {total_baixo}", styles['Normal'])
    elements.append(rodape)

    doc.build(elements, onFirstPage=moldura_kaldi, onLaterPages=moldura_kaldi)
    buffer.seek(0)
    return buffer

def gerar_excel_movimentacoes(movimentacoes, data_inicio, data_fim):
    """Gera Excel com movimentações em um período"""
    data = []
    for m in movimentacoes:
        data.append({
            'Data': m['data_movimento'],
            'Produto': m['produto_nome'],
            'Tipo': 'Entrada' if m['tipo'] == 'entrada' else 'Saída',
            'Quantidade': m['quantidade'],
            'Unidade': m['unidade'] or '',
            'Valor Unitário': m['valor_unitario'] if m['valor_unitario'] else 0,
            'Valor Total': (m['quantidade'] * m['valor_unitario']) if m['valor_unitario'] else 0,
            'Observações': m['observacoes'] or ''
        })

    df = pd.DataFrame(data)
    total_entradas = df[df['Tipo'] == 'Entrada']['Valor Total'].sum()
    total_saidas = df[df['Tipo'] == 'Saída']['Valor Total'].sum()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Movimentações', index=False)

        resumo = pd.DataFrame({
            'Período': [f"{data_inicio} a {data_fim}"],
            'Total Entradas (R$)': [f"{total_entradas:.2f}"],
            'Total Saídas (R$)': [f"{total_saidas:.2f}"],
            'Saldo (R$)': [f"{total_entradas - total_saidas:.2f}"]
        })
        resumo.to_excel(writer, sheet_name='Resumo', index=False)

    output.seek(0)
    return output

def gerar_pdf_movimentacoes(movimentacoes, data_inicio, data_fim):
    """Gera PDF com movimentações em um período"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.5*cm, leftMargin=1.5*cm,
                           topMargin=2.4*cm, bottomMargin=1.8*cm)

    elements = []
    styles = getSampleStyleSheet()

    titulo = Paragraph(f"Relatório de Movimentações - {data_inicio} a {data_fim}", styles['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 0.5*cm))

    data = [['Data', 'Produto', 'Tipo', 'Quantidade', 'Unidade', 'Valor Unit.', 'Valor Total']]

    total_entradas = 0
    total_saidas = 0

    for m in movimentacoes:
        tipo = 'Entrada' if m['tipo'] == 'entrada' else 'Saída'
        valor_unit = m['valor_unitario'] or 0
        valor_total = m['quantidade'] * valor_unit

        if m['tipo'] == 'entrada':
            total_entradas += valor_total
        else:
            total_saidas += valor_total

        data.append([
            m['data_movimento'],
            m['produto_nome'],
            tipo,
            f"{m['quantidade']:.2f}",
            m['unidade'] or '-',
            f"{valor_unit:.2f}" if valor_unit else '-',
            f"{valor_total:.2f}"
        ])

    data.append(['', '', '', '', '', 'TOTAL:', f"{total_entradas - total_saidas:.2f}"])

    table = Table(data, colWidths=[2.5*cm, 5*cm, 2.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2.5*cm])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ])

    for i, m in enumerate(movimentacoes, start=1):
        if m['tipo'] == 'entrada':
            style.add('BACKGROUND', (2, i), (2, i), colors.lightgreen)
        else:
            style.add('BACKGROUND', (2, i), (2, i), colors.lightcoral)

    table.setStyle(style)
    elements.append(table)

    doc.build(elements, onFirstPage=moldura_kaldi, onLaterPages=moldura_kaldi)
    buffer.seek(0)
    return buffer

def listar_categorias():
    """Lista categorias ativas."""
    query = "SELECT id, nome, descricao, cor FROM categorias_estoque WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        return [{'id': r['id'], 'nome': r['nome'], 'descricao': r['descricao'], 'cor': r['cor']} for r in resultado] if resultado else []
    except Exception:
        return []

def get_valor_por_categoria():
    """Retorna valor total por categoria para grafico."""
    query = """
    SELECT
        COALESCE(p.categoria, 'Sem categoria') as categoria,
        COUNT(*) as produtos,
        COALESCE(SUM(p.quantidade_atual * COALESCE((
            SELECT valor_unitario FROM movimentacoes_estoque
            WHERE produto_id = p.id AND valor_unitario IS NOT NULL AND ativo = TRUE
            ORDER BY data_movimento DESC, id DESC LIMIT 1
        ), 0)), 0) as valor
    FROM produtos_estoque p
    WHERE p.ativo = TRUE
    GROUP BY p.categoria
    ORDER BY valor DESC
    """
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        labels = []
        dados = []
        for r in resultado:
            labels.append(r['categoria'])
            dados.append(float(r['valor']) if r['valor'] else 0)
        return {'labels': labels, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}

def get_consumo_ultimos_6_meses():
    """Retorna consumo (saidas) dos ultimos 6 meses."""
    query = """
    SELECT TO_CHAR(data_movimento, 'YYYY-MM') as mes, SUM(quantidade) as total
    FROM movimentacoes_estoque
    WHERE tipo IN ('saida', 'saída') AND ativo = TRUE
      AND data_movimento >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY TO_CHAR(data_movimento, 'YYYY-MM')
    ORDER BY mes ASC
    """
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        meses = []
        dados = []
        for r in resultado:
            ano, mes = r['mes'].split('-')
            meses.append(f"{mes}/{ano}")
            dados.append(float(r['total']) if r['total'] else 0)
        return {'labels': meses, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}

def get_top_produtos_consumo(limite=10):
    """Retorna produtos mais consumidos (saida)."""
    query = """
    SELECT p.nome, SUM(m.quantidade) as total
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.tipo IN ('saida', 'saída') AND m.ativo = TRUE
    GROUP BY p.id, p.nome
    ORDER BY total DESC
    LIMIT %s
    """
    try:
        resultado = executar_query(query, (limite,), fetch_all=True, dict_cursor=True)
        labels = [r['nome'] for r in resultado]
        dados = [float(r['total']) if r['total'] else 0 for r in resultado]
        return {'labels': labels, 'dados': dados}
    except Exception:
        return {'labels': [], 'dados': []}