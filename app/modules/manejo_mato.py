"""
Módulo de Manejo do Mato
Gerencia registros de capinas, herbicidas e roçadas
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

def listar_manejos(talhao_id=None):
    """Lista manejos, opcionalmente filtrados por talhão"""
    if talhao_id:
        query = """
        SELECT m.id, m.talhao_id, t.nome as talhao_nome,
               m.data_manejo, m.tipo_manejo, m.produtos,
               m.dosagem, m.responsavel, m.observacoes
        FROM manejos_mato m
        JOIN talhoes t ON t.id = m.talhao_id
        WHERE m.talhao_id = %s
        ORDER BY m.data_manejo DESC
        """
        params = (talhao_id,)
    else:
        query = """
        SELECT m.id, m.talhao_id, t.nome as talhao_nome,
               m.data_manejo, m.tipo_manejo, m.produtos,
               m.dosagem, m.responsavel, m.observacoes
        FROM manejos_mato m
        JOIN talhoes t ON t.id = m.talhao_id
        ORDER BY m.data_manejo DESC
        LIMIT 100
        """
        params = None

    try:
        resultado = executar_query(query, params, fetch_all=True)
        manejos = []
        for r in resultado:
            manejos.append({
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'data_manejo': r[3],
                'tipo_manejo': r[4],
                'produtos': r[5],
                'dosagem': r[6],
                'responsavel': r[7],
                'observacoes': r[8]
            })
        return manejos
    except Exception as e:
        print(f"Erro ao listar manejos: {e}")
        return []

def buscar_manejo_por_id(id):
    """Retorna um manejo específico"""
    query = """
    SELECT m.id, m.talhao_id, t.nome as talhao_nome,
           m.data_manejo, m.tipo_manejo, m.produtos,
           m.dosagem, m.responsavel, m.observacoes
    FROM manejos_mato m
    JOIN talhoes t ON t.id = m.talhao_id
    WHERE m.id = %s
    """
    try:
        r = executar_query(query, (id,), fetch_one=True)
        if r:
            return {
                'id': r[0],
                'talhao_id': r[1],
                'talhao_nome': r[2],
                'data_manejo': r[3],
                'tipo_manejo': r[4],
                'produtos': r[5],
                'dosagem': r[6],
                'responsavel': r[7],
                'observacoes': r[8]
            }
        return None
    except Exception as e:
        print(f"Erro ao buscar manejo: {e}")
        return None

def inserir_manejo(dados):
    """Insere um novo registro de manejo"""
    query = """
    INSERT INTO manejos_mato
        (talhao_id, data_manejo, tipo_manejo, produtos, dosagem, responsavel, observacoes)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(query,
            (dados['talhao_id'], dados['data_manejo'], dados['tipo_manejo'],
             dados.get('produtos'), dados.get('dosagem'),
             dados.get('responsavel'), dados.get('observacoes')),
            fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir manejo: {e}")
        return None

def atualizar_manejo(id, dados):
    """Atualiza um manejo existente"""
    query = """
    UPDATE manejos_mato
    SET talhao_id=%s, data_manejo=%s, tipo_manejo=%s,
        produtos=%s, dosagem=%s, responsavel=%s, observacoes=%s
    WHERE id=%s
    """
    try:
        executar_query(query,
            (dados['talhao_id'], dados['data_manejo'], dados['tipo_manejo'],
             dados.get('produtos'), dados.get('dosagem'),
             dados.get('responsavel'), dados.get('observacoes'),
             id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar manejo: {e}")
        return False
    
def excluir_manejo(id):
    """Exclui um manejo do mato"""
    try:
        executar_query("DELETE FROM manejos_mato WHERE id = %s", (id,))
        return True, "Manejo excluído com sucesso"
    except Exception as e:
        print(f"Erro ao excluir manejo: {e}")
        return False, f"Erro ao excluir: {str(e)}"

def excluir_planta(id):
    """Exclui uma planta daninha (verifica se não está em uso)"""
    try:
        # Verificar se há ocorrências vinculadas
        count = executar_query("SELECT COUNT(*) FROM ocorrencias_plantas WHERE planta_id = %s", (id,), fetch_one=True)[0]
        if count > 0:
            return False, f"Não é possível excluir: planta registrada em {count} ocorrência(s)"
        
        executar_query("UPDATE plantas_daninhas SET ativo = FALSE WHERE id = %s", (id,))
        return True, "Planta excluída com sucesso"
    except Exception as e:
        print(f"Erro ao excluir planta: {e}")
        return False, f"Erro ao excluir: {str(e)}"