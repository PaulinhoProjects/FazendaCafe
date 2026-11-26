"""
Módulo de Maquinário.

Escopo isolado do estoque de insumos/café:
- estoque próprio de peças, óleo, filtros e materiais de manutenção;
- cadastro de máquinas, horímetro e manutenções;
- abastecimentos de Diesel S10, boletos/lembretes e preços públicos da ANP;
- registro e soma de gastos com maquinário.

Nenhuma função deste arquivo consulta as tabelas do estoque de insumos.
"""
import io
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao
from app.models import get_logger

logger = get_logger(__name__)

ANP_URL = os.getenv(
    "MAQ_ANP_URL",
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/qus/ultimas-4-semanas-diesel-gnv.csv",
)
ANP_MUNICIPIO = os.getenv("MAQ_ANP_MUNICIPIO", "ALFENAS").upper()
ANP_UF = os.getenv("MAQ_ANP_UF", "MG").upper()
PRODUTO_DIESEL = "DIESEL S10"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT_ANP = 90

try:
    CACHE_ANP_MINUTOS = max(1, int(os.getenv("MAQ_ANP_CACHE_MINUTOS", "360")))
except (TypeError, ValueError):
    CACHE_ANP_MINUTOS = 360

_DADOS_ANP = {"valor": None, "timestamp": None}

CATEGORIAS_ESTOQUE = [
    "Peças", "Óleo e lubrificantes", "Filtros", "Ferramentas", "Implementos", "Outros",
]
TIPOS_MANUTENCAO = [
    "Revisão", "Reparo", "Troca de óleo", "Troca de filtro", "Lavagem", "Outros",
]
CATEGORIAS_GASTO = [
    "Manutenção", "Peças", "Combustível", "Serviços", "Ferramentas", "Outros",
]


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------
def _texto(valor):
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _decimal(valor, padrao=0.0):
    """Converte '1.234,56', '1234.56' ou número para float."""
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(" ", "")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except (TypeError, ValueError):
        return padrao


def _inteiro(valor, padrao=0):
    try:
        return int(_decimal(valor, padrao))
    except (TypeError, ValueError):
        return padrao


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = _texto(valor)
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto[:19], formato).date()
        except ValueError:
            continue
    return None


def _booleano(valor):
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().lower() in ("1", "true", "on", "sim", "s", "yes")


