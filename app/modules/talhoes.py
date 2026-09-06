"""
Módulo de Talhões — AgroCafé
Gerencia CRUD de talhões com GPS, fotos e cálculo de pés de café.
"""
import sys
import os
import re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query

def criar_tabela_talhoes():
    """Cria a tabela de talhões se não existir."""
    query = """
    CREATE TABLE IF NOT EXISTS talhoes (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        area_hectares NUMERIC(10,2) NOT NULL,
        data_plantio DATE,
        variedade_cafe VARCHAR(100),
        altitude_media NUMERIC(10,2),
        observacoes TEXT,
        data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo BOOLEAN DEFAULT TRUE,
        espacamento VARCHAR(50),
        produtor_id INTEGER,
        latitude NUMERIC(10,7),
        longitude NUMERIC(10,7),
        foto_url TEXT
    )
    """
    executar_query(query)

def calcular_pes_cafe(area, espacamento):
    """Calcula pés de café baseado na área e espaçamento."""
    if not area or area <= 0:
        return 0, ""
    if not espacamento:
        return 0, ""
    try:
        numeros = re.findall(r'(\d+[.,]?\d*)', str(espacamento))
        if len(numeros) < 2:
            return 0, ""
        entre_linhas = float(numeros[0].replace(',', '.'))
        entre_plantas = float(numeros[1].replace(',', '.'))
        if entre_linhas <= 0 or entre_plantas <= 0:
            return 0, ""
        plantas_por_ha = 10000.0 / (entre_linhas * entre_plantas)
        total_plantas = int(round(plantas_por_ha * float(area)))
        formula = f"{plantas_por_ha:.0f} pl/ha x {area:.2f} ha = {total_plantas} pés"
        return total_plantas, formula
    except Exception:
        return 0, ""

def listar_talhoes(ativos=True):
    """Retorna lista de talhões com cálculo de pés de café."""
    query = """
    SELECT
        id, nome, area_hectares, data_plantio, variedade_cafe,
        altitude_media, observacoes, data_cadastro, ativo,
        espacamento, produtor_id, latitude, longitude, foto_url
    FROM talhoes
    WHERE ativo = TRUE
    ORDER BY id
    """
    try:
        resultado = executar_query(query, fetch_all=True)
        if not resultado:
            return []
        lista = []
        for r in resultado:
            area = float(r[2]) if r[2] else 0.0
            espacamento = r[9] if r[9] else None
            pes_cafe, formula = calcular_pes_cafe(area, espacamento)
            lista.append({
                'id': r[0],
                'nome': r[1],
                'area': area,
                'area_hectares': area,
                'data_plantio': r[3],
                'variedade': r[4] if r[4] else 'Não informada',
                'variedade_cafe': r[4] if r[4] else 'Não informada',
                'altitude': float(r[5]) if r[5] else None,
                'altitude_media': float(r[5]) if r[5] else None,
                'observacoes': r[6],
                'data_cadastro': r[7],
                'ativo': r[8],
                'espacamento': espacamento,
                'produtor_id': r[10],
                'latitude': float(r[11]) if r[11] else None,
                'longitude': float(r[12]) if r[12] else None,
                'foto_url': r[13] if r[13] else None,
                'pes_cafe': pes_cafe,
                'formula_pes': formula
            })
        return lista
    except Exception as e:
        print(f"Erro ao listar talhões: {e}")
        return []

def buscar_talhao_por_id(talhao_id):
    """Busca um talhão pelo ID."""
    query = """
    SELECT
        id, nome, area_hectares, data_plantio, variedade_cafe,
        altitude_media, observacoes, data_cadastro, ativo,
        espacamento, produtor_id, latitude, longitude, foto_url
    FROM talhoes
    WHERE id = %s
    """
    try:
        r = executar_query(query, (talhao_id,), fetch_one=True)
        if not r:
            return None
        area = float(r[2]) if r[2] else 0.0
        espacamento = r[9] if r[9] else None
        pes_cafe, formula = calcular_pes_cafe(area, espacamento)
        return {
            'id': r[0],
            'nome': r[1],
            'area': area,
            'area_hectares': area,
            'data_plantio': r[3],
            'variedade': r[4] if r[4] else 'Não informada',
            'variedade_cafe': r[4] if r[4] else 'Não informada',
            'altitude': float(r[5]) if r[5] else None,
            'altitude_media': float(r[5]) if r[5] else None,
            'observacoes': r[6],
            'data_cadastro': r[7],
            'ativo': r[8],
            'espacamento': espacamento,
            'produtor_id': r[10],
            'latitude': float(r[11]) if r[11] else None,
            'longitude': float(r[12]) if r[12] else None,
            'foto_url': r[13] if r[13] else None,
            'pes_cafe': pes_cafe,
            'formula_pes': formula
        }
    except Exception as e:
        print(f"Erro ao buscar talhão: {e}")
        return None

