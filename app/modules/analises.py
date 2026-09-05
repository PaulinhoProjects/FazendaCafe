"""
Módulo de Análises de Solo e Foliares
Gerencia laboratórios, análises e resultados
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query
from datetime import datetime

# =====================================================
# FUNÇÕES PARA TIPOS DE ANÁLISE
# =====================================================

def listar_tipos_analise():
    query = "SELECT id, nome FROM tipos_analise WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True)
        return [{'id': r[0], 'nome': r[1]} for r in resultado] if resultado else []
    except Exception as e:
        print(f"Erro ao listar tipos: {e}")
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
        resultado = executar_query(query, (tipo_analise_id,), fetch_all=True)
        return [{'id': r[0], 'nome': r[1], 'unidade': r[2]} for r in resultado] if resultado else []
    except Exception as e:
        print(f"Erro ao listar parâmetros: {e}")
        return []

# =====================================================
# FUNÇÕES PARA LABORATÓRIOS
# =====================================================

def listar_laboratorios():
    """Retorna lista de laboratórios ativos"""
    query = "SELECT id, nome, responsavel, telefone, email, endereco, observacoes FROM laboratorios WHERE ativo = TRUE ORDER BY nome"
    try:
        resultado = executar_query(query, fetch_all=True)
        
        if not resultado:
            return []
        
        laboratorios = []
        for r in resultado:
            laboratorios.append({
                'id': r[0],
                'nome': r[1],
                'responsavel': r[2],
                'telefone': r[3],
                'email': r[4],
                'endereco': r[5],
                'observacoes': r[6]
            })
        return laboratorios
        
    except Exception as e:
        print(f"Erro ao listar laboratórios: {e}")
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
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir laboratório: {e}")
        return None

# =====================================================
# FUNÇÕES PARA ANÁLISES
# =====================================================

def listar_analises(talhao_id=None):
    """Lista análises, opcionalmente filtradas por talhão"""
    if talhao_id:
        query = """
        SELECT a.id, a.talhao_id, t.nome as talhao_nome,
               a.tipo_analise_id, tp.nome as tipo_nome,
               a.laboratorio_id, l.nome as lab_nome,
               a.data_coleta, a.data_resultado, a.numero_protocolo,
               a.responsavel_coleta, a.observacoes
        FROM analises a
        JOIN talhoes t ON t.id = a.talhao_id
        JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
        LEFT JOIN laboratorios l ON l.id = a.laboratorio_id
        WHERE a.talhao_id = %s AND a.ativo = TRUE
        ORDER BY a.data_coleta DESC
        """
        params = (talhao_id,)
    else:
        query = """
        SELECT a.id, a.talhao_id, t.nome as talhao_nome,
               a.tipo_analise_id, tp.nome as tipo_nome,
               a.laboratorio_id, l.nome as lab_nome,
               a.data_coleta, a.data_resultado, a.numero_protocolo,
               a.responsavel_coleta, a.observacoes
        FROM analises a
        JOIN talhoes t ON t.id = a.talhao_id
        JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
        LEFT JOIN laboratorios l ON l.id = a.laboratorio_id
        WHERE a.ativo = TRUE
        ORDER BY a.data_coleta DESC
        LIMIT 100
        """
        params = None
    
    try:
        resultado = executar_query(query, params, fetch_all=True)
        if not resultado:
            return []  # <-- IMPORTANTE: retorna lista vazia se não houver resultados
        
        analises = []
        for r in resultado:
            analises.append({
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'tipo_id': r[3],
                'tipo_nome': r[4],
                'laboratorio_id': r[5],
                'laboratorio_nome': r[6],
                'data_coleta': r[7],
                'data_resultado': r[8],
                'numero_protocolo': r[9],
                'responsavel': r[10],
                'observacoes': r[11]
            })
        return analises
    except Exception as e:
        print(f"Erro ao listar análises: {e}")
        return []  # <-- IMPORTANTE: sempre retorna lista vazia em caso de erro

def buscar_analise_por_id(id):
    query = """
    SELECT a.id, a.talhao_id, t.nome as talhao_nome,
           a.tipo_analise_id, tp.nome as tipo_nome,
           a.laboratorio_id, l.nome as lab_nome,
           a.data_coleta, a.data_resultado, a.numero_protocolo,
           a.responsavel_coleta, a.observacoes, a.arquivo_pdf
    FROM analises a
    JOIN talhoes t ON t.id = a.talhao_id
    JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
    LEFT JOIN laboratorios l ON l.id = a.laboratorio_id
    WHERE a.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'tipo_id': r[3],
                'tipo_nome': r[4],
                'laboratorio_id': r[5],
                'laboratorio_nome': r[6],
                'data_coleta': r[7],
                'data_resultado': r[8],
                'numero_protocolo': r[9],
                'responsavel': r[10],
                'observacoes': r[11],
                'arquivo_pdf': r[12]  # <-- NOVO
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar análise: {e}")
        return None