# ---------------------------------------------------------------------------
# Estoque isolado de maquinário
# ---------------------------------------------------------------------------
def listar_produtos(ativos=True):
    sql = """
        SELECT id, nome, categoria, unidade, quantidade_atual, estoque_minimo,
               local_armazenagem, observacoes, ativo, data_cadastro
        FROM maq_produtos
    """
    if ativos:
        sql += " WHERE ativo = TRUE"
    sql += " ORDER BY nome"
    try:
        return executar_query(sql, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_produtos: {e}")
        return []


def buscar_produto(id):
    if not id:
        return None
    try:
        return executar_query(
            "SELECT * FROM maq_produtos WHERE id = %s", (id,),
            fetch_one=True, dict_cursor=True,
        )
    except Exception as e:
        logger.error(f"maquinario.buscar_produto: {e}")
        return None


def inserir_produto(dados):
    nome = _texto(dados.get("nome"))
    if not nome:
        return None, "Informe o nome do produto."
    sql = """
        INSERT INTO maq_produtos
            (nome, categoria, unidade, quantidade_atual, estoque_minimo,
             local_armazenagem, observacoes)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (
        nome, _texto(dados.get("categoria")) or "Outros",
        _texto(dados.get("unidade")) or "un",
        _decimal(dados.get("quantidade_atual")),
        _decimal(dados.get("estoque_minimo")),
        _texto(dados.get("local_armazenagem")), _texto(dados.get("observacoes")),
    )
    try:
        produto_id = executar_transacao(lambda cur: _inserir(cur, sql, params))
        return produto_id, "Produto cadastrado no estoque de maquinário!"
    except Exception as e:
        logger.error(f"maquinario.inserir_produto: {e}")
        return None, f"Erro ao cadastrar produto: {e}"


def _inserir(cursor, sql, params):
    cursor.execute(sql, params)
    return cursor.fetchone()["id"]


def atualizar_produto(id, dados):
    nome = _texto(dados.get("nome"))
    if not nome:
        return False, "Informe o nome do produto."
    sql = """
        UPDATE maq_produtos
        SET nome = %s, categoria = %s, unidade = %s, estoque_minimo = %s,
            local_armazenagem = %s, observacoes = %s
        WHERE id = %s AND ativo = TRUE
    """
    params = (
        nome, _texto(dados.get("categoria")) or "Outros",
        _texto(dados.get("unidade")) or "un",
        _decimal(dados.get("estoque_minimo")),
        _texto(dados.get("local_armazenagem")), _texto(dados.get("observacoes")), id,
    )

    def operacao(cursor):
        cursor.execute(sql, params)
        if cursor.rowcount == 0:
            raise ValueError("Produto não encontrado.")

    try:
        executar_transacao(operacao)
        return True, "Produto atualizado!"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"maquinario.atualizar_produto: {e}")
        return False, f"Erro ao atualizar produto: {e}"


def excluir_produto(id):
    """Exclusão lógica; o saldo vai a zero para não indicar estoque ativo."""
    try:
        executar_query(
            "UPDATE maq_produtos SET ativo = FALSE, quantidade_atual = 0 WHERE id = %s",
            (id,),
        )
        return True, "Produto removido. O histórico de movimentações foi mantido."
    except Exception as e:
        logger.error(f"maquinario.excluir_produto: {e}")
        return False, f"Erro ao remover produto: {e}"


def listar_movimentacoes(produto_id=None, limite=200):
    sql = """
        SELECT mv.*, p.nome AS produto_nome
        FROM maq_movimentacoes mv
        JOIN maq_produtos p ON p.id = mv.produto_id
        WHERE mv.ativo = TRUE
    """
    params = []
    if produto_id:
        sql += " AND mv.produto_id = %s"
        params.append(produto_id)
    sql += " ORDER BY mv.data_movimento DESC, mv.id DESC"
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_movimentacoes: {e}")
        return []


def registrar_movimentacao(dados):
    produto_id = _inteiro(dados.get("produto_id"))
    tipo = _texto(dados.get("tipo"))
    tipo = tipo.lower() if tipo else ""
    quantidade = _decimal(dados.get("quantidade"))
    if not produto_id:
        return None, "Informe o produto."
    if tipo not in ("entrada", "saida"):
        return None, "Informe o tipo de movimentação."
    if quantidade <= 0:
        return None, "A quantidade deve ser maior que zero."

    data_movimento = _data(dados.get("data_movimento")) or date.today()
    valor_unitario = _decimal(dados.get("valor_unitario"), 0) or None

    def operacao(cursor):
        cursor.execute(
            "SELECT nome, quantidade_atual FROM maq_produtos "
            "WHERE id = %s AND ativo = TRUE FOR UPDATE", (produto_id,),
        )
        produto = cursor.fetchone()
        if not produto:
            raise ValueError("Produto não encontrado ou inativo.")
        if tipo == "saida" and quantidade > float(produto["quantidade_atual"]):
            raise ValueError(
                f"Saldo insuficiente para {produto['nome']}. "
                f"Disponível: {float(produto['quantidade_atual']):,.2f}."
            )
        delta = quantidade if tipo == "entrada" else -quantidade
        cursor.execute("""
            INSERT INTO maq_movimentacoes
                (produto_id, tipo, quantidade, unidade, data_movimento,
                 valor_unitario, nota_fiscal, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            produto_id, tipo, quantidade, _texto(dados.get("unidade")),
            data_movimento, valor_unitario, _texto(dados.get("nota_fiscal")),
            _texto(dados.get("observacoes")),
        ))
        mov_id = cursor.fetchone()["id"]
        cursor.execute(
            "UPDATE maq_produtos SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
            (delta, produto_id),
        )
        return mov_id

    try:
        mov_id = executar_transacao(operacao)
        return mov_id, "Movimentação registrada e saldo atualizado!"
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"maquinario.registrar_movimentacao: {e}")
        return None, f"Erro ao registrar movimentação: {e}"


def excluir_movimentacao(id):
    """Reverte o saldo e desativa a movimentação na mesma transação."""
    def operacao(cursor):
        cursor.execute("""
            SELECT produto_id, tipo, quantidade FROM maq_movimentacoes
            WHERE id = %s AND ativo = TRUE FOR UPDATE
        """, (id,))
        mov = cursor.fetchone()
        if not mov:
            raise ValueError("Movimentação não encontrada.")
        sinal = 1 if mov["tipo"] == "saida" else -1
        cursor.execute(
            "UPDATE maq_produtos SET quantidade_atual = quantidade_atual + %s WHERE id = %s",
            (sinal * float(mov["quantidade"]), mov["produto_id"]),
        )
        cursor.execute("UPDATE maq_movimentacoes SET ativo = FALSE WHERE id = %s", (id,))

    try:
        executar_transacao(operacao)
        return True, "Movimentação removida e saldo recalculado."
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"maquinario.excluir_movimentacao: {e}")
        return False, f"Erro ao remover movimentação: {e}"


def resumo_estoque():
    try:
        linha = executar_query("""
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(quantidade_atual), 0) AS quantidade,
                   COALESCE(SUM(CASE WHEN estoque_minimo > 0
                                     AND quantidade_atual <= estoque_minimo
                                     THEN 1 ELSE 0 END), 0) AS baixos
            FROM maq_produtos WHERE ativo = TRUE
        """, fetch_one=True, dict_cursor=True) or {}
        mov = executar_query("""
            SELECT COUNT(*) AS total FROM maq_movimentacoes
            WHERE ativo = TRUE AND data_movimento >= CURRENT_DATE - INTERVAL '30 days'
        """, fetch_one=True, dict_cursor=True) or {}
        return {
            "total": int(linha.get("total") or 0),
            "quantidade": float(linha.get("quantidade") or 0),
            "baixos": int(linha.get("baixos") or 0),
            "movimentacoes_30d": int(mov.get("total") or 0),
        }
    except Exception as e:
        logger.error(f"maquinario.resumo_estoque: {e}")
        return {"total": 0, "quantidade": 0, "baixos": 0, "movimentacoes_30d": 0}


