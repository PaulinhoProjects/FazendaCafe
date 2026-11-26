"""
Módulo de fornecedores pré-cadastrados.
A nota fiscal guarda nome e CNPJ como snapshot; a lista serve para agilizar o cadastro.
"""
import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao
from app.models import get_logger
from app.modules.estoque import normalizar_nome

logger = get_logger(__name__)


def _limpar_nome(nome):
    """Remove espaços repetidos para evitar 'Agro  Insumos' x 'Agro Insumos'."""
    return re.sub(r'\s+', ' ', (nome or '').strip())


def listar_fornecedores(ativos=True):
    """Lista fornecedores em ordem alfabética."""
    sql = "SELECT id, nome, cnpj, telefone, ativo FROM fornecedores"
    if ativos:
        sql += " WHERE ativo = TRUE"
    sql += " ORDER BY nome"
    try:
        return executar_query(sql, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"fornecedores.listar_fornecedores: {e}")
        return []


def buscar_fornecedor_por_id(id):
    if not id:
        return None
    try:
        return executar_query(
            "SELECT id, nome, cnpj, telefone, ativo FROM fornecedores WHERE id = %s",
            (id,), fetch_one=True, dict_cursor=True)
    except Exception as e:
        logger.error(f"fornecedores.buscar_fornecedor_por_id: {e}")
        return None


def _validar_duplicado(cursor, nome, excluir_id=None):
    cursor.execute("SELECT id, nome FROM fornecedores WHERE ativo = TRUE")
    alvo = normalizar_nome(nome)
    for r in cursor.fetchall():
        if excluir_id and r['id'] == excluir_id:
            continue
        if normalizar_nome(r['nome']) == alvo:
            raise ValueError('Já existe fornecedor com esse nome.')


def inserir_fornecedor(dados):
    """Cadastra um fornecedor. Retorna (id, mensagem)."""
    nome = _limpar_nome(dados.get('nome'))
    if not nome:
        return None, 'Informe o nome do fornecedor.'

    def operacao(cursor):
        _validar_duplicado(cursor, nome)
        cursor.execute("""
            INSERT INTO fornecedores (nome, cnpj, telefone)
            VALUES (%s, %s, %s) RETURNING id
        """, (nome, (dados.get('cnpj') or '').strip() or None,
              (dados.get('telefone') or '').strip() or None))
        return cursor.fetchone()['id']

    try:
        fornecedor_id = executar_transacao(operacao)
        return fornecedor_id, 'Fornecedor cadastrado!'
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"fornecedores.inserir_fornecedor: {e}")
        return None, f'Erro ao cadastrar fornecedor: {e}'


def atualizar_fornecedor(id, dados):
    """Atualiza os dados do fornecedor. Retorna (sucesso, mensagem)."""
    nome = _limpar_nome(dados.get('nome'))
    if not nome:
        return False, 'Informe o nome do fornecedor.'

    def operacao(cursor):
        cursor.execute("SELECT id FROM fornecedores WHERE id = %s AND ativo = TRUE", (id,))
        if not cursor.fetchone():
            raise ValueError('Fornecedor não encontrado.')
        _validar_duplicado(cursor, nome, excluir_id=id)
        cursor.execute("""
            UPDATE fornecedores
            SET nome = %s, cnpj = %s, telefone = %s
            WHERE id = %s
        """, (nome, (dados.get('cnpj') or '').strip() or None,
              (dados.get('telefone') or '').strip() or None, id))

    try:
        executar_transacao(operacao)
        return True, 'Fornecedor atualizado!'
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"fornecedores.atualizar_fornecedor: {e}")
        return False, f'Erro ao atualizar fornecedor: {e}'


def excluir_fornecedor(id):
    """Exclusão lógica. Notas antigas mantêm o nome e o CNPJ salvos."""
    try:
        executar_query(
            "UPDATE fornecedores SET ativo = FALSE WHERE id = %s", (id,))
        return True, 'Fornecedor removido da lista. As notas antigas foram mantidas.'
    except Exception as e:
        logger.error(f"fornecedores.excluir_fornecedor: {e}")
        return False, f'Erro ao remover fornecedor: {e}'