def inserir_analise(dados):
    query = """
    INSERT INTO analises 
        (talhao_id, tipo_analise_id, laboratorio_id, data_coleta, 
         data_resultado, numero_protocolo, responsavel_coleta, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['tipo_id'], dados.get('laboratorio_id'),
             dados['data_coleta'], dados.get('data_resultado'),
             dados.get('numero_protocolo'), dados.get('responsavel'),
             dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir análise: {e}")
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
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir resultado: {e}")
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
        resultado = executar_query(query, (analise_id,), fetch_all=True)
        resultados = []
        for r in resultado:
            resultados.append({
                'id': r[0],
                'parametro': r[1],
                'unidade': r[2],
                'valor': float(r[3]) if r[3] else None,
                'interpretacao': r[4],
                'observacoes': r[5]
            })
        return resultados
    except Exception as e:
        print(f"Erro ao listar resultados: {e}")
        return []
    
def inserir_analise(dados):
    query = """
    INSERT INTO analises 
        (talhao_id, tipo_analise_id, laboratorio_id, data_coleta, 
         data_resultado, numero_protocolo, responsavel_coleta, observacoes, arquivo_pdf)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['tipo_id'], dados.get('laboratorio_id'),
             dados['data_coleta'], dados.get('data_resultado'),
             dados.get('numero_protocolo'), dados.get('responsavel'),
             dados.get('observacoes'), dados.get('arquivo_pdf')),  # <-- NOVO
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir análise: {e}")
        return None
    
def atualizar_data_resultado(analise_id):
    """Atualiza a data_resultado para a data atual quando resultados são inseridos"""
    query = "UPDATE analises SET data_resultado = CURRENT_DATE WHERE id = %s AND data_resultado IS NULL"
    try:
        executar_query(query, (analise_id,))
        return True
    except Exception as e:
        print(f"Erro ao atualizar data_resultado: {e}")
        return False 

def excluir_analise(id):
    """Exclui uma análise (resultados serão excluídos por CASCADE)"""
    try:
        # Exclusão lógica (mantém histórico mas não aparece nas listas)
        executar_query("UPDATE analises SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Análise excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir análise: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_laboratorio(id):
    """Exclui um laboratório (verifica se não está em uso)"""
    try:
        # Verificar se há análises vinculadas
        count = executar_query("SELECT COUNT(*) FROM analises WHERE laboratorio_id = %s AND ativo = TRUE", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: laboratório vinculado a {count} análise(s) ativa(s)"
        
        # Exclusão lógica
        executar_query("UPDATE laboratorios SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Laboratório excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir laboratório: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_parametro(id):
    """Exclui um parâmetro de análise (verifica se não está em uso)"""
    try:
        # Verificar se há resultados vinculados
        count = executar_query("SELECT COUNT(*) FROM resultados_analise WHERE parametro_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: parâmetro usado em {count} resultado(s)"
        
        executar_query("UPDATE parametros_analise SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Parâmetro excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir parâmetro: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_tipo_analise(id):
    """Exclui um tipo de análise (verifica se não está em uso)"""
    try:
        # Verificar se há parâmetros vinculados
        count_param = executar_query("SELECT COUNT(*) FROM parametros_analise WHERE tipo_analise_id = %s AND ativo = TRUE", (id,), fetch_one=True)[0]
        if count_param > 0:
            return False, f"Não é possível excluir: tipo possui {count_param} parâmetro(s) ativo(s)"
        
        # Verificar se há análises vinculadas
        count_analise = executar_query("SELECT COUNT(*) FROM analises WHERE tipo_analise_id = %s AND ativo = TRUE", (id,), fetch_one=True)[0]
        if count_analise > 0:
            return False, f"Não é possível excluir: tipo usado em {count_analise} análise(s)"
        
        executar_query("UPDATE tipos_analise SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Tipo de análise excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir tipo de análise: {e}")
        return False, f"Erro ao excluir: {str(e)}"
    
    
def buscar_laboratorio_por_id(id):
    query = "SELECT id, nome, responsavel, telefone, email, endereco, observacoes FROM laboratorios WHERE id = %s"
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'nome': r[1],
                'responsavel': r[2],
                'telefone': r[3],
                'email': r[4],
                'endereco': r[5],
                'observacoes': r[6]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar laboratório: {e}")
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
        print(f"Erro ao atualizar laboratório: {e}")
        return False

