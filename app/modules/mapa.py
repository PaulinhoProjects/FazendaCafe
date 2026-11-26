"""
Módulo do Mapa da Fazenda.

Lê os talhões com GPS e importa camadas KML/KMZ exportadas do Google Earth.
Os elementos importados ficam no banco (camada anterior é desativada, nunca excluída).
"""

import io
import json
import logging
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao

logger = logging.getLogger(__name__)

MAX_ELEMENTOS = 1000
TAMANHO_MAXIMO = 12 * 1024 * 1024


def criar_tabela_mapa():
    """Cria a tabela que guarda a camada KML ativa."""
    query = """
    CREATE TABLE IF NOT EXISTS mapas_importados (
        id SERIAL PRIMARY KEY,
        nome_arquivo VARCHAR(255) NOT NULL,
        conteudo TEXT NOT NULL,
        total_elementos INTEGER DEFAULT 0,
        data_importacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ativo BOOLEAN DEFAULT TRUE
    )
    """
    try:
        executar_query(query)
        return True
    except Exception as e:
        logger.error(f"mapa.criar_tabela_mapa: {e}")
        return False


def _nome_local(tag):
    return tag.split('}')[-1]


def _texto(elemento, nome):
    for filho in elemento.iter():
        if _nome_local(filho.tag) == nome:
            return (filho.text or '').strip()
    return ''


