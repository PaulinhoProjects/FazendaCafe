"""
Módulo de Adubação baseado em Análises de Solo
Gerencia recomendações e aplicações de adubos
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from app.models import get_logger

logger = get_logger(__name__)

# Namespace fixo de advisory locks: compra e aplicação disputam a mesma chave.
_LOCK_NUTRI_COMPRA = 61027

# =====================================================
# FUNÇÕES PARA TIPOS DE ADUBAÇÃO
# =====================================================

def listar_tipos_adubacao():
    query = "SELECT id, nome, descricao FROM tipos_adubacao WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        return [{'id': r['id'], 'nome': r['nome'], 'descricao': r['descricao']} for r in resultado] if resultado else []
    except Exception as e:
        print(f"Erro ao listar tipos: {e}")
        return []

# =====================================================
# FUNÇÕES PARA RECOMENDAÇÕES
# =====================================================

def gerar_recomendacao_automatica(analise_id):
    """
    Gera recomendação automática baseada nos resultados da análise de solo
    Retorna dicionário com recomendações de nutrientes
    """
    try:
        # Buscar resultados da análise
        query_resultados = """
        SELECT p.nome, r.valor
        FROM resultados_analise r
        JOIN parametros_analise p ON p.id = r.parametro_id
        WHERE r.analise_id = %s
        """
        resultados = executar_query(query_resultados, (analise_id,), fetch_all=True, dict_cursor=True)

        if not resultados:
            return None, "Análise sem resultados"

        # Converter para dicionário
        valores = {}
        for r in resultados:
            valores[r['nome']] = float(r['valor']) if r['valor'] else 0
        
        # Regras básicas de recomendação (exemplo simplificado)
        recomendacoes = []
        
        # Fósforo (P)
        p_valor = valores.get('Fósforo (P)', 0)
        if p_valor < 10:
            recomendacoes.append({
                'nutriente': 'P2O5',
                'quantidade': 120,
                'unidade': 'kg/ha',
                'fonte': 'Superfosfato Simples',
                'observacoes': 'Teor baixo de fósforo'
            })
        elif p_valor < 20:
            recomendacoes.append({
                'nutriente': 'P2O5',
                'quantidade': 80,
                'unidade': 'kg/ha',
                'fonte': 'Superfosfato Simples',
                'observacoes': 'Teor médio de fósforo'
            })
        
        # Potássio (K)
        k_valor = valores.get('Potássio (K)', 0)
        if k_valor < 0.15:
            recomendacoes.append({
                'nutriente': 'K2O',
                'quantidade': 100,
                'unidade': 'kg/ha',
                'fonte': 'Cloreto de Potássio',
                'observacoes': 'Teor baixo de potássio'
            })
        elif k_valor < 0.3:
            recomendacoes.append({
                'nutriente': 'K2O',
                'quantidade': 60,
                'unidade': 'kg/ha',
                'fonte': 'Cloreto de Potássio',
                'observacoes': 'Teor médio de potássio'
            })
        
        # pH e necessidade de calcário
        ph_valor = valores.get('pH (CaCl2)', 0) or valores.get('pH (H2O)', 0)
        if ph_valor < 5.5:
            recomendacoes.append({
                'nutriente': 'Calcário',
                'quantidade': 2,
                'unidade': 't/ha',
                'fonte': 'Calcário Dolomítico',
                'observacoes': 'Acidez alta - necessidade de calagem'
            })
        elif ph_valor < 6.0:
            recomendacoes.append({
                'nutriente': 'Calcário',
                'quantidade': 1,
                'unidade': 't/ha',
                'fonte': 'Calcário Dolomítico',
                'observacoes': 'Acidez média - calagem de manutenção'
            })
        
        return recomendacoes, None
        
    except Exception as e:
        print(f"Erro ao gerar recomendação: {e}")
        return None, str(e)

def inserir_recomendacao(dados):
    """Insere uma nova recomendação de adubação"""
    query = """
    INSERT INTO recomendacoes_adubacao 
        (talhao_id, analise_id, data_recomendacao, data_validade, responsavel, observacoes, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados.get('analise_id'), dados['data_recomendacao'],
             dados.get('data_validade'), dados.get('responsavel'), dados.get('observacoes'),
             dados.get('status', 'Pendente')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir recomendação: {e}")
        return None

def inserir_item_recomendacao(dados):
    """Insere um item na recomendação"""
    query = """
    INSERT INTO itens_recomendacao 
        (recomendacao_id, nutriente, quantidade_recomendada, unidade, fonte_recomendada, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['recomendacao_id'], dados['nutriente'], dados['quantidade'],
             dados['unidade'], dados.get('fonte'), dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir item: {e}")
        return None

def listar_recomendacoes(talhao_id=None):
    """Lista recomendações de adubação"""
    if talhao_id:
        query = """
        SELECT r.id, r.talhao_id, t.nome as talhao_nome,
               r.analise_id, a.data_coleta as analise_data,
               r.data_recomendacao, r.data_validade, r.responsavel,
               r.observacoes, r.status
        FROM recomendacoes_adubacao r
        JOIN talhoes t ON t.id = r.talhao_id
        LEFT JOIN analises a ON a.id = r.analise_id
        WHERE r.talhao_id = %s
        ORDER BY r.data_recomendacao DESC
        """
        params = (talhao_id,)
    else:
        query = """
        SELECT r.id, r.talhao_id, t.nome as talhao_nome,
               r.analise_id, a.data_coleta as analise_data,
               r.data_recomendacao, r.data_validade, r.responsavel,
               r.observacoes, r.status
        FROM recomendacoes_adubacao r
        JOIN talhoes t ON t.id = r.talhao_id
        LEFT JOIN analises a ON a.id = r.analise_id
        ORDER BY r.data_recomendacao DESC
        LIMIT 100
        """
        params = None

    try:
        resultado = executar_query(query, params, fetch_all=True, dict_cursor=True)
        recomendacoes = []
        for r in resultado:
            recomendacoes.append({
                'id': r['id'],
                'talhao_id': r['talhao_id'],
                'talhao_nome': r['talhao_nome'],
                'analise_id': r['analise_id'],
                'analise_data': r['analise_data'],
                'data_recomendacao': r['data_recomendacao'],
                'data_validade': r['data_validade'],
                'responsavel': r['responsavel'],
                'observacoes': r['observacoes'],
                'status': r['status']
            })
        return recomendacoes
    except Exception as e:
        print(f"Erro ao listar recomendações: {e}")
        return []

def buscar_recomendacao_por_id(id):
    """Busca uma recomendação específica"""
    query = """
    SELECT r.id, r.talhao_id, t.nome as talhao_nome,
           r.analise_id, a.data_coleta as analise_data,
           r.data_recomendacao, r.data_validade, r.responsavel,
           r.observacoes, r.status
    FROM recomendacoes_adubacao r
    JOIN talhoes t ON t.id = r.talhao_id
    LEFT JOIN analises a ON a.id = r.analise_id
    WHERE r.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            return {
                'id': r['id'],
                'talhao_id': r['talhao_id'],
                'talhao_nome': r['talhao_nome'],
                'analise_id': r['analise_id'],
                'analise_data': r['analise_data'],
                'data_recomendacao': r['data_recomendacao'],
                'data_validade': r['data_validade'],
                'responsavel': r['responsavel'],
                'observacoes': r['observacoes'],
                'status': r['status']
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar recomendação: {e}")
        return None

def listar_itens_recomendacao(recomendacao_id):
    """Lista os itens de uma recomendação"""
    query = """
    SELECT id, nutriente, quantidade_recomendada, unidade, fonte_recomendada, observacoes
    FROM itens_recomendacao
    WHERE recomendacao_id = %s
    ORDER BY nutriente
    """
    try:
        resultado = executar_query(query, (recomendacao_id,), fetch_all=True, dict_cursor=True)
        itens = []
        for r in resultado:
            itens.append({
                'id': r['id'],
                'nutriente': r['nutriente'],
                'quantidade': float(r['quantidade_recomendada']) if r['quantidade_recomendada'] else 0,
                'unidade': r['unidade'],
                'fonte': r['fonte_recomendada'],
                'observacoes': r['observacoes']
            })
        return itens
    except Exception as e:
        print(f"Erro ao listar itens: {e}")
        return []

def atualizar_status_recomendacao(id, novo_status):
    """Atualiza o status de uma recomendação"""
    query = "UPDATE recomendacoes_adubacao SET status = %s WHERE id = %s"
    try:
        executar_query(query, (novo_status, id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar status: {e}")
        return False
    
def inserir_adubacao(dados):
    """Registra uma adubação realizada"""
    query = """
    INSERT INTO adubacoes 
        (talhao_id, recomendacao_id, tipo_adubacao_id, data_aplicacao, responsavel, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['recomendacao_id'], dados['tipo_adubacao_id'],
             dados['data_aplicacao'], dados.get('responsavel'), dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir adubação: {e}")
        return None

def inserir_produto_adubacao(dados):
    """Registra produto usado na adubação"""
    query = """
    INSERT INTO produtos_adubacao 
        (adubacao_id, produto_nome, quantidade, unidade, custo_unitario, fornecedor, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['adubacao_id'], dados['produto_nome'], dados['quantidade'],
             dados['unidade'], dados.get('custo_unitario'), dados.get('fornecedor'),
             dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir produto: {e}")
        return None

def inserir_nutriente_aplicado(dados):
    """Registra nutriente aplicado"""
    query = """
    INSERT INTO nutrientes_aplicados (adubacao_id, nutriente, quantidade_aplicada, unidade)
    VALUES (%s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['adubacao_id'], dados['nutriente'], dados['quantidade_aplicada'], dados['unidade']),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir nutriente: {e}")
        return None

def buscar_adubacao_por_id(id):
    """Busca uma adubação específica"""
    query = """
    SELECT a.id, a.talhao_id, t.nome as talhao_nome,
           a.recomendacao_id, r.data_recomendacao,
           a.tipo_adubacao_id, ta.nome as tipo_nome,
           a.data_aplicacao, a.responsavel, a.observacoes
    FROM adubacoes a
    JOIN talhoes t ON t.id = a.talhao_id
    LEFT JOIN recomendacoes_adubacao r ON r.id = a.recomendacao_id
    LEFT JOIN tipos_adubacao ta ON ta.id = a.tipo_adubacao_id
    WHERE a.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            return {
                'id': r['id'],
                'talhao_id': r['talhao_id'],
                'talhao_nome': r['talhao_nome'],
                'recomendacao_id': r['recomendacao_id'],
                'recomendacao_data': r['data_recomendacao'],
                'tipo_id': r['tipo_adubacao_id'],
                'tipo_nome': r['tipo_nome'],
                'data_aplicacao': r['data_aplicacao'],
                'responsavel': r['responsavel'],
                'observacoes': r['observacoes']
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar adubação: {e}")
        return None

def listar_produtos_adubacao(adubacao_id):
    """Lista produtos usados em uma adubação"""
    query = """
    SELECT id, produto_nome, quantidade, unidade, custo_unitario, fornecedor, observacoes
    FROM produtos_adubacao
    WHERE adubacao_id = %s
    """
    try:
        resultado = executar_query(query, (adubacao_id,), fetch_all=True, dict_cursor=True)
        produtos = []
        for r in resultado:
            produtos.append({
                'id': r['id'],
                'nome': r['produto_nome'],
                'quantidade': float(r['quantidade']) if r['quantidade'] else 0,
                'unidade': r['unidade'],
                'custo': float(r['custo_unitario']) if r['custo_unitario'] else None,
                'fornecedor': r['fornecedor'],
                'observacoes': r['observacoes']
            })
        return produtos
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
        return []

def listar_nutrientes_aplicados(adubacao_id):
    """Lista nutrientes aplicados"""
    query = """
    SELECT id, nutriente, quantidade_aplicada, unidade
    FROM nutrientes_aplicados
    WHERE adubacao_id = %s
    """
    try:
        resultado = executar_query(query, (adubacao_id,), fetch_all=True, dict_cursor=True)
        nutrientes = []
        for r in resultado:
            nutrientes.append({
                'id': r['id'],
                'nutriente': r['nutriente'],
                'quantidade': float(r['quantidade_aplicada']) if r['quantidade_aplicada'] else 0,
                'unidade': r['unidade']
            })
        return nutrientes
    except Exception as e:
        print(f"Erro ao listar nutrientes: {e}")
        return []
    
def listar_adubacoes(limite=100):
    """Lista todas as adubações realizadas"""
    query = """
    SELECT a.id, a.talhao_id, t.nome as talhao_nome,
           a.recomendacao_id, r.data_recomendacao,
           a.tipo_adubacao_id, ta.nome as tipo_nome,
           a.data_aplicacao, a.responsavel
    FROM adubacoes a
    JOIN talhoes t ON t.id = a.talhao_id
    LEFT JOIN recomendacoes_adubacao r ON r.id = a.recomendacao_id
    LEFT JOIN tipos_adubacao ta ON ta.id = a.tipo_adubacao_id
    ORDER BY a.data_aplicacao DESC
    LIMIT %s
    """
    try:
        resultado = executar_query(query, (limite,), fetch_all=True, dict_cursor=True)
        adubacoes = []
        for r in resultado:
            adubacoes.append({
                'id': r['id'],
                'talhao_id': r['talhao_id'],
                'talhao_nome': r['talhao_nome'],
                'recomendacao_id': r['recomendacao_id'],
                'recomendacao_data': r['data_recomendacao'],
                'tipo_id': r['tipo_adubacao_id'],
                'tipo_nome': r['tipo_nome'],
                'data_aplicacao': r['data_aplicacao'],
                'responsavel': r['responsavel']
            })
        return adubacoes
    except Exception as e:
        print(f"Erro ao listar adubações: {e}")
        return []

def excluir_recomendacao(id):
    """Exclui uma recomendação (itens serão excluídos automaticamente por CASCADE)"""
    try:
        # Verificar se há adubações vinculadas
        r = executar_query("SELECT COUNT(*) AS total FROM adubacoes WHERE recomendacao_id = %s", (id,), fetch_one=True, dict_cursor=True)
        count = r['total']
        if count > 0:
            print(f"Recomendação {id} já foi aplicada em {count} adubação(ões)")
            return False, "Esta recomendação já foi aplicada e não pode ser excluída"
        
        # Excluir a recomendação (CASCADE cuida dos itens)
        executar_query("UPDATE recomendacoes_adubacao SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Recomendação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir recomendação: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_adubacao(id):
    """Exclui uma adubação (produtos e nutrientes serão excluídos por CASCADE)"""
    try:
        # CASCADE cuida dos filhos
        executar_query("UPDATE adubacoes SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Adubação excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir adubação: {e}")
        return False, f"Erro ao excluir: {str(e)}"


# =====================================================
# NUTRIÇÃO E CORREÇÃO DO SOLO
# Compra da formulação -> saldo próprio -> aplicação por talhão.
# Nenhuma função desta seção consulta insumos, café ou maquinário.
# =====================================================

TECNOLOGIAS = [
    'Convencional', 'Liberação lenta (6 a 10 meses)', 'Orgânica',
    'Micronutrientes', 'Fertirrigação', 'Outra',
]
METODOS_APLICACAO = ['Tratorizada', 'Fertirrigação', 'Manual', 'Outro']
UNIDADES_COMPRA = [('kg', 'Quilograma (kg)'), ('saco', 'Saco (sc)')]

# Saldo de cada formulação comprada. Aplicações excluídas não descontam saldo.
_SQL_FORMULACOES = """
    SELECT i.*, c.fornecedor, c.numero_nota, c.data_nota,
           ta.nome AS categoria_nome,
           i.quantidade_kg - COALESCE(
               SUM(atl.quantidade_kg) FILTER (WHERE a.ativo = TRUE AND atl.ativo = TRUE), 0
           ) AS saldo_kg
    FROM nutri_compra_itens i
    JOIN nutri_compras c ON c.id = i.compra_id AND c.ativo = TRUE
    LEFT JOIN tipos_adubacao ta ON ta.id = i.categoria_id
    LEFT JOIN nutri_aplicacoes a ON a.compra_item_id = i.id
    LEFT JOIN nutri_aplicacao_talhoes atl
           ON atl.aplicacao_id = a.id AND atl.ativo = TRUE
    WHERE i.ativo = TRUE
    GROUP BY i.id, c.fornecedor, c.numero_nota, c.data_nota, ta.nome
"""


def _texto(valor):
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _decimal_2(valor):
    """Quantiza na precisão das colunas NUMERIC(14,2) do banco."""
    if valor is None or valor == '':
        return Decimal('0.00')
    return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _decimal(valor, padrao=0.0):
    if valor is None or valor == '':
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(' ', '')
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')
        else:
            texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return float(texto)
    except (TypeError, ValueError):
        return padrao


def _inteiro(valor):
    if valor in (None, ''):
        return None
    try:
        return int(_decimal(valor))
    except (TypeError, ValueError):
        return None


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = _texto(valor)
    if not texto:
        return None
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%Y %H:%M'):
        try:
            return datetime.strptime(texto[:19], formato).date()
        except ValueError:
            continue
    return None


def _numero_br(valor, casas=2):
    """1.234,56 — usado nas mensagens exibidas ao usuário."""
    texto = f"{float(valor or 0):,.{casas}f}"
    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


def _kg(quantidade, unidade, peso_saco):
    """Converte a compra para kg, base comum de saldo e aplicação."""
    qtd = _decimal(quantidade)
    if _texto(unidade) and _texto(unidade).lower() in ('saco', 'sacos', 'sc'):
        return qtd * (_decimal(peso_saco, 50) or 50)
    return qtd


def _normalizar_talhoes(talhoes):
    """Só considera linhas com talhão e quantidade válidos."""
    normalizados = []
    for item in talhoes or []:
        talhao_id = _inteiro(item.get('talhao_id'))
        quantidade = _decimal(item.get('quantidade_kg'))
        if not talhao_id or quantidade <= 0:
            continue
        normalizados.append({
            'talhao_id': talhao_id,
            'recomendacao_id': _inteiro(item.get('recomendacao_id')),
            'quantidade_kg': float(_decimal_2(quantidade)),
            'area_ha': _decimal(item.get('area_ha')) or None,
            'observacoes': _texto(item.get('observacoes')),
        })
    return normalizados


def _bloquear_compra(cur, compra_id):
    """Advisory lock de transação: serialize exclusão e aplicações da mesma nota."""
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_LOCK_NUTRI_COMPRA, int(compra_id)))


# ---------------------------- Compras --------------------------------------
def listar_compras(limite=None):
    sql = """
        SELECT c.*, COUNT(i.id) AS total_itens,
               COALESCE(SUM(i.valor_total), 0) AS valor_total
        FROM nutri_compras c
        LEFT JOIN nutri_compra_itens i ON i.compra_id = c.id AND i.ativo = TRUE
        WHERE c.ativo = TRUE
        GROUP BY c.id
        ORDER BY c.data_nota DESC, c.id DESC
    """
    params = []
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_compras: {e}")
        return []


def buscar_compra(id):
    try:
        return executar_query(
            "SELECT * FROM nutri_compras WHERE id = %s AND ativo = TRUE",
            (id,), fetch_one=True, dict_cursor=True,
        )
    except Exception as e:
        logger.error(f"adubacao.buscar_compra: {e}")
        return None


def listar_itens_compra(compra_id):
    sql = _SQL_FORMULACOES.replace('WHERE i.ativo = TRUE',
                                   'WHERE i.ativo = TRUE AND i.compra_id = %s')
    sql += " ORDER BY i.id"
    try:
        return executar_query(sql, (compra_id,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_itens_compra: {e}")
        return []


def inserir_compra(dados, itens):
    """Uma nota com uma ou mais formulações, gravada em uma única transação."""
    itens_validos = []
    for item in itens or []:
        produto = _texto(item.get('produto'))
        quantidade_kg = _kg(item.get('quantidade'), item.get('unidade'), item.get('peso_saco_kg'))
        if not produto:
            continue
        if quantidade_kg <= 0:
            raise ValueError(f"Quantidade inválida para {produto}.")
        itens_validos.append((produto, item, quantidade_kg))
    if not itens_validos:
        raise ValueError('Informe ao menos uma formulação comprada.')

    def operacao(cur):
        cur.execute("""
            INSERT INTO nutri_compras (fornecedor, numero_nota, data_nota, observacoes)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (
            _texto(dados.get('fornecedor')) or 'Fornecedor não informado',
            _texto(dados.get('numero_nota')),
            _data(dados.get('data_nota')) or date.today(),
            _texto(dados.get('observacoes')),
        ))
        compra_id = cur.fetchone()['id']
        for produto, item, quantidade_kg in itens_validos:
            valor_total = _decimal(item.get('valor_total')) or None
            quantidade = _decimal(item.get('quantidade'))
            if valor_total is None:
                valor_total = quantidade * _decimal(item.get('valor_unitario'))
            cur.execute("""
                INSERT INTO nutri_compra_itens (
                    compra_id, produto, formulacao, marca, tecnologia, categoria_id,
                    quantidade, unidade, peso_saco_kg, quantidade_kg,
                    valor_unitario, valor_total, lote, validade, observacoes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                compra_id, produto, _texto(item.get('formulacao')),
                _texto(item.get('marca')), _texto(item.get('tecnologia')),
                _inteiro(item.get('categoria_id')), quantidade,
                _texto(item.get('unidade')) or 'kg',
                _decimal(item.get('peso_saco_kg')) or None,
                quantidade_kg, _decimal(item.get('valor_unitario')) or None,
                valor_total, _texto(item.get('lote')), _data(item.get('validade')),
                _texto(item.get('observacoes')),
            ))
        return compra_id

    try:
        compra_id = executar_transacao(operacao)
        return compra_id, 'Compra registrada com sucesso. O saldo das formulações já está disponível.'
    except Exception as e:
        logger.error(f"adubacao.inserir_compra: {e}")
        return None, str(e)


def atualizar_compra(id, dados):
    sql = """
        UPDATE nutri_compras
        SET fornecedor = %s, numero_nota = %s, data_nota = %s, observacoes = %s
        WHERE id = %s AND ativo = TRUE
    """
    try:
        executar_query(sql, (
            _texto(dados.get('fornecedor')) or 'Fornecedor não informado',
            _texto(dados.get('numero_nota')),
            _data(dados.get('data_nota')) or date.today(),
            _texto(dados.get('observacoes')), id,
        ))
        return True, 'Dados da nota atualizados. As formulações compradas permanecem inalteradas.'
    except Exception as e:
        logger.error(f"adubacao.atualizar_compra: {e}")
        return False, str(e)


def excluir_compra(id):
    """Exclusão lógica; bloqueia notas com aplicações ativas."""
    def operacao(cur):
        _bloquear_compra(cur, id)
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM nutri_aplicacoes a
            JOIN nutri_compra_itens i ON i.id = a.compra_item_id
            WHERE i.compra_id = %s AND a.ativo = TRUE AND i.ativo = TRUE
        """, (id,))
        if cur.fetchone()['total']:
            raise ValueError('Esta nota possui aplicações ativas. Exclua as aplicações antes.')
        cur.execute("UPDATE nutri_compras SET ativo = FALSE WHERE id = %s", (id,))
        cur.execute("UPDATE nutri_compra_itens SET ativo = FALSE WHERE compra_id = %s", (id,))

    try:
        executar_transacao(operacao)
        return True, 'Nota excluída com sucesso.'
    except Exception as e:
        logger.error(f"adubacao.excluir_compra: {e}")
        return False, str(e)


# ------------------------- Formulações e saldo ------------------------------
def listar_formulacoes(disponiveis=False, limite=None):
    sql = "SELECT * FROM (" + _SQL_FORMULACOES + ") AS f WHERE TRUE"
    params = []
    if disponiveis:
        sql += " AND f.saldo_kg > 0.009"
    sql += " ORDER BY f.saldo_kg, f.id"
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_formulacoes: {e}")
        return []


def buscar_formulacao(id):
    sql = "SELECT * FROM (" + _SQL_FORMULACOES + ") AS f WHERE f.id = %s"
    try:
        return executar_query(sql, (id,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"adubacao.buscar_formulacao: {e}")
        return None


# ---------------------------- Aplicações -----------------------------------
_SQL_APLICACOES = """
    SELECT a.*, i.produto, i.formulacao, i.marca, i.tecnologia,
           c.fornecedor, c.numero_nota, ta.nome AS categoria_nome,
           COALESCE(SUM(atl.quantidade_kg), 0) AS total_kg,
           COUNT(atl.id) AS total_talhoes,
           COALESCE(SUM(atl.quantidade_kg) * i.valor_total / NULLIF(i.quantidade_kg, 0), 0) AS custo_total
    FROM nutri_aplicacoes a
    JOIN nutri_compra_itens i ON i.id = a.compra_item_id
    JOIN nutri_compras c ON c.id = i.compra_id
    LEFT JOIN tipos_adubacao ta ON ta.id = i.categoria_id
    LEFT JOIN nutri_aplicacao_talhoes atl
           ON atl.aplicacao_id = a.id AND atl.ativo = TRUE
    WHERE a.ativo = TRUE AND i.ativo = TRUE AND c.ativo = TRUE
    GROUP BY a.id, i.produto, i.formulacao, i.marca, i.tecnologia,
             c.fornecedor, c.numero_nota, ta.nome, i.valor_total, i.quantidade_kg
"""


def listar_aplicacoes(limite=None):
    sql = _SQL_APLICACOES + " ORDER BY a.data_aplicacao DESC, a.id DESC"
    params = []
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_aplicacoes: {e}")
        return []


def buscar_aplicacao(id):
    sql = "SELECT * FROM (" + _SQL_APLICACOES + ") AS ap WHERE ap.id = %s"
    try:
        return executar_query(sql, (id,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"adubacao.buscar_aplicacao: {e}")
        return None


def listar_talhoes_aplicacao(aplicacao_id):
    sql = """
        SELECT atl.*, t.nome AS talhao_nome, t.area_hectares AS talhao_area,
               r.data_recomendacao,
               atl.quantidade_kg * i.valor_total / NULLIF(i.quantidade_kg, 0) AS custo_rateado
        FROM nutri_aplicacao_talhoes atl
        JOIN talhoes t ON t.id = atl.talhao_id
        JOIN nutri_aplicacoes a ON a.id = atl.aplicacao_id
        JOIN nutri_compra_itens i ON i.id = a.compra_item_id
        LEFT JOIN recomendacoes_adubacao r ON r.id = atl.recomendacao_id
        WHERE atl.aplicacao_id = %s AND atl.ativo = TRUE AND a.ativo = TRUE
        ORDER BY t.nome
    """
    try:
        return executar_query(sql, (aplicacao_id,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_talhoes_aplicacao: {e}")
        return []


def listar_aplicacoes_formulacao(compra_item_id):
    sql = """
        SELECT a.*, COALESCE(SUM(atl.quantidade_kg), 0) AS total_kg
        FROM nutri_aplicacoes a
        LEFT JOIN nutri_aplicacao_talhoes atl
               ON atl.aplicacao_id = a.id AND atl.ativo = TRUE
        WHERE a.compra_item_id = %s AND a.ativo = TRUE
        GROUP BY a.id
        ORDER BY a.data_aplicacao DESC, a.id DESC
    """
    try:
        return executar_query(sql, (compra_item_id,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"adubacao.listar_aplicacoes_formulacao: {e}")
        return []


def _validar_saldo(cur, compra_item_id, quantidade_aplicada, aplicacao_id=None):
    """Trava a nota e a formulação antes de validar o saldo na precisão do banco."""
    cur.execute("""
        SELECT compra_id FROM nutri_compra_itens WHERE id = %s
    """, (compra_item_id,))
    linha = cur.fetchone()
    if not linha:
        raise ValueError('Formulação comprada não encontrada.')
    _bloquear_compra(cur, linha['compra_id'])

    cur.execute("""
        SELECT quantidade_kg FROM nutri_compra_itens
        WHERE id = %s AND ativo = TRUE FOR UPDATE
    """, (compra_item_id,))
    item = cur.fetchone()
    if not item:
        raise ValueError('Formulação comprada não encontrada.')
    sql = """
        SELECT COALESCE(SUM(atl.quantidade_kg), 0) AS usado
        FROM nutri_aplicacoes a
        JOIN nutri_aplicacao_talhoes atl ON atl.aplicacao_id = a.id AND atl.ativo = TRUE
        WHERE a.compra_item_id = %s AND a.ativo = TRUE
    """
    params = [compra_item_id]
    if aplicacao_id:
        sql += " AND a.id <> %s"
        params.append(aplicacao_id)
    cur.execute(sql, tuple(params))
    usado = _decimal_2(cur.fetchone()['usado'])
    disponivel = _decimal_2(item['quantidade_kg']) - usado
    if _decimal_2(quantidade_aplicada) > disponivel:
        raise ValueError(
            f'Quantidade acima do saldo disponível: {_numero_br(disponivel)} kg.'
        )
    return item


def inserir_aplicacao(dados, talhoes):
    """Aplicação de uma compra em vários talhões, com baixa de saldo atômica."""
    talhoes_validos = _normalizar_talhoes(talhoes)
    if not talhoes_validos:
        raise ValueError('Informe ao menos um talhão com quantidade aplicada.')
    total = sum(item['quantidade_kg'] for item in talhoes_validos)

    def operacao(cur):
        compra_item_id = _inteiro(dados.get('compra_item_id'))
        if not compra_item_id:
            raise ValueError('Selecione a formulação comprada.')
        _validar_saldo(cur, compra_item_id, total)
        cur.execute("""
            INSERT INTO nutri_aplicacoes
                (compra_item_id, data_aplicacao, metodo, responsavel, observacoes)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (
            compra_item_id,
            _data(dados.get('data_aplicacao')) or date.today(),
            _texto(dados.get('metodo')) or 'Tratorizada',
            _texto(dados.get('responsavel')),
            _texto(dados.get('observacoes')),
        ))
        aplicacao_id = cur.fetchone()['id']
        _inserir_talhoes(cur, aplicacao_id, talhoes_validos)
        return aplicacao_id

    try:
        aplicacao_id = executar_transacao(operacao)
        return aplicacao_id, 'Aplicação registrada. O saldo da formulação foi baixado.'
    except Exception as e:
        logger.error(f"adubacao.inserir_aplicacao: {e}")
        return None, str(e)


def _inserir_talhoes(cur, aplicacao_id, talhoes):
    for talhao in talhoes:
        cur.execute("""
            INSERT INTO nutri_aplicacao_talhoes
                (aplicacao_id, talhao_id, recomendacao_id, quantidade_kg, area_ha, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            aplicacao_id, talhao['talhao_id'], talhao['recomendacao_id'],
            talhao['quantidade_kg'], talhao['area_ha'], talhao['observacoes'],
        ))


def atualizar_aplicacao(id, dados, talhoes):
    """Reajusta doses/talhões da aplicação recalculando o saldo na mesma transação."""
    talhoes_validos = _normalizar_talhoes(talhoes)
    if not talhoes_validos:
        raise ValueError('Informe ao menos um talhão com quantidade aplicada.')
    total = sum(item['quantidade_kg'] for item in talhoes_validos)

    def operacao(cur):
        cur.execute("SELECT compra_item_id FROM nutri_aplicacoes WHERE id = %s AND ativo = TRUE", (id,))
        atual = cur.fetchone()
        if not atual:
            raise ValueError('Aplicação não encontrada.')
        compra_item_id = _inteiro(dados.get('compra_item_id')) or atual['compra_item_id']
        _validar_saldo(cur, compra_item_id, total, aplicacao_id=id)
        cur.execute("""
            UPDATE nutri_aplicacoes
            SET compra_item_id = %s, data_aplicacao = %s, metodo = %s,
                responsavel = %s, observacoes = %s
            WHERE id = %s
        """, (
            compra_item_id,
            _data(dados.get('data_aplicacao')) or date.today(),
            _texto(dados.get('metodo')) or 'Tratorizada',
            _texto(dados.get('responsavel')),
            _texto(dados.get('observacoes')), id,
        ))
        cur.execute("UPDATE nutri_aplicacao_talhoes SET ativo = FALSE WHERE aplicacao_id = %s", (id,))
        _inserir_talhoes(cur, id, talhoes_validos)

    try:
        executar_transacao(operacao)
        return True, 'Aplicação atualizada. O saldo foi recalculado.'
    except Exception as e:
        logger.error(f"adubacao.atualizar_aplicacao: {e}")
        return False, str(e)


def excluir_aplicacao(id):
    """Exclusão lógica: a quantidade volta para o saldo da formulação."""
    def operacao(cur):
        cur.execute("UPDATE nutri_aplicacoes SET ativo = FALSE WHERE id = %s", (id,))
        cur.execute("UPDATE nutri_aplicacao_talhoes SET ativo = FALSE WHERE aplicacao_id = %s", (id,))

    try:
        executar_transacao(operacao)
        return True, 'Aplicação excluída. A quantidade voltou para o saldo.'
    except Exception as e:
        logger.error(f"adubacao.excluir_aplicacao: {e}")
        return False, str(e)


# -------------------------- Resumo e catálogo -------------------------------
def resumo_nutricao():
    vazio = {'valor_compras': 0, 'compras_mes': 0, 'saldo_kg': 0,
             'aplicacoes_30d': 0, 'aplicado_30d_kg': 0, 'talhoes_atendidos': 0}
    try:
        compras = executar_query("""
            SELECT COUNT(DISTINCT c.id) AS total, COALESCE(SUM(i.valor_total), 0) AS valor
            FROM nutri_compras c
            JOIN nutri_compra_itens i ON i.compra_id = c.id AND i.ativo = TRUE
            WHERE c.ativo = TRUE AND c.data_nota >= date_trunc('month', CURRENT_DATE)
        """, fetch_one=True, dict_cursor=True)
        saldo = executar_query(
            "SELECT COALESCE(SUM(f.saldo_kg), 0) AS total FROM (" + _SQL_FORMULACOES + ") AS f",
            fetch_one=True, dict_cursor=True,
        )
        aplicacoes = executar_query("""
            SELECT COUNT(DISTINCT a.id) AS total, COALESCE(SUM(atl.quantidade_kg), 0) AS kg,
                   COUNT(DISTINCT atl.talhao_id) AS talhoes
            FROM nutri_aplicacoes a
            JOIN nutri_aplicacao_talhoes atl ON atl.aplicacao_id = a.id AND atl.ativo = TRUE
            WHERE a.ativo = TRUE AND a.data_aplicacao >= CURRENT_DATE - INTERVAL '30 days'
        """, fetch_one=True, dict_cursor=True)
        return {
            'valor_compras': float(compras['valor'] or 0),
            'compras_mes': int(compras['total'] or 0),
            'saldo_kg': float(saldo['total'] or 0),
            'aplicacoes_30d': int(aplicacoes['total'] or 0),
            'aplicado_30d_kg': float(aplicacoes['kg'] or 0),
            'talhoes_atendidos': int(aplicacoes['talhoes'] or 0),
        }
    except Exception as e:
        logger.error(f"adubacao.resumo_nutricao: {e}")
        return vazio


def listar_alertas():
    alertas = []
    try:
        baixos = executar_query("""
            SELECT f.id, f.produto, f.formulacao, f.saldo_kg
            FROM (""" + _SQL_FORMULACOES + """) AS f
            WHERE f.saldo_kg > 0 AND f.saldo_kg <= f.quantidade_kg * 0.10
            ORDER BY f.saldo_kg LIMIT 10
        """, fetch_all=True, dict_cursor=True) or []
        for item in baixos:
            alertas.append({
                'tipo': 'danger', 'titulo': 'Saldo baixo: ' + (item['produto'] or 'formulação'),
                'detalhe': f"Restam {_numero_br(item['saldo_kg'])} kg.",
                'url': 'adubacao.formulacoes',
            })
        # Só avisa validade de formulações que ainda têm saldo para usar
        vencidos = executar_query("""
            SELECT f.produto, f.validade, f.saldo_kg
            FROM (""" + _SQL_FORMULACOES + """) AS f
            WHERE f.saldo_kg > 0.009 AND f.validade IS NOT NULL
              AND f.validade <= CURRENT_DATE + INTERVAL '30 days'
            ORDER BY f.validade LIMIT 10
        """, fetch_all=True, dict_cursor=True) or []
        for item in vencidos:
            vencido = item['validade'] < date.today()
            alertas.append({
                'tipo': 'danger' if vencido else 'warning',
                'titulo': ('Vencido: ' if vencido else 'Validade próxima: ') + (item['produto'] or 'formulação'),
                'detalhe': ('Venceu em ' if vencido else 'Vence em ')
                + item['validade'].strftime('%d/%m/%Y')
                + f" · saldo {_numero_br(item['saldo_kg'])} kg.",
                'url': 'adubacao.formulacoes',
            })
    except Exception as e:
        logger.error(f"adubacao.listar_alertas: {e}")
    return alertas


def listar_catalogo():
    return {
        'tecnologias': TECNOLOGIAS,
        'metodos': METODOS_APLICACAO,
        'unidades': [{'valor': valor, 'rotulo': rotulo} for valor, rotulo in UNIDADES_COMPRA],
        'categorias': listar_tipos_adubacao(),
    }