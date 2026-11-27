"""
Módulo de Análises de Solo, Folha, Raiz, Água e demais laudos
Gerencia laboratórios, análises, laudos em PDF e resultados
"""

import sys
import os
import re
import zlib
import unicodedata
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from contextlib import contextmanager
from database import executar_query, executar_transacao, conexao_dedicada
from datetime import datetime

logger = logging.getLogger(__name__)

# Ordem de prioridade: um laudo de raiz com "solo" no texto não vira Solo.
# "Folha" é gravado no banco como "Foliar" (nome já existente no sistema).
_PADROES_TIPO = (
    ('Raiz (Nematódeos)', ('nematoid', 'nematode', 'nematodo', 'raiz', 'raizes',
                           'root', 'meloidogyne', 'pratylenchus')),
    ('Água', ('agua', 'irrig', 'water', 'hidro', 'hydro')),
    ('Foliar', ('folha', 'foliar', 'leaf')),
    ('Solo', ('solo', 'soil', 'terra')),
    ('Substrato', ('substrato', 'turfa', 'fibra de coco')),
)


def _normalizar_texto(valor):
    """Remove acentos e caixa para comparar nomes de arquivos e texto do PDF."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(valor or '').lower())
        if not unicodedata.combining(c)
    )


def extrair_dica_texto_pdf(caminho, limite=50000, max_entrada=2_000_000, max_descompactado=4_000_000):
    """
    Dica opcional de classificação lida do PDF com recursos da biblioteca padrão.
    Não é extração de resultados: apenas termos para sugerir Solo/Folha/Raiz/Água.
    Lê no máximo `max_entrada` bytes do arquivo, descompacta no máximo
    `max_descompactado` bytes no total e para assim que junta `limite` caracteres.
    Falha silenciosamente (logada) em PDFs com compressão/encoding diferente.
    """
    try:
        with open(caminho, 'rb') as arquivo:
            dados = arquivo.read(max_entrada)
        partes, total = [], 0

        def juntar(bloco):
            nonlocal total
            for trecho in re.findall(rb'[ -~]{4,}', bloco):
                texto = trecho.decode('latin-1', 'ignore')
                partes.append(texto)
                total += len(texto) + 1
                if total >= limite:
                    return True
            return False

        if juntar(dados):
            return ' '.join(partes)[:limite]
        orcamento = max_descompactado
        for bloco in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', dados, re.S):
            if orcamento <= 0:
                break
            try:
                descompactador = zlib.decompressobj()
                saida = descompactador.decompress(bloco.group(1), orcamento)
            except zlib.error:
                continue  # bloco sem zlib: o texto cru já foi lido acima
            orcamento -= len(saida)
            if juntar(saida):
                break
        return ' '.join(partes)[:limite]
    except Exception as e:
        logger.error(f"analises.extrair_dica_texto_pdf: {e}")
        return ''


def classificar_laudo(nome_arquivo, texto=''):
    """Sugere o tipo de análise pelo nome do arquivo e, se houver, pelo texto do PDF."""
    nome = _normalizar_texto(nome_arquivo)
    corpo = _normalizar_texto(texto)
    sugestao = 'Outros'
    origem = 'arquivo'

    for tipo, palavras in _PADROES_TIPO:
        if any(palavra in nome for palavra in palavras):
            sugestao = tipo
            break
    else:
        origem = 'conteudo'
        for tipo, palavras in _PADROES_TIPO:
            if any(palavra in corpo for palavra in palavras):
                sugestao = tipo
                break

    tipos = listar_tipos_analise()
    por_nome = {_normalizar_texto(t['nome']): t for t in tipos}
    tipo = por_nome.get(_normalizar_texto(sugestao))
    if not tipo:
        tipo = por_nome.get('outros') or {'id': None, 'nome': 'Outros'}
    return {
        'tipo_id': tipo['id'],
        'tipo_nome': tipo['nome'],
        'origem': origem if sugestao != 'Outros' else 'manual',
    }


def contar_analises():
    """Total de análises ativas (sem o limite da listagem)."""
    try:
        r = executar_query("SELECT COUNT(*) AS total FROM analises WHERE ativo = TRUE",
                           fetch_one=True, dict_cursor=True)
        return int(r['total'] or 0) if r else 0
    except Exception as e:
        logger.error(f"analises.contar_analises: {e}")
        return 0


def contar_por_tipo():
    """Totais de análises ativas por tipo (para separar Solo/Folha/Raiz/Água)."""
    query = """
    SELECT tp.nome AS tipo_nome, tp.id AS tipo_id, COUNT(a.id) AS total
    FROM tipos_analise tp
    LEFT JOIN analises a ON a.tipo_analise_id = tp.id AND a.ativo = TRUE
    WHERE tp.ativo = TRUE
    GROUP BY tp.id, tp.nome
    ORDER BY tp.nome
    """
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True) or []
        return [{'id': r['tipo_id'], 'nome': r['tipo_nome'], 'total': int(r['total'] or 0)}
                for r in resultado]
    except Exception as e:
        logger.error(f"analises.contar_por_tipo: {e}")
        return []

# =====================================================
# FUNÇÕES PARA TIPOS DE ANÁLISE
# =====================================================

def listar_tipos_analise():
    query = "SELECT id, nome FROM tipos_analise WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        return [{'id': r['id'], 'nome': r['nome']} for r in resultado] if resultado else []
    except Exception as e:
        logger.error(f"Erro ao listar tipos: {e}")
        return []

# =====================================================
# FUNÇÕES PARA PARÂMETROS
# =====================================================

def listar_parametros_por_tipo(tipo_analise_id):
    query = """
    SELECT id, nome, unidade 
    FROM parametros_analise 
    WHERE tipo_analise_id = %s AND ativo = TRUE 
    ORDER BY ordem_exibicao
    """
    try:
        resultado = executar_query(query, (tipo_analise_id,), fetch_all=True, dict_cursor=True)
        return [{'id': r['id'], 'nome': r['nome'], 'unidade': r['unidade']} for r in resultado] if resultado else []
    except Exception as e:
        logger.error(f"Erro ao listar parâmetros: {e}")
        return []

# =====================================================
# FUNÇÕES PARA LABORATÓRIOS
# =====================================================

def listar_laboratorios():
    """Retorna lista de laboratórios ativos"""
    query = "SELECT id, nome, responsavel, telefone, email, endereco, observacoes FROM laboratorios WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True, dict_cursor=True)
        if not resultado:
            return []
        laboratorios = []
        for r in resultado:
            laboratorios.append({
                'id': r['id'],
                'nome': r['nome'],
                'responsavel': r['responsavel'],
                'telefone': r['telefone'],
                'email': r['email'],
                'endereco': r['endereco'],
                'observacoes': r['observacoes']
            })
        return laboratorios
    except Exception as e:
        logger.error(f"Erro ao listar laboratórios: {e}")
        return []

def inserir_laboratorio(dados):
    query = """
    INSERT INTO laboratorios (nome, responsavel, telefone, email, endereco, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['nome'], dados.get('responsavel'), dados.get('telefone'),
             dados.get('email'), dados.get('endereco'), dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        logger.error(f"Erro ao inserir laboratório: {e}")
        return None

# =====================================================
# FUNÇÕES PARA ANÁLISES
# =====================================================

_SQL_ANALISES = """
SELECT a.id, a.talhao_id, t.nome AS talhao_nome,
       a.tipo_analise_id, tp.nome AS tipo_nome,
       a.laboratorio_id, l.nome AS lab_nome,
       a.data_coleta, a.data_resultado, a.numero_protocolo,
       a.responsavel_coleta, a.observacoes, a.arquivo_pdf, a.arquivo_original
FROM analises a
LEFT JOIN talhoes t ON t.id = a.talhao_id
JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
LEFT JOIN laboratorios l ON l.id = a.laboratorio_id
WHERE a.ativo = TRUE
"""


def _mapear_analise(r):
    return {
        'id': r['id'],
        'talhao_id': r['talhao_id'],
        'talhao_nome': r['talhao_nome'],
        'tipo_id': r['tipo_analise_id'],
        'tipo_nome': r['tipo_nome'],
        'laboratorio_id': r['laboratorio_id'],
        'laboratorio_nome': r['lab_nome'],
        'data_coleta': r['data_coleta'],
        'data_resultado': r['data_resultado'],
        'numero_protocolo': r['numero_protocolo'],
        'responsavel': r['responsavel_coleta'],
        'observacoes': r['observacoes'],
        'arquivo_pdf': r['arquivo_pdf'],
        'arquivo_original': r['arquivo_original'],
    }


def listar_analises(talhao_id=None, tipo_id=None, limite=100):
    """Lista análises ativas; talhão é opcional (ex.: análise de água)."""
    query = _SQL_ANALISES
    params = []
    if talhao_id:
        query += " AND a.talhao_id = %s"
        params.append(talhao_id)
    if tipo_id:
        query += " AND a.tipo_analise_id = %s"
        params.append(tipo_id)
    query += " ORDER BY a.data_coleta DESC NULLS LAST, a.id DESC LIMIT %s"
    params.append(limite)

    try:
        resultado = executar_query(query, tuple(params), fetch_all=True, dict_cursor=True)
        return [_mapear_analise(r) for r in resultado] if resultado else []
    except Exception as e:
        logger.error(f"Erro ao listar análises: {e}")
        return []


def buscar_analise_por_id(id):
    try:
        r = executar_query(_SQL_ANALISES + " AND a.id = %s", (id,),
                           fetch_one=True, dict_cursor=True)
        return _mapear_analise(r) if r else None
    except Exception as e:
        logger.error(f"Erro ao buscar análise: {e}")
        return None

# =====================================================
# FUNÇÕES PARA RESULTADOS
# =====================================================

def inserir_resultado(dados):
    query = """
    INSERT INTO resultados_analise (analise_id, parametro_id, valor, interpretacao, observacoes)
    VALUES (%s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['analise_id'], dados['parametro_id'], dados['valor'],
             dados.get('interpretacao'), dados.get('observacoes')),
            fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        logger.error(f"Erro ao inserir resultado: {e}")
        return None

def listar_resultados_por_analise(analise_id):
    query = """
    SELECT r.id, p.nome as parametro, p.unidade, r.valor, r.interpretacao, r.observacoes
    FROM resultados_analise r
    JOIN parametros_analise p ON p.id = r.parametro_id
    WHERE r.analise_id = %s
    ORDER BY p.ordem_exibicao
    """
    try:
        resultado = executar_query(query, (analise_id,), fetch_all=True, dict_cursor=True)
        resultados = []
        for r in resultado:
            resultados.append({
                'id': r['id'],
                'parametro': r['parametro'],
                'unidade': r['unidade'],
                'valor': float(r['valor']) if r['valor'] else None,
                'interpretacao': r['interpretacao'],
                'observacoes': r['observacoes']
            })
        return resultados
    except Exception as e:
        logger.error(f"Erro ao listar resultados: {e}")
        return []
    
_SQL_INSERIR_ANALISE = """
INSERT INTO analises
    (talhao_id, tipo_analise_id, laboratorio_id, data_coleta,
     data_resultado, numero_protocolo, responsavel_coleta, observacoes,
     arquivo_pdf, arquivo_original)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
"""


def _valores_analise(dados):
    return (
        dados.get('talhao_id') or None,
        dados['tipo_id'],
        dados.get('laboratorio_id') or None,
        dados.get('data_coleta') or None,
        dados.get('data_resultado') or None,
        dados.get('numero_protocolo') or None,
        dados.get('responsavel') or None,
        dados.get('observacoes') or None,
        dados.get('arquivo_pdf') or None,
        dados.get('arquivo_original') or None,
    )


def inserir_analise(dados):
    try:
        resultado = executar_query(_SQL_INSERIR_ANALISE, _valores_analise(dados),
                                   fetch_one=True, dict_cursor=True)
        return resultado['id'] if resultado else None
    except Exception as e:
        logger.error(f"analises.inserir_analise: {e}")
        return None


NAMESPACE_TRAVA_LOTE = 7201  # separa estas travas de outras travas consultivas do banco


@contextmanager
def trava_lote(lote_token):
    """Trava exclusiva do lote no PostgreSQL (não bloqueia: devolve False se outro tem a trava).

    A confirmação segura a trava do começo ao fim; a recuperação só mexe no lote se
    conseguir a mesma trava. Se o processo da confirmação cair, a conexão fecha e a
    trava é liberada pelo banco, então a recuperação pode agir sem prazo arbitrário."""
    conn = None
    obtida = False
    try:
        conn = conexao_dedicada()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s, hashtext(%s)) AS ok",
                        (NAMESPACE_TRAVA_LOTE, lote_token))
            obtida = bool(cur.fetchone()[0])
        yield obtida
    finally:
        if conn is not None:
            try:
                if obtida:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s, hashtext(%s))",
                                    (NAMESPACE_TRAVA_LOTE, lote_token))
            except Exception as e:
                logger.error(f"analises.trava_lote (liberar): {e}")
            finally:
                conn.close()


class LoteJaGravado(Exception):
    """O lote de laudos já está no banco (confirmação repetida ou interrompida)."""
    def __init__(self, ids):
        super().__init__('Lote já gravado.')
        self.ids = ids


def ids_do_lote(lote_token):
    """Análises gravadas por um lote de upload (o banco é a fonte de verdade do lote)."""
    if not lote_token:
        return []
    try:
        linhas = executar_query("SELECT id FROM analises WHERE lote_token = %s ORDER BY lote_indice, id",
                                (lote_token,), fetch_all=True, dict_cursor=True) or []
        return [r['id'] for r in linhas]
    except Exception as e:
        logger.error(f"analises.ids_do_lote: {e}")
        raise


def inserir_analises_lote(lista_dados, lote_token=None):
    """Grava vários laudos em uma única transação; rollback se qualquer um falhar.
    Com lote_token, cada análise leva o identificador do lote; um lote já gravado
    não é gravado de novo (índice único garante isso também sob concorrência)."""
    def operacao(cur):
        if lote_token:
            cur.execute("SELECT id FROM analises WHERE lote_token = %s ORDER BY lote_indice", (lote_token,))
            existentes = [r['id'] for r in cur.fetchall()]
            if existentes:
                raise LoteJaGravado(existentes)
        ids = []
        for indice, dados in enumerate(lista_dados):
            cur.execute(_SQL_INSERIR_ANALISE, _valores_analise(dados))
            novo_id = cur.fetchone()['id']
            if lote_token:
                cur.execute("UPDATE analises SET lote_token = %s, lote_indice = %s WHERE id = %s",
                            (lote_token, indice, novo_id))
            ids.append(novo_id)
        return ids

    try:
        return executar_transacao(operacao)
    except LoteJaGravado:
        raise
    except Exception as e:
        if lote_token and 'ux_analises_lote' in str(e):
            raise LoteJaGravado(ids_do_lote(lote_token))
        logger.error(f"analises.inserir_analises_lote: {e}")
        raise

def atualizar_data_resultado(analise_id):
    """Atualiza a data_resultado para a data atual quando resultados são inseridos"""
    query = "UPDATE analises SET data_resultado = CURRENT_DATE WHERE id = %s AND data_resultado IS NULL"
    try:
        executar_query(query, (analise_id,))
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar data_resultado: {e}")
        return False 

def excluir_analise(id):
    """Exclui uma análise (resultados serão excluídos por CASCADE)"""
    try:
        # Exclusão lógica (mantém histórico mas não aparece nas listas)
        executar_query("UPDATE analises SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Análise excluída com sucesso"
    except Exception as e:
        logger.error(f"Erro ao excluir análise: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_laboratorio(id):
    """Exclui um laboratório (verifica se não está em uso)"""
    try:
        # Verificar se há análises vinculadas
        r = executar_query("SELECT COUNT(*) AS total FROM analises WHERE laboratorio_id = %s AND ativo = TRUE", (id,), fetch_one=True, dict_cursor=True)
        count = r['total']
        if count > 0:
            return False, f"Não é possível excluir: laboratório vinculado a {count} análise(s) ativa(s)"
        
        # Exclusão lógica
        executar_query("UPDATE laboratorios SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Laboratório excluído com sucesso"
    except Exception as e:
        logger.error(f"Erro ao excluir laboratório: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_parametro(id):
    """Exclui um parâmetro de análise (verifica se não está em uso)"""
    try:
        # Verificar se há resultados vinculados
        r = executar_query("SELECT COUNT(*) AS total FROM resultados_analise WHERE parametro_id = %s", (id,), fetch_one=True, dict_cursor=True)
        count = r['total']
        if count > 0:
            return False, f"Não é possível excluir: parâmetro usado em {count} resultado(s)"
        
        executar_query("UPDATE parametros_analise SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Parâmetro excluído com sucesso"
    except Exception as e:
        logger.error(f"Erro ao excluir parâmetro: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_tipo_analise(id):
    """Exclui um tipo de análise (verifica se não está em uso)"""
    try:
        # Verificar se há parâmetros vinculados
        r = executar_query("SELECT COUNT(*) AS total FROM parametros_analise WHERE tipo_analise_id = %s AND ativo = TRUE", (id,), fetch_one=True, dict_cursor=True)
        count_param = r['total']
        if count_param > 0:
            return False, f"Não é possível excluir: tipo possui {count_param} parâmetro(s) ativo(s)"
        
        # Verificar se há análises vinculadas
        r = executar_query("SELECT COUNT(*) AS total FROM analises WHERE tipo_analise_id = %s AND ativo = TRUE", (id,), fetch_one=True, dict_cursor=True)
        count_analise = r['total']
        if count_analise > 0:
            return False, f"Não é possível excluir: tipo usado em {count_analise} análise(s)"
        
        executar_query("UPDATE tipos_analise SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Tipo de análise excluído com sucesso"
    except Exception as e:
        logger.error(f"Erro ao excluir tipo de análise: {e}")
        return False, f"Erro ao excluir: {str(e)}"
    
    
def buscar_laboratorio_por_id(id):
    query = "SELECT id, nome, responsavel, telefone, email, endereco, observacoes FROM laboratorios WHERE id = %s"
    try:
        r = executar_query(query, (id,), fetch_one=True, dict_cursor=True)
        if r:
            return {
                'id': r['id'],
                'nome': r['nome'],
                'responsavel': r['responsavel'],
                'telefone': r['telefone'],
                'email': r['email'],
                'endereco': r['endereco'],
                'observacoes': r['observacoes']
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar laboratório: {e}")
        return None

def atualizar_laboratorio(id, dados):
    query = """
    UPDATE laboratorios 
    SET nome=%s, responsavel=%s, telefone=%s, email=%s, endereco=%s, observacoes=%s
    WHERE id=%s
    """
    try:
        executar_query(query,
            (dados['nome'], dados['responsavel'], dados['telefone'],
             dados['email'], dados['endereco'], dados['observacoes'], id))
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar laboratório: {e}")
        return False