def inserir_talhao(dados):
    """Insere um novo talhão."""
    if isinstance(dados, dict):
        nome = dados.get('nome')
        area = dados.get('area') or dados.get('area_hectares')
        data_plantio = dados.get('data_plantio') or None
        variedade = dados.get('variedade') or dados.get('variedade_cafe') or ''
        altitude = dados.get('altitude') or dados.get('altitude_media') or None
        observacoes = dados.get('observacoes') or ''
        espacamento = dados.get('espacamento') or None
        latitude = dados.get('latitude') or None
        longitude = dados.get('longitude') or None
        foto_url = dados.get('foto_url') or None
    else:
        return None

    query = """
    INSERT INTO talhoes (nome, area_hectares, data_plantio, variedade_cafe, altitude_media, observacoes, espacamento, latitude, longitude, foto_url)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    try:
        resultado = executar_query(query, (nome, area, data_plantio, variedade, altitude, observacoes, espacamento, latitude, longitude, foto_url), fetch_one=True)
        return resultado[0] if resultado else None
    except Exception as e:
        print(f"Erro ao inserir talhão: {e}")
        return None

def atualizar_talhao(talhao_id, dados):
    """Atualiza um talhão existente."""
    if isinstance(dados, dict):
        nome = dados.get('nome')
        area = dados.get('area') or dados.get('area_hectares')
        data_plantio = dados.get('data_plantio') or None
        variedade = dados.get('variedade') or dados.get('variedade_cafe') or ''
        altitude = dados.get('altitude') or dados.get('altitude_media') or None
        observacoes = dados.get('observacoes') or ''
        espacamento = dados.get('espacamento') or None
        latitude = dados.get('latitude') or None
        longitude = dados.get('longitude') or None
        foto_url = dados.get('foto_url') or None
    else:
        return False

    query = """
    UPDATE talhoes SET
        nome = %s, area_hectares = %s, data_plantio = %s,
        variedade_cafe = %s, altitude_media = %s, observacoes = %s,
        espacamento = %s, latitude = %s, longitude = %s, foto_url = %s
    WHERE id = %s
    """
    try:
        executar_query(query, (nome, area, data_plantio, variedade, altitude, observacoes, espacamento, latitude, longitude, foto_url, talhao_id))
        return True
    except Exception as e:
        print(f"Erro ao atualizar talhão: {e}")
        return False

def excluir_talhao(talhao_id):
    """Desativa um talhão (exclusão lógica)."""
    query = "UPDATE talhoes SET ativo = FALSE WHERE id = %s"
    try:
        executar_query(query, (talhao_id,))
        return True
    except Exception as e:
        print(f"Erro ao excluir talhão: {e}")
        return False

def get_historico_talhao(talhao_id):
    """Retorna histórico de atividades de um talhão."""
    historico = []

    # Pulverizações
    try:
        query = """
        SELECT data_aplicacao, 'Pulverização' as tipo, r.nome as detalhe, ap.responsavel
        FROM aplicacoes_pulverizacao ap
        LEFT JOIN receitas r ON r.id = ap.receita_id
        WHERE ap.talhao_id = %s
        ORDER BY data_aplicacao DESC LIMIT 20
        """
        resultado = executar_query(query, (talhao_id,), fetch_all=True)
        for r in resultado:
            historico.append({
                'data': r[0], 'tipo': r[1], 'detalhe': r[2] or 'Sem receita', 'responsavel': r[3] or '—'
            })
    except Exception:
        pass

    # Análises
    try:
        query = """
        SELECT data_coleta, 'Análise' as tipo, tp.nome as detalhe, '—' as responsavel
        FROM analises a
        JOIN tipos_analise tp ON tp.id = a.tipo_analise_id
        WHERE a.talhao_id = %s AND a.ativo = TRUE
        ORDER BY data_coleta DESC LIMIT 20
        """
        resultado = executar_query(query, (talhao_id,), fetch_all=True)
        for r in resultado:
            historico.append({
                'data': r[0], 'tipo': r[1], 'detalhe': r[2], 'responsavel': r[3]
            })
    except Exception:
        pass

    # Manejos do mato
    try:
        query = """
        SELECT data_manejo, 'Manejo de Mato' as tipo, tipo_manejo as detalhe, responsavel
        FROM manejos_mato
        WHERE talhao_id = %s
        ORDER BY data_manejo DESC LIMIT 20
        """
        resultado = executar_query(query, (talhao_id,), fetch_all=True)
        for r in resultado:
            historico.append({
                'data': r[0], 'tipo': r[1], 'detalhe': r[2], 'responsavel': r[3] or '—'
            })
    except Exception:
        pass

    # Ordenar por data
    historico.sort(key=lambda x: x['data'] if x['data'] else None, reverse=True)
    return historico[:30]