# ---------------------------------------------------------------------------
# Máquinas e manutenção
# ---------------------------------------------------------------------------
def listar_maquinas(ativas=True):
    sql = """
        SELECT m.*,
               (SELECT MAX(x.data_servico) FROM maq_manutencoes x
                 WHERE x.maquina_id = m.id AND x.ativo = TRUE) AS ultima_manutencao,
               (SELECT x.proxima_data FROM maq_manutencoes x
                 WHERE x.maquina_id = m.id AND x.ativo = TRUE AND x.proxima_data IS NOT NULL
                 ORDER BY x.data_servico DESC, x.id DESC LIMIT 1) AS proxima_data,
               (SELECT x.proximas_horas FROM maq_manutencoes x
                 WHERE x.maquina_id = m.id AND x.ativo = TRUE AND x.proximas_horas IS NOT NULL
                 ORDER BY x.data_servico DESC, x.id DESC LIMIT 1) AS proximas_horas,
               (SELECT COUNT(*) FROM maq_manutencoes x
                 WHERE x.maquina_id = m.id AND x.ativo = TRUE) AS total_manutencoes
        FROM maq_maquinas m
    """
    if ativas:
        sql += " WHERE m.ativo = TRUE"
    sql += " ORDER BY m.nome"
    try:
        return executar_query(sql, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_maquinas: {e}")
        return []


def buscar_maquina(id):
    if not id:
        return None
    for maquina in listar_maquinas(ativas=False):
        if maquina["id"] == id:
            return maquina
    return None


def inserir_maquina(dados):
    nome = _texto(dados.get("nome"))
    if not nome:
        return None, "Informe o nome da máquina."
    sql = """
        INSERT INTO maq_maquinas
            (nome, marca, modelo, ano, numero_serie, placa, horas_atuais,
             data_aquisicao, observacoes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (
        nome, _texto(dados.get("marca")), _texto(dados.get("modelo")),
        _texto(dados.get("ano")), _texto(dados.get("numero_serie")),
        _texto(dados.get("placa")), _decimal(dados.get("horas_atuais")),
        _data(dados.get("data_aquisicao")), _texto(dados.get("observacoes")),
    )
    try:
        maquina_id = executar_transacao(lambda cur: _inserir(cur, sql, params))
        return maquina_id, "Máquina cadastrada!"
    except Exception as e:
        logger.error(f"maquinario.inserir_maquina: {e}")
        return None, f"Erro ao cadastrar máquina: {e}"


def atualizar_maquina(id, dados):
    nome = _texto(dados.get("nome"))
    if not nome:
        return False, "Informe o nome da máquina."
    sql = """
        UPDATE maq_maquinas
        SET nome = %s, marca = %s, modelo = %s, ano = %s, numero_serie = %s,
            placa = %s, horas_atuais = %s, data_aquisicao = %s, observacoes = %s
        WHERE id = %s AND ativo = TRUE
    """
    params = (
        nome, _texto(dados.get("marca")), _texto(dados.get("modelo")),
        _texto(dados.get("ano")), _texto(dados.get("numero_serie")),
        _texto(dados.get("placa")), _decimal(dados.get("horas_atuais")),
        _data(dados.get("data_aquisicao")), _texto(dados.get("observacoes")), id,
    )

    def operacao(cursor):
        cursor.execute(sql, params)
        if cursor.rowcount == 0:
            raise ValueError("Máquina não encontrada.")

    try:
        executar_transacao(operacao)
        return True, "Máquina atualizada!"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"maquinario.atualizar_maquina: {e}")
        return False, f"Erro ao atualizar máquina: {e}"


def excluir_maquina(id):
    try:
        executar_query("UPDATE maq_maquinas SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Máquina removida. O histórico foi mantido."
    except Exception as e:
        logger.error(f"maquinario.excluir_maquina: {e}")
        return False, f"Erro ao remover máquina: {e}"


def atualizar_horimetro(id, horas):
    novo = _decimal(horas, None)
    if novo is None or novo < 0:
        return False, "Informe um horímetro válido."

    def operacao(cursor):
        cursor.execute(
            "SELECT horas_atuais FROM maq_maquinas WHERE id = %s AND ativo = TRUE FOR UPDATE",
            (id,),
        )
        atual = cursor.fetchone()
        if not atual:
            raise ValueError("Máquina não encontrada.")
        if novo < float(atual["horas_atuais"]):
            raise ValueError("O horímetro não pode ser menor que o registrado.")
        cursor.execute("UPDATE maq_maquinas SET horas_atuais = %s WHERE id = %s", (novo, id))

    try:
        executar_transacao(operacao)
        return True, "Horímetro atualizado!"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"maquinario.atualizar_horimetro: {e}")
        return False, f"Erro ao atualizar horímetro: {e}"


def listar_manutencoes(maquina_id=None, limite=200):
    sql = """
        SELECT mt.*, m.nome AS maquina_nome
        FROM maq_manutencoes mt
        JOIN maq_maquinas m ON m.id = mt.maquina_id
        WHERE mt.ativo = TRUE
    """
    params = []
    if maquina_id:
        sql += " AND mt.maquina_id = %s"
        params.append(maquina_id)
    sql += " ORDER BY mt.data_servico DESC, mt.id DESC"
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_manutencoes: {e}")
        return []


def _gravar_manutencao(id, dados):
    maquina_id = _inteiro(dados.get("maquina_id"))
    tipo = _texto(dados.get("tipo"))
    if not maquina_id:
        return None, "Informe a máquina."
    if not tipo:
        return None, "Informe o tipo de serviço."
    data_servico = _data(dados.get("data_servico")) or date.today()
    horimetro = _decimal(dados.get("horimetro"), None)

    def operacao(cursor):
        if horimetro is not None:
            cursor.execute(
                "SELECT horas_atuais FROM maq_maquinas WHERE id = %s AND ativo = TRUE FOR UPDATE",
                (maquina_id,),
            )
            maquina = cursor.fetchone()
            if not maquina:
                raise ValueError("Máquina não encontrada.")
            if horimetro < float(maquina["horas_atuais"]):
                raise ValueError("O horímetro não pode ser menor que o atual.")
            cursor.execute(
                "UPDATE maq_maquinas SET horas_atuais = %s WHERE id = %s",
                (horimetro, maquina_id),
            )
        campos = ("maquina_id", "tipo", "data_servico", "horimetro", "descricao",
                  "valor", "fornecedor", "proxima_data", "proximas_horas", "observacoes")
        valores = (
            maquina_id, tipo, data_servico, horimetro, _texto(dados.get("descricao")),
            _decimal(dados.get("valor")), _texto(dados.get("fornecedor")),
            _data(dados.get("proxima_data")),
            _decimal(dados.get("proximas_horas"), None), _texto(dados.get("observacoes")),
        )
        if id:
            atribuicoes = ", ".join(f"{campo} = %s" for campo in campos)
            cursor.execute(
                f"UPDATE maq_manutencoes SET {atribuicoes} "
                "WHERE id = %s AND ativo = TRUE", valores + (id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Manutenção não encontrada.")
            return id
        nomes = ", ".join(campos)
        marcadores = ", ".join(["%s"] * len(campos))
        cursor.execute(
            f"INSERT INTO maq_manutencoes ({nomes}) VALUES ({marcadores}) RETURNING id",
            valores,
        )
        return cursor.fetchone()["id"]

    try:
        registro_id = executar_transacao(operacao)
        return registro_id, "Manutenção registrada!"
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"maquinario._gravar_manutencao: {e}")
        return None, f"Erro ao salvar manutenção: {e}"


def inserir_manutencao(dados):
    return _gravar_manutencao(None, dados)


def atualizar_manutencao(id, dados):
    registro_id, mensagem = _gravar_manutencao(id, dados)
    return (registro_id is not None), mensagem


def excluir_manutencao(id):
    try:
        executar_query("UPDATE maq_manutencoes SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Manutenção removida do histórico ativo."
    except Exception as e:
        logger.error(f"maquinario.excluir_manutencao: {e}")
        return False, f"Erro ao remover manutenção: {e}"


def resumo_manutencoes():
    try:
        linha = executar_query("""
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(valor), 0) AS valor,
                   COALESCE(SUM(CASE WHEN data_servico >= CURRENT_DATE - INTERVAL '30 days'
                                     THEN 1 ELSE 0 END), 0) AS ultimos_30d
            FROM maq_manutencoes WHERE ativo = TRUE
        """, fetch_one=True, dict_cursor=True) or {}
        return {
            "total": int(linha.get("total") or 0),
            "valor": float(linha.get("valor") or 0),
            "ultimos_30d": int(linha.get("ultimos_30d") or 0),
        }
    except Exception as e:
        logger.error(f"maquinario.resumo_manutencoes: {e}")
        return {"total": 0, "valor": 0, "ultimos_30d": 0}


# ---------------------------------------------------------------------------
# Combustível: abastecimentos, boletos e preço público da ANP
# ---------------------------------------------------------------------------
def listar_abastecimentos(pendentes=False, limite=None):
    sql = """
        SELECT a.*, m.nome AS maquina_nome,
               CASE WHEN a.pago THEN 'pago'
                    WHEN a.vencimento IS NOT NULL AND a.vencimento < CURRENT_DATE
                    THEN 'vencido' ELSE 'pendente' END AS situacao
        FROM maq_abastecimentos a
        LEFT JOIN maq_maquinas m ON m.id = a.maquina_id
        WHERE a.ativo = TRUE
    """
    if pendentes:
        sql += " AND a.pago = FALSE"
    sql += " ORDER BY a.data_abastecimento DESC, a.id DESC"
    params = []
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_abastecimentos: {e}")
        return []


def buscar_abastecimento(id):
    if not id:
        return None
    try:
        return executar_query(
            "SELECT * FROM maq_abastecimentos WHERE id = %s AND ativo = TRUE",
            (id,), fetch_one=True, dict_cursor=True,
        )
    except Exception as e:
        logger.error(f"maquinario.buscar_abastecimento: {e}")
        return None


def _gravar_abastecimento(id, dados):
    quantidade = _decimal(dados.get("quantidade_litros"))
    valor_litro = _decimal(dados.get("valor_litro"))
    if quantidade <= 0:
        return None, "Informe a quantidade em litros."
    if valor_litro <= 0:
        return None, "Informe o valor pago por litro."
    total = _decimal(dados.get("valor_total"), 0)
    if total <= 0:
        total = quantidade * valor_litro

    pago = _booleano(dados.get("pago"))
    vencimento = _data(dados.get("vencimento"))
    lembrete = _data(dados.get("lembrete_em"))
    if vencimento and not pago and lembrete is None:
        lembrete = vencimento - timedelta(days=3)

    campos = ("maquina_id", "data_abastecimento", "produto", "quantidade_litros",
              "valor_litro", "valor_total", "fornecedor", "boleto", "vencimento",
              "lembrete_em", "pago", "data_pagamento", "observacoes")
    valores = (
        _inteiro(dados.get("maquina_id"), None),
        _data(dados.get("data_abastecimento")) or date.today(),
        _texto(dados.get("produto")) or PRODUTO_DIESEL,
        quantidade, valor_litro, total, _texto(dados.get("fornecedor")),
        _texto(dados.get("boleto")), vencimento, lembrete, pago,
        date.today() if pago else None, _texto(dados.get("observacoes")),
    )

    def operacao(cursor):
        dados_completos = list(valores)
        if id and pago:
            cursor.execute(
                "SELECT data_pagamento FROM maq_abastecimentos WHERE id = %s", (id,),
            )
            anterior = cursor.fetchone()
            if anterior and anterior["data_pagamento"]:
                dados_completos[11] = anterior["data_pagamento"]
        if id:
            atribuicoes = ", ".join(f"{campo} = %s" for campo in campos)
            cursor.execute(
                f"UPDATE maq_abastecimentos SET {atribuicoes} "
                "WHERE id = %s AND ativo = TRUE", tuple(dados_completos) + (id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Abastecimento não encontrado.")
            return id
        nomes = ", ".join(campos)
        marcadores = ", ".join(["%s"] * len(campos))
        cursor.execute(
            f"INSERT INTO maq_abastecimentos ({nomes}) VALUES ({marcadores}) RETURNING id",
            tuple(dados_completos),
        )
        return cursor.fetchone()["id"]

    try:
        registro_id = executar_transacao(operacao)
        return registro_id, "Abastecimento registrado!"
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"maquinario._gravar_abastecimento: {e}")
        return None, f"Erro ao salvar abastecimento: {e}"


def inserir_abastecimento(dados):
    return _gravar_abastecimento(None, dados)


def atualizar_abastecimento(id, dados):
    registro_id, mensagem = _gravar_abastecimento(id, dados)
    return (registro_id is not None), mensagem


def marcar_pago(id):
    try:
        executar_query("""
            UPDATE maq_abastecimentos
            SET pago = TRUE, data_pagamento = CURRENT_DATE
            WHERE id = %s AND ativo = TRUE
        """, (id,))
        return True, "Pagamento registrado!"
    except Exception as e:
        logger.error(f"maquinario.marcar_pago: {e}")
        return False, f"Erro ao registrar pagamento: {e}"


def excluir_abastecimento(id):
    try:
        executar_query("UPDATE maq_abastecimentos SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Abastecimento removido."
    except Exception as e:
        logger.error(f"maquinario.excluir_abastecimento: {e}")
        return False, f"Erro ao remover abastecimento: {e}"


def resumo_combustivel():
    try:
        linha = executar_query("""
            SELECT COALESCE(SUM(quantidade_litros), 0) AS litros,
                   COALESCE(SUM(valor_total), 0) AS gasto,
                   COALESCE(SUM(CASE WHEN pago = FALSE THEN 1 ELSE 0 END), 0) AS pendentes,
                   COALESCE(SUM(CASE WHEN pago = FALSE THEN valor_total ELSE 0 END), 0) AS a_pagar
            FROM maq_abastecimentos WHERE ativo = TRUE
        """, fetch_one=True, dict_cursor=True) or {}
        litros = float(linha.get("litros") or 0)
        gasto = float(linha.get("gasto") or 0)
        return {
            "litros": litros,
            "gasto": gasto,
            "preco_pago": (gasto / litros) if litros else 0,
            "pendentes": int(linha.get("pendentes") or 0),
            "a_pagar": float(linha.get("a_pagar") or 0),
        }
    except Exception as e:
        logger.error(f"maquinario.resumo_combustivel: {e}")
        return {"litros": 0, "gasto": 0, "preco_pago": 0, "pendentes": 0, "a_pagar": 0}


def _coluna_csv(colunas, *candidatos):
    norm = {str(c).replace("\ufeff", "").strip().lower(): c for c in colunas}
    for candidato in candidatos:
        if candidato.lower() in norm:
            return norm[candidato.lower()]
    return None


def _carregar_csv_anp():
    resposta = requests.get(ANP_URL, headers=HEADERS, timeout=TIMEOUT_ANP)
    resposta.raise_for_status()
    try:
        tabela = pd.read_csv(
            io.BytesIO(resposta.content), sep=";", encoding="latin-1",
            dtype=str, keep_default_na=False, low_memory=False,
        )
    except UnicodeDecodeError:
        tabela = pd.read_csv(
            io.BytesIO(resposta.content), sep=";", encoding="utf-8",
            dtype=str, keep_default_na=False, low_memory=False,
        )
    tabela.columns = [str(c).replace("\ufeff", "").strip() for c in tabela.columns]
    col_produto = _coluna_csv(tabela.columns, "Produto")
    col_data = _coluna_csv(tabela.columns, "Data da Coleta")
    col_valor = _coluna_csv(tabela.columns, "Valor de Venda")
    col_uf = _coluna_csv(tabela.columns, "Estado - Sigla", "UF")
    col_municipio = _coluna_csv(tabela.columns, "Municipio", "Município")
    if not all((col_produto, col_data, col_valor, col_uf, col_municipio)):
        raise ValueError("CSV da ANP mudou as colunas (formato não reconhecido).")

    registros = []
    for _, linha in tabela.iterrows():
        if str(linha.get(col_produto, "")).strip().upper() != PRODUTO_DIESEL:
            continue
        data = _data(linha.get(col_data))
        valor = _decimal(linha.get(col_valor), None)
        if not data or valor is None or valor <= 0:
            continue
        registros.append({
            "data": data,
            "uf": str(linha.get(col_uf, "")).strip().upper(),
            "municipio": str(linha.get(col_municipio, "")).strip().upper(),
            "valor": valor,
        })
    if not registros:
        raise ValueError(f"ANP não trouxe cotações de {PRODUTO_DIESEL}.")
    return registros


def _salvar_precos_anp(data_coleta, grupos):
    def operacao(cursor):
        for nivel, municipio, uf, valores in grupos:
            if not valores:
                continue
            cursor.execute("""
                INSERT INTO maq_precos_diesel
                    (nivel, municipio, uf, produto, data_coleta, preco_medio,
                     preco_min, preco_max, amostras)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (nivel, municipio, data_coleta) DO UPDATE SET
                    preco_medio = EXCLUDED.preco_medio,
                    preco_min = EXCLUDED.preco_min,
                    preco_max = EXCLUDED.preco_max,
                    amostras = EXCLUDED.amostras,
                    ativo = TRUE,
                    data_cadastro = CURRENT_TIMESTAMP
            """, (
                nivel, municipio, uf, PRODUTO_DIESEL, data_coleta,
                round(sum(valores) / len(valores), 4), round(min(valores), 4),
                round(max(valores), 4), len(valores),
            ))

    try:
        executar_transacao(operacao)
    except Exception as e:
        logger.error(f"maquinario._salvar_precos_anp: {e}")
        raise


def buscar_precos_anp(force=False, usar_cache_em_falha=True):
    """Baixa o CSV público da ANP e salva o resumo semanal (Brasil/UF/cidade)."""
    if (not force and _DADOS_ANP["valor"] and _DADOS_ANP["timestamp"]
            and (datetime.now() - _DADOS_ANP["timestamp"]).total_seconds()
            < CACHE_ANP_MINUTOS * 60):
        return _DADOS_ANP["valor"]

    try:
        registros = _carregar_csv_anp()
        agrupados = defaultdict(list)
        for registro in registros:
            chave = (registro["data"], registro["uf"], registro["municipio"])
            agrupados[chave].append(registro["valor"])
        # A ANP publica semanalmente e nem todo município aparece em toda semana.
        # Usa a semana mais recente em que a cidade de referência tem coleta.
        datas_cidade = sorted(
            data for (data, uf, nome) in agrupados
            if uf == ANP_UF and nome == ANP_MUNICIPIO
        )
        if not datas_cidade:
            raise ValueError(
                f"ANP sem {PRODUTO_DIESEL} para {ANP_MUNICIPIO}/{ANP_UF} "
                "no arquivo publicado."
            )
        ultima_data = datas_cidade[-1]
        def valores_no_periodo(condicao):
            encontrados = []
            for (data, uf, nome), valores in agrupados.items():
                if condicao(data, uf, nome):
                    encontrados.extend(valores)
            return encontrados

        municipio = valores_no_periodo(
            lambda data, uf, nome: data == ultima_data
            and uf == ANP_UF and nome == ANP_MUNICIPIO
        )
        estado = valores_no_periodo(
            lambda data, uf, nome: data == ultima_data and uf == ANP_UF
        )
        brasil = valores_no_periodo(lambda data, uf, nome: data == ultima_data)
        grupos = [
            ("brasil", "BRASIL", None, brasil),
            ("estado", f"ESTADO {ANP_UF}", ANP_UF, estado),
            ("municipio", ANP_MUNICIPIO, ANP_UF, municipio),
        ]
        _salvar_precos_anp(ultima_data, grupos)

        def resumo(valores):
            return {
                "preco": round(sum(valores) / len(valores), 4),
                "min": round(min(valores), 4),
                "max": round(max(valores), 4),
                "amostras": len(valores),
            }

        valor = {
            "brasil": resumo(brasil),
            "estado": resumo(estado),
            "municipio": resumo(municipio),
            "semana": ultima_data,
            "atualizado_em": datetime.now(),
            "url": ANP_URL,
            "municipio_referencia": f"{ANP_MUNICIPIO}/{ANP_UF}",
        }
        _DADOS_ANP.update(valor=valor, timestamp=datetime.now())
        return valor
    except Exception as e:
        logger.error(f"maquinario.buscar_precos_anp: {e}")
        if usar_cache_em_falha and _DADOS_ANP["valor"]:
            return _DADOS_ANP["valor"]
        raise


def obter_preco_referencia():
    """Preço mais recente salvo; se não houver, busca na ANP."""
    try:
        linhas = executar_query("""
            SELECT nivel, municipio, uf, data_coleta, preco_medio, preco_min,
                   preco_max, amostras, data_cadastro
            FROM maq_precos_diesel
            WHERE ativo = TRUE AND data_coleta = (
                SELECT MAX(data_coleta) FROM maq_precos_diesel WHERE ativo = TRUE
            )
        """, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.obter_preco_referencia: {e}")
        linhas = []
    if not linhas:
        try:
            return buscar_precos_anp()
        except Exception:
            return None

    mapa = {linha["nivel"]: linha for linha in linhas}
    if "municipio" not in mapa:
        return None

    def bloco(nivel, padrao):
        linha = mapa.get(nivel)
        if not linha:
            return padrao
        return {
            "preco": float(linha["preco_medio"]),
            "min": float(linha["preco_min"] or 0),
            "max": float(linha["preco_max"] or 0),
            "amostras": int(linha["amostras"] or 0),
        }

    municipio = mapa["municipio"]
    return {
        "brasil": bloco("brasil", {"preco": 0, "min": 0, "max": 0, "amostras": 0}),
        "estado": bloco("estado", {"preco": 0, "min": 0, "max": 0, "amostras": 0}),
        "municipio": bloco("municipio", {"preco": 0, "min": 0, "max": 0, "amostras": 0}),
        "semana": municipio["data_coleta"],
        "atualizado_em": municipio["data_cadastro"],
        "url": ANP_URL,
        "municipio_referencia": f"{municipio['municipio']}/{municipio['uf'] or ''}".strip("/"),
    }


def listar_precos_diesel(limite=30):
    try:
        return executar_query("""
            SELECT nivel, municipio, uf, data_coleta, preco_medio, preco_min,
                   preco_max, amostras, data_cadastro
            FROM maq_precos_diesel
            WHERE ativo = TRUE
            ORDER BY data_coleta DESC, nivel, municipio
            LIMIT %s
        """, (limite,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_precos_diesel: {e}")
        return []


def verificar_fonte():
    """Registro consumido pelo monitor de integrações (cotacoes.MONITORAMENTO)."""
    dados = buscar_precos_anp(force=True, usar_cache_em_falha=False)
    return {
        "anp_diesel": {
            "chave": "anp_diesel",
            "fonte": "ANP Diesel S10",
            "papel": dados["municipio_referencia"],
            "descricao": "Preço médio semanal de revenda (dados abertos)",
            "valor": dados["municipio"]["preco"],
            "unidade": "R$/L",
            "data_origem": dados["semana"].strftime("%d/%m/%Y"),
        }
    }


# ---------------------------------------------------------------------------
# Gastos com maquinário
# ---------------------------------------------------------------------------
def listar_gastos(limite=300):
    sql = """
        SELECT g.*, m.nome AS maquina_nome
        FROM maq_gastos g
        LEFT JOIN maq_maquinas m ON m.id = g.maquina_id
        WHERE g.ativo = TRUE
        ORDER BY g.data_gasto DESC, g.id DESC
    """
    params = []
    if limite:
        sql += " LIMIT %s"
        params.append(limite)
    try:
        return executar_query(sql, tuple(params), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"maquinario.listar_gastos: {e}")
        return []


def buscar_gasto(id):
    if not id:
        return None
    try:
        return executar_query(
            "SELECT * FROM maq_gastos WHERE id = %s AND ativo = TRUE",
            (id,), fetch_one=True, dict_cursor=True,
        )
    except Exception as e:
        logger.error(f"maquinario.buscar_gasto: {e}")
        return None


def _gravar_gasto(id, dados):
    descricao = _texto(dados.get("descricao"))
    valor = _decimal(dados.get("valor"))
    if not descricao:
        return None, "Informe a descrição do gasto."
    if valor <= 0:
        return None, "Informe o valor do gasto."

    campos = ("data_gasto", "descricao", "categoria", "maquina_id", "valor",
              "local_compra", "fornecedor", "nota_fiscal", "observacoes")
    valores = (
        _data(dados.get("data_gasto")) or date.today(), descricao,
        _texto(dados.get("categoria")) or "Outros",
        _inteiro(dados.get("maquina_id"), None), valor,
        _texto(dados.get("local_compra")), _texto(dados.get("fornecedor")),
        _texto(dados.get("nota_fiscal")), _texto(dados.get("observacoes")),
    )

    def operacao(cursor):
        if id:
            atribuicoes = ", ".join(f"{campo} = %s" for campo in campos)
            cursor.execute(
                f"UPDATE maq_gastos SET {atribuicoes} WHERE id = %s AND ativo = TRUE",
                valores + (id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Gasto não encontrado.")
            return id
        nomes = ", ".join(campos)
        marcadores = ", ".join(["%s"] * len(campos))
        cursor.execute(
            f"INSERT INTO maq_gastos ({nomes}) VALUES ({marcadores}) RETURNING id",
            valores,
        )
        return cursor.fetchone()["id"]

    try:
        registro_id = executar_transacao(operacao)
        return registro_id, "Gasto registrado!"
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"maquinario._gravar_gasto: {e}")
        return None, f"Erro ao salvar gasto: {e}"


def inserir_gasto(dados):
    return _gravar_gasto(None, dados)


def atualizar_gasto(id, dados):
    registro_id, mensagem = _gravar_gasto(id, dados)
    return (registro_id is not None), mensagem


def excluir_gasto(id):
    try:
        executar_query("UPDATE maq_gastos SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Gasto removido."
    except Exception as e:
        logger.error(f"maquinario.excluir_gasto: {e}")
        return False, f"Erro ao remover gasto: {e}"


def resumo_gastos():
    try:
        linha = executar_query("""
            SELECT COUNT(*) AS total, COALESCE(SUM(valor), 0) AS valor,
                   COALESCE(SUM(CASE WHEN data_gasto >= date_trunc('month', CURRENT_DATE)
                                     THEN valor ELSE 0 END), 0) AS mes_atual
            FROM maq_gastos WHERE ativo = TRUE
        """, fetch_one=True, dict_cursor=True) or {}
        por_categoria = executar_query("""
            SELECT categoria, SUM(valor) AS total, COUNT(*) AS quantidade
            FROM maq_gastos WHERE ativo = TRUE
            GROUP BY categoria ORDER BY total DESC
        """, fetch_all=True, dict_cursor=True) or []
        return {
            "total": int(linha.get("total") or 0),
            "valor": float(linha.get("valor") or 0),
            "mes_atual": float(linha.get("mes_atual") or 0),
            "por_categoria": [
                {
                    "categoria": item.get("categoria") or "Outros",
                    "total": float(item.get("total") or 0),
                    "quantidade": int(item.get("quantidade") or 0),
                }
                for item in por_categoria
            ],
        }
    except Exception as e:
        logger.error(f"maquinario.resumo_gastos: {e}")
        return {"total": 0, "valor": 0, "mes_atual": 0, "por_categoria": []}


# ---------------------------------------------------------------------------
# Alertas exibidos no painel
# ---------------------------------------------------------------------------
def listar_alertas():
    alertas = []
    hoje = date.today()
    try:
        for maquina in listar_maquinas():
            nome = maquina["nome"]
            proxima_data = _data(maquina.get("proxima_data"))
            if proxima_data and proxima_data <= hoje:
                dias = (hoje - proxima_data).days
                alertas.append({
                    "tipo": "warning",
                    "titulo": f"Revisão de {nome}",
                    "detalhe": (f"Vencida há {dias} dia(s) "
                                f"({proxima_data.strftime('%d/%m/%Y')})."),
                    "url": "maquinario.manutencoes",
                })
            proximas_horas = maquina.get("proximas_horas")
            if proximas_horas and float(maquina["horas_atuais"] or 0) >= float(proximas_horas):
                alertas.append({
                    "tipo": "warning",
                    "titulo": f"Horímetro de {nome}",
                    "detalhe": f"Passou de {float(proximas_horas):,.0f} h previstas.",
                    "url": "maquinario.manutencoes",
                })
        for abastecimento in listar_abastecimentos(pendentes=True):
            vencimento = _data(abastecimento.get("vencimento"))
            lembrete = _data(abastecimento.get("lembrete_em"))
            alvo = vencimento or lembrete
            if alvo and alvo <= hoje + timedelta(days=3):
                alertas.append({
                    "tipo": "danger" if vencimento and vencimento < hoje else "warning",
                    "titulo": f"Boleto pendente — {abastecimento.get('fornecedor') or 'fornecedor não informado'}",
                    "detalhe": f"Vencimento/lembrete em {alvo.strftime('%d/%m/%Y')} · R$ {float(abastecimento['valor_total']):,.2f}",
                    "url": "maquinario.abastecimentos",
                })
        baixos = [
            p for p in listar_produtos()
            if float(p["estoque_minimo"] or 0) > 0
            and float(p["quantidade_atual"] or 0) <= float(p["estoque_minimo"])
        ]
        if baixos:
            alertas.append({
                "tipo": "warning",
                "titulo": "Estoque de maquinário baixo",
                "detalhe": "Itens abaixo do mínimo: " + ", ".join(p["nome"] for p in baixos[:5]),
                "url": "maquinario.estoque",
            })
    except Exception as e:
        logger.error(f"maquinario.listar_alertas: {e}")
    return alertas