def _coordenadas(texto):
    """Converte 'lon,lat,alt' do KML para [lat, lng]."""
    pontos = []
    for bloco in (texto or '').split():
        partes = bloco.split(',')
        if len(partes) < 2:
            continue
        try:
            lng = float(partes[0])
            lat = float(partes[1])
        except (TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            pontos.append([round(lat, 7), round(lng, 7)])
    return pontos


def _coordenadas_exteriores(poligono):
    """Pega apenas o contorno externo, ignorando buracos do polígono."""
    for filho in poligono.iter():
        if _nome_local(filho.tag) == 'outerBoundaryIs':
            texto = _texto(filho, 'coordinates')
            if texto:
                return _coordenadas(texto)
    return _coordenadas(_texto(poligono, 'coordinates'))


def _elementos_placemark(placemark):
    nome = _texto(placemark, 'name') or 'Sem nome'
    descricao = _texto(placemark, 'description')
    elementos = []

    for filho in placemark.iter():
        tipo = _nome_local(filho.tag)
        if tipo == 'Polygon':
            pontos = _coordenadas_exteriores(filho)
            if len(pontos) >= 3:
                elementos.append({
                    'tipo': 'area', 'nome': nome,
                    'descricao': descricao, 'coordenadas': pontos
                })
        elif tipo == 'LineString':
            pontos = _coordenadas(_texto(filho, 'coordinates'))
            if len(pontos) >= 2:
                elementos.append({
                    'tipo': 'linha', 'nome': nome,
                    'descricao': descricao, 'coordenadas': pontos
                })
        elif tipo == 'Point':
            pontos = _coordenadas(_texto(filho, 'coordinates'))
            if pontos:
                elementos.append({
                    'tipo': 'ponto', 'nome': nome,
                    'descricao': descricao, 'coordenadas': pontos[0]
                })
    return elementos


def interpretar_kml(nome_arquivo, conteudo):
    """Extrai áreas, linhas e pontos de um arquivo KML ou KMZ."""
    extensao = nome_arquivo.lower().rsplit('.', 1)[-1] if '.' in nome_arquivo else ''
    if extensao not in ('kml', 'kmz'):
        raise ValueError('Envie um arquivo .kml ou .kmz')

    if len(conteudo) > TAMANHO_MAXIMO:
        raise ValueError('Arquivo muito grande (limite: 12 MB)')

    if extensao == 'kmz':
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
                candidatos = [n for n in pacote.namelist() if n.lower().endswith('.kml')]
                if not candidatos:
                    raise ValueError('O KMZ não contém arquivo KML')
                principal = next(
                    (n for n in candidatos if n.lower().endswith('doc.kml')), candidatos[0]
                )
                conteudo = pacote.read(principal)
        except zipfile.BadZipFile as e:
            raise ValueError(f'KMZ inválido: {e}')

    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise ValueError(f'KML inválido: {e}')

    elementos = []
    for filho in raiz.iter():
        if _nome_local(filho.tag) != 'Placemark':
            continue
        elementos.extend(_elementos_placemark(filho))
        if len(elementos) >= MAX_ELEMENTOS:
            break

    if not elementos:
        raise ValueError('Nenhum ponto, linha ou área encontrado no arquivo')
    return elementos[:MAX_ELEMENTOS]


def obter_mapa_ativo():
    """Retorna os dados da camada KML ativa."""
    query = """
    SELECT id, nome_arquivo, conteudo, total_elementos, data_importacao
    FROM mapas_importados
    WHERE ativo = TRUE
    ORDER BY id DESC
    LIMIT 1
    """
    try:
        registro = executar_query(query, fetch_one=True, dict_cursor=True)
        if not registro:
            return None
        data = registro['data_importacao']
        return {
            'id': registro['id'],
            'nome_arquivo': registro['nome_arquivo'],
            'conteudo': registro['conteudo'],
            'total_elementos': registro['total_elementos'],
            'data_importacao': data.strftime('%d/%m/%Y %H:%M') if hasattr(data, 'strftime') else str(data or ''),
        }
    except Exception as e:
        logger.error(f"mapa.obter_mapa_ativo: {e}")
        return None


def salvar_mapa(nome_arquivo, conteudo):
    """Importa uma nova camada, desativando a anterior na mesma transação."""
    elementos = interpretar_kml(nome_arquivo, conteudo)
    conteudo_json = json.dumps(elementos, ensure_ascii=False)

    def operacao(cursor):
        cursor.execute("UPDATE mapas_importados SET ativo = FALSE WHERE ativo = TRUE")
        cursor.execute("""
            INSERT INTO mapas_importados (nome_arquivo, conteudo, total_elementos, ativo)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id
        """, (nome_arquivo, conteudo_json, len(elementos)))
        return cursor.fetchone()['id']

    try:
        executar_transacao(operacao)
        return True, f'{len(elementos)} elementos importados', len(elementos)
    except Exception as e:
        logger.error(f"mapa.salvar_mapa: {e}")
        return False, str(e), 0


def desativar_mapa():
    """Remove a camada da visualização sem apagar o histórico."""
    try:
        executar_query("UPDATE mapas_importados SET ativo = FALSE WHERE ativo = TRUE")
        return True, 'Camadas removidas da visualização.'
    except Exception as e:
        logger.error(f"mapa.desativar_mapa: {e}")
        return False, str(e)


def obter_dados_mapa():
    """Monta os dados usados pelo mapa: talhões com GPS + camada importada."""
    talhoes = []
    query = """
    SELECT id, nome, area_hectares, variedade_cafe, latitude, longitude
    FROM talhoes
    WHERE ativo = TRUE AND latitude IS NOT NULL AND longitude IS NOT NULL
    ORDER BY nome
    """
    try:
        registros = executar_query(query, fetch_all=True, dict_cursor=True)
        for registro in registros or []:
            talhoes.append({
                'id': registro['id'],
                'nome': registro['nome'],
                'area': float(registro['area_hectares'] or 0),
                'variedade': registro['variedade_cafe'] or '',
                'lat': float(registro['latitude']),
                'lng': float(registro['longitude']),
            })
    except Exception as e:
        logger.error(f"mapa.obter_dados_mapa: {e}")

    ativo = obter_mapa_ativo()
    elementos = []
    if ativo:
        try:
            elementos = json.loads(ativo.pop('conteudo') or '[]')
        except (TypeError, ValueError) as e:
            logger.error(f"mapa.obter_dados_mapa (JSON): {e}")
            elementos = []

    return {'talhoes': talhoes, 'elementos': elementos, 'importacao': ativo}
