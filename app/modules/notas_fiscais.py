"""
Módulo para gestão de Notas Fiscais de entrada de produtos
Permite upload de PDF e vinculação com movimentações
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao
from app.modules.estoque import normalizar_nome, registrar_embalagens

# =====================================================
# FUNÇÕES PARA NOTAS FISCAIS
# =====================================================

def listar_notas(data_inicio=None, data_fim=None, fornecedor=None):
    """
    Lista todas as notas fiscais com opção de filtros
    """
    query = """
    SELECT n.id, n.numero_nota, n.serie, n.data_emissao, n.data_recebimento,
           n.fornecedor, n.cnpj_fornecedor, n.valor_total, n.arquivo_pdf,
           n.observacoes, n.data_cadastro,
           COUNT(m.id) as total_produtos
    FROM notas_fiscais n
    LEFT JOIN movimentacoes_estoque m ON m.nota_fiscal_id = n.id AND m.tipo = 'entrada'
    WHERE n.ativo = TRUE
    """
    params = []

    if data_inicio and data_fim:
        query += " AND n.data_recebimento BETWEEN %s AND %s"
        params.extend([data_inicio, data_fim])

    if fornecedor:
        query += " AND n.fornecedor ILIKE %s"
        params.append(f"%{fornecedor}%")

    query += " GROUP BY n.id ORDER BY n.data_recebimento DESC, n.id DESC"

    try:
        resultado = executar_query(query, params if params else None, fetch_all=True, dict_cursor=True)
        notas = []
        for r in resultado:
            notas.append({
                'id': r['id'],
                'numero_nota': r['numero_nota'],
                'serie': r['serie'],
                'data_emissao': r['data_emissao'],
                'data_recebimento': r['data_recebimento'],
                'fornecedor': r['fornecedor'],
                'cnpj_fornecedor': r['cnpj_fornecedor'],
                'valor_total': float(r['valor_total']) if r['valor_total'] else None,
                'arquivo_pdf': r['arquivo_pdf'],
                'observacoes': r['observacoes'],
                'data_cadastro': r['data_cadastro'],
                'total_produtos': r['total_produtos']
            })
        return notas
    except Exception as e:
        print(f"Erro ao listar notas fiscais: {e}")
        return []

def valor_itens_nota(nota_id):
    """Soma dos itens da nota, usada apenas como conferência."""
    try:
        r = executar_query("""
            SELECT COALESCE(SUM(quantidade * COALESCE(preco_unitario_base, valor_unitario, 0)), 0) AS total
            FROM movimentacoes_estoque
            WHERE nota_fiscal_id = %s AND tipo = 'entrada' AND ativo = TRUE
        """, (nota_id,), fetch_one=True, dict_cursor=True)
        return round(float(r['total'] or 0), 2) if r else 0
    except Exception as e:
        print(f"Erro ao calcular valor dos itens da nota: {e}")
        return 0


def buscar_nota_por_id(id):
    """Busca uma nota fiscal específica pelo ID"""
    query = """
    SELECT n.id, n.numero_nota, n.serie, n.data_emissao, n.data_recebimento,
           n.fornecedor, n.cnpj_fornecedor, n.fornecedor_id, n.valor_total, n.arquivo_pdf,
           n.observacoes, n.data_cadastro
    FROM notas_fiscais n
    WHERE n.id = %s AND n.ativo = TRUE
    """
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            valor_nota = float(r['valor_total']) if r['valor_total'] else 0
            itens = valor_itens_nota(id)
            return {
                'id': r['id'],
                'numero_nota': r['numero_nota'],
                'serie': r['serie'],
                'data_emissao': r['data_emissao'],
                'data_recebimento': r['data_recebimento'],
                'fornecedor': r['fornecedor'],
                'cnpj_fornecedor': r['cnpj_fornecedor'],
                'fornecedor_id': r['fornecedor_id'],
                'valor_total': valor_nota or None,
                'valor_itens': itens,
                'diferenca_valor': round(valor_nota - itens, 2),
                'arquivo_pdf': r['arquivo_pdf'],
                'observacoes': r['observacoes'],
                'data_cadastro': r['data_cadastro']
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar nota fiscal: {e}")
        return None

def inserir_nota_fiscal(dados, arquivo_pdf=None):
    """
    Insere uma nova nota fiscal
    Retorna o ID da nota criada
    """
    query = """
    INSERT INTO notas_fiscais
        (numero_nota, serie, data_emissao, data_recebimento, fornecedor,
         cnpj_fornecedor, fornecedor_id, valor_total, arquivo_pdf, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['numero_nota'], dados.get('serie'), dados['data_emissao'],
             dados['data_recebimento'], dados['fornecedor'], dados.get('cnpj_fornecedor'),
             dados.get('fornecedor_id'), dados.get('valor_total'), arquivo_pdf,
             dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir nota fiscal: {e}")
        return None

def vincular_movimentacao_nota(movimentacao_id, nota_id):
    """Vincula uma movimentação a uma nota fiscal"""
    try:
        executar_query(
            "UPDATE movimentacoes_estoque SET nota_fiscal_id = %s WHERE id = %s",
            (nota_id, movimentacao_id)
        )
        return True
    except Exception as e:
        print(f"Erro ao vincular movimentação: {e}")
        return False

def listar_entradas_rapidas_pendentes():
    """Entradas feitas no campo que ainda não foram vinculadas a uma nota."""
    query = """
    SELECT m.id, m.quantidade, m.unidade, m.data_movimento, m.confirmado_por,
           p.nome AS produto_nome, t.id AS tarefa_id, tal.nome AS talhao_nome
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    LEFT JOIN aplicacao_tarefas t ON t.id = m.tarefa_id
    LEFT JOIN talhoes tal ON tal.id = t.talhao_id
    WHERE m.tipo = 'entrada' AND m.origem = 'entrada_rapida'
      AND m.nota_fiscal_id IS NULL AND m.ativo = TRUE
    ORDER BY m.data_movimento DESC, m.id DESC
    """
    try:
        registros = executar_query(query, fetch_all=True, dict_cursor=True)
        return [{
            'id': r['id'],
            'produto_nome': r['produto_nome'],
            'quantidade': float(r['quantidade'] or 0),
            'unidade': r['unidade'] or '',
            'data_movimento': r['data_movimento'],
            'confirmado_por': r['confirmado_por'] or '—',
            'tarefa_id': r['tarefa_id'],
            'talhao_nome': r['talhao_nome'] or '—',
        } for r in registros or []]
    except Exception as e:
        print(f"Erro ao listar entradas rápidas: {e}")
        return []


def vincular_entradas_rapidas(nota_id, ids, usuario):
    """
    Faz a entrada rápida constar como item da nota, sem mexer no saldo:
    o produto já entrou no estoque quando foi confirmada no campo.
    """
    if not ids:
        raise ValueError('Selecione pelo menos uma entrada rápida.')

    def operacao(cursor):
        vinculadas = []
        for bruto in ids:
            try:
                mov_id = int(bruto)
            except (TypeError, ValueError):
                raise ValueError('Entrada rápida inválida.')
            cursor.execute("""
                SELECT m.id, m.quantidade, m.unidade, m.nota_fiscal_id,
                       p.nome AS produto_nome
                FROM movimentacoes_estoque m
                JOIN produtos_estoque p ON p.id = m.produto_id
                WHERE m.id = %s AND m.ativo = TRUE AND m.tipo = 'entrada'
                  AND m.origem = 'entrada_rapida' FOR UPDATE OF m
            """, (mov_id,))
            movimento = cursor.fetchone()
            if not movimento:
                raise ValueError(f'Entrada rápida #{mov_id} não encontrada.')
            if movimento['nota_fiscal_id'] is not None:
                raise ValueError(f'Entrada rápida #{mov_id} já está vinculada a outra nota.')
            cursor.execute("""
                UPDATE movimentacoes_estoque
                SET nota_fiscal_id = %s,
                    observacoes = COALESCE(observacoes, '') || %s
                WHERE id = %s
            """, (nota_id,
                  f" | Vinculada à nota #{nota_id} por {usuario or 'sistema'}",
                  mov_id))
            vinculadas.append(
                f"{movimento['produto_nome']}: {float(movimento['quantidade']):.2f} "
                f"{movimento['unidade'] or ''}".strip()
            )
        return vinculadas

    try:
        return executar_transacao(operacao)
    except Exception as e:
        print(f"Erro ao vincular entradas rápidas: {e}")
        raise


def listar_movimentacoes_por_nota(nota_id):
    """Lista todas as movimentações (produtos) de uma nota fiscal"""
    query = """
    SELECT m.id, p.nome as produto_nome, m.quantidade, m.unidade,
           m.valor_unitario, m.preco_unitario_base, m.embalagens_quantidade,
           m.observacoes
    FROM movimentacoes_estoque m
    JOIN produtos_estoque p ON p.id = m.produto_id
    WHERE m.nota_fiscal_id = %s AND m.tipo = 'entrada' AND m.ativo = TRUE
    ORDER BY m.id
    """
    try:
        resultado = executar_query(query, (nota_id,), fetch_all=True, dict_cursor=True)
        movs = []
        for r in resultado:
            movs.append({
                'id': r['id'],
                'produto_nome': r['produto_nome'],
                'quantidade': float(r['quantidade']) if r['quantidade'] else 0,
                'unidade': r['unidade'],
                'valor_unitario': float(r['valor_unitario']) if r['valor_unitario'] else None,
                'preco_base': float(r['preco_unitario_base']) if r['preco_unitario_base'] else None,
                'embalagens': r['embalagens_quantidade'],
                'observacoes': r['observacoes']
            })
        return movs
    except Exception as e:
        print(f"Erro ao listar movimentações da nota: {e}")
        return []

def excluir_nota_fiscal(id):
    """Inativa a nota. Entradas, saldo, preços e embalagens ficam no histórico."""
    def operacao(cursor):
        cursor.execute("UPDATE notas_fiscais SET ativo = FALSE WHERE id = %s", (id,))
        cursor.execute("""
            UPDATE movimentacoes_estoque
            SET observacoes = COALESCE(observacoes, '') || %s
            WHERE nota_fiscal_id = %s AND ativo = TRUE
        """, (f' | Nota #{id} excluída; entrada mantida', id))
    try:
        executar_transacao(operacao)
        return True, "Nota fiscal excluída. O estoque e o histórico de compras foram mantidos."
    except Exception as e:
        print(f"Erro ao excluir nota fiscal: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def get_resumo_notas():
    """Retorna resumo das notas fiscais."""
    try:
        total_notas = executar_query("SELECT COUNT(*) AS total FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True, dict_cursor=True)
        total_notas = total_notas['total'] if total_notas else 0
    except Exception:
        total_notas = 0
    try:
        valor_total = executar_query("SELECT COALESCE(SUM(valor_total), 0) AS total FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True, dict_cursor=True)
        valor_total = float(valor_total['total']) if valor_total and valor_total['total'] else 0
    except Exception:
        valor_total = 0
    try:
        notas_mes = executar_query("""
            SELECT COUNT(*) AS total FROM notas_fiscais
            WHERE ativo = TRUE AND EXTRACT(MONTH FROM data_recebimento) = EXTRACT(MONTH FROM CURRENT_DATE)
        """, fetch_one=True, dict_cursor=True)
        notas_mes = notas_mes['total'] if notas_mes else 0
    except Exception:
        notas_mes = 0
    try:
        total_itens = executar_query("""
            SELECT COUNT(*) AS total FROM movimentacoes_estoque
            WHERE tipo = 'entrada' AND nota_fiscal_id IS NOT NULL
        """, fetch_one=True, dict_cursor=True)
        total_itens = total_itens['total'] if total_itens else 0
    except Exception:
        total_itens = 0
    try:
        total_fornecedores = executar_query("SELECT COUNT(DISTINCT fornecedor) AS total FROM notas_fiscais WHERE ativo = TRUE", fetch_one=True, dict_cursor=True)
        total_fornecedores = total_fornecedores['total'] if total_fornecedores else 0
    except Exception:
        total_fornecedores = 0
    return {
        'total_notas': total_notas,
        'valor_total': valor_total,
        'notas_mes': notas_mes,
        'total_itens': total_itens,
        'total_fornecedores': total_fornecedores
    }

def normalizar_nome_produto(nome):
    return normalizar_nome(nome)


def buscar_produto_por_nome(nome):
    """Reaproveita produto com o mesmo nome normalizado (caixa, acentos e espaços)."""
    if not nome:
        return None
    produtos = executar_query(
        "SELECT id, nome, unidade FROM produtos_estoque WHERE ativo = TRUE",
        fetch_all=True, dict_cursor=True) or []
    alvo = normalizar_nome(nome)
    for p in produtos:
        if normalizar_nome(p['nome']) == alvo:
            return p
    return None


def listar_produtos_para_selecao():
    return executar_query("""
        SELECT id, nome, unidade, quantidade_atual
        FROM produtos_estoque WHERE ativo = TRUE ORDER BY nome
    """, fetch_all=True, dict_cursor=True) or []


def buscar_ou_criar_produto(nome, unidade='L', categoria='Outros'):
    """Busca um produto pelo nome normalizado. Se não existir, cria."""
    if not nome or not nome.strip():
        return None
    encontrado = buscar_produto_por_nome(nome)
    if encontrado:
        return encontrado['id']
    try:
        resultado = executar_query(
            """INSERT INTO produtos_estoque
               (nome, unidade, categoria, estoque_minimo, quantidade_atual, ativo)
               VALUES (%s, %s, %s, 0, 0, TRUE) RETURNING id""",
            (nome.strip(), unidade, categoria), fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao criar produto automatico: {e}")
        return None

def adicionar_item_nota(nota_id, dados):
    """Adiciona item à NF. Escolhe produto existente ou cria um novo, sem duplicar nome."""
    produto_id = dados.get('produto_id')
    nome_produto = (dados.get('nome_produto') or '').strip()
    if not produto_id and not nome_produto:
        return None, "Selecione um produto cadastrado ou informe o nome de um novo produto."
    try:
        quantidade = float(dados.get('quantidade') or 0)
        valor_unitario = float(dados.get('valor_unitario') or 0) if dados.get('valor_unitario') else 0
    except (ValueError, TypeError):
        return None, "Quantidade e valor devem ser números válidos."
    unidade = dados.get('unidade') or 'L'
    categoria = dados.get('categoria') or 'Outros'
    embalagem = {
        'descricao': dados.get('embalagem_descricao'),
        'capacidade': dados.get('embalagem_capacidade'),
        'unidade': dados.get('embalagem_unidade') or unidade,
        'quantidade': dados.get('embalagem_quantidade'),
        'preco': dados.get('embalagem_preco'),
        'nota_fiscal_id': nota_id,
    }
    usar_embalagem = bool(embalagem['descricao'] and embalagem['capacidade']
                          and embalagem['quantidade'])
    if usar_embalagem and quantidade <= 0:
        quantidade = 1  # volume real é calculado pela embalagem
    if quantidade <= 0:
        return None, "A quantidade deve ser maior que zero."

    def _operacao(cursor):
        if produto_id:
            cursor.execute("SELECT id, nome, unidade FROM produtos_estoque WHERE id = %s AND ativo = TRUE FOR UPDATE", (int(produto_id),))
            produto = cursor.fetchone()
            if not produto:
                raise ValueError('Produto selecionado não encontrado.')
            produto_id_final = produto['id']
            nome_final = produto['nome']
            unidade_base = produto['unidade'] or unidade
        else:
            cursor.execute("SELECT id, nome, unidade FROM produtos_estoque WHERE ativo = TRUE")
            existentes = cursor.fetchall()
            alvo = normalizar_nome(nome_produto)
            encontrado = next((p for p in existentes if normalizar_nome(p['nome']) == alvo), None)
            if encontrado and not dados.get('confirmar_nome') == 'criar-novo':
                produto_id_final = encontrado['id']
                nome_final = encontrado['nome']
                unidade_base = encontrado['unidade'] or unidade
            else:
                cursor.execute("""
                    INSERT INTO produtos_estoque
                        (nome, unidade, categoria, estoque_minimo, quantidade_atual, ativo)
                    VALUES (%s, %s, %s, 0, 0, TRUE) RETURNING id
                """, (nome_produto, unidade, categoria))
                produto_id_final = cursor.fetchone()['id']
                nome_final = nome_produto
                unidade_base = unidade

        dados_emb = None
        if usar_embalagem:
            dados_emb = registrar_embalagens(cursor, produto_id_final, embalagem)
            quantidade_final = dados_emb['volume_base']
            unidade_final = unidade_base
            # preço da embalagem ÷ capacidade de UMA embalagem (2 galões de 20 L a R$ 120 = R$ 6/L)
            preco_base = float(dados_emb.get('preco_base') or 0)
            preco_mov = preco_base
            obs_extra = (f"{dados_emb['quantidade']}x {dados_emb['descricao']} "
                         f"de {dados_emb['capacidade']} {dados_emb['unidade']}")
        else:
            from app.modules.estoque import fator_para_base
            fator = fator_para_base(unidade, unidade_base)
            quantidade_final = quantidade * fator
            unidade_final = unidade_base
            preco_base = valor_unitario / fator if fator and valor_unitario else valor_unitario
            preco_mov = valor_unitario
            obs_extra = ''

        obs = f"Entrada via NF — {nome_final}"
        if obs_extra:
            obs += f" ({obs_extra})"
        if dados.get('observacoes'):
            obs += f" — {dados['observacoes']}"

        cursor.execute("""
            INSERT INTO movimentacoes_estoque
                (produto_id, tipo, quantidade, unidade, data_movimento, valor_unitario,
                 preco_unitario_base, embalagem_id, embalagens_quantidade, observacoes, nota_fiscal_id)
            VALUES (%s, 'entrada', %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (produto_id_final, quantidade_final, unidade_final, preco_mov, preco_base,
              dados_emb['id'] if dados_emb else None,
              dados_emb['quantidade'] if dados_emb else None, obs, nota_id))
        mov_id = cursor.fetchone()['id']

        cursor.execute(
            "UPDATE produtos_estoque SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
            (quantidade_final, produto_id_final))
        # O valor_total da nota é a conferência informada no cadastro e não é alterado aqui.
        return mov_id, quantidade_final, unidade_final

    try:
        mov_id, quantidade_final, unidade_final = executar_transacao(_operacao)
        return mov_id, (f"Item adicionado: {quantidade_final:.2f} {unidade_final} "
                        f"entraram no estoque e o preço foi registrado no histórico.")
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Erro ao adicionar item: {e}"

def remover_item_nota(movimentacao_id, nota_id=None):
    """Remove um item da nota fiscal e reverte a entrada no estoque.
    Trava a entrada ativa da nota; um segundo envio não estorna de novo."""
    from app.modules.estoque import estornar_embalagens_da_entrada

    def _operacao(cursor):
        cursor.execute(
            """SELECT m.id, m.produto_id, m.quantidade, m.nota_fiscal_id, m.embalagem_id, m.embalagens_quantidade
               FROM movimentacoes_estoque m
               WHERE m.id = %s AND m.tipo = 'entrada' AND m.ativo = TRUE
                 AND (%s::int IS NULL OR m.nota_fiscal_id = %s::int)
               FOR UPDATE""",
            (movimentacao_id, nota_id, nota_id)
        )
        r = cursor.fetchone()
        if not r:
            raise ValueError("Item não encontrado nesta nota ou já removido.")

        produto_id = r['produto_id']
        quantidade = float(r['quantidade']) if r['quantidade'] else 0

        cursor.execute("SELECT quantidade_atual FROM produtos_estoque WHERE id = %s FOR UPDATE", (produto_id,))
        produto = cursor.fetchone()
        if not produto or float(produto['quantidade_atual'] or 0) + 0.0005 < quantidade:
            raise ValueError(
                f"Não é possível remover: o saldo atual é menor que a entrada de "
                f"{quantidade:.3f}. Ajuste o estoque antes de estornar.".replace('.', ',', 1)
            )
        cursor.execute(
            "UPDATE produtos_estoque SET quantidade_atual = GREATEST(quantidade_atual - %s, 0) WHERE id = %s",
            (quantidade, produto_id)
        )

        # Só as embalagens desta compra saem do controle; as de outras notas continuam
        estornar_embalagens_da_entrada(cursor, r)

        # O valor_total da nota é a conferência informada no cadastro e não é alterado aqui.
        cursor.execute("UPDATE movimentacoes_estoque SET ativo = FALSE WHERE id = %s", (movimentacao_id,))
        return True

    try:
        executar_transacao(_operacao)
        return True, "Item removido e entrada estornada no estoque!"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        print(f"Erro ao remover item: {e}")
        return False, f"Erro: {e}"