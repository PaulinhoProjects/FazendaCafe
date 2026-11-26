"""
Cotações de café e dólar de fontes públicas, sem login e sem chave de API.

Fontes:
- Cooxupé / Hub do Café: API JSON pública /api/cotacao-cafe
- Coopercam: tabela diária pública de café físico (HTML)
- Cocatrel: API JSON pública de café físico (COC 01 a 16)
- Banco Central do Brasil: PTAX (dados abertos, OData)
- AwesomeAPI: dólar comercial USD/BRL
- Climatempo: previsão pública (incluído apenas no monitor de integrações)
- ANP: preço semanal do Diesel S10 (incluído apenas no monitor de integrações)

Atualização preguiçosa com cache de 30 minutos (COTACOES_CACHE_MINUTOS) e botão
para forçar no painel admin. Cada coleta grava um snapshot no banco para histórico.
"""
import logging
import os
import re
import sys
from datetime import datetime, timedelta

import requests

from app.modules import clima, maquinario

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao, get_config

logger = logging.getLogger(__name__)

COOXUPE_URL = "https://hubdocafe.cooxupe.com.br/api/cotacao-cafe"
BCB_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
           "CotacaoDolarPeriodo(dataInicial=@d1,dataFinalCotacao=@d2)")
AWESOME_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
COOPERCAM_URL = "https://coopercam.com.br/cotacoes/"
COCATREL_URL = "https://portal.cocatrel.com.br/DPmercadoCafe.aspx"
COCATREL_API = "https://portal.cocatrel.com.br/api/v1/loadpagina/cafe/mercado"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 15
LIBRAS_POR_SACA = 132.27736  # 60 kg (saca de café) convertidos para libras
ORDEM_COOPERCAM = [
    'Gourmet', 'APM', 'Duro Limpo', 'Duro Riado', 'Duro Riado Rio', 'Rio de Pano',
]
ORDEM_COCATREL = [f'COC {i:02d}' for i in range(1, 17)]

try:
    CACHE_MINUTOS = max(1, int(os.getenv("COTACOES_CACHE_MINUTOS", "30")))
except (TypeError, ValueError):
    CACHE_MINUTOS = 30

_DADOS = {"valor": None, "timestamp": None}
_SAUDE = {"valor": None, "timestamp": None}
SAUDE_CACHE_MINUTOS = 5

try:
    HISTORICO_MAX = max(50, int(os.getenv("COTACOES_HISTORICO_MAX", "300")))
except (TypeError, ValueError):
    HISTORICO_MAX = 300

try:
    SAUDE_MAX = max(20, int(os.getenv("COTACOES_SAUDE_MAX", "200")))
except (TypeError, ValueError):
    SAUDE_MAX = 200

FONTES = [
    {
        'nome': 'Cooxupé / Hub do Café',
        'url': 'https://hubdocafe.cooxupe.com.br/cotacoes',
        'descricao': 'Café Nova York, B3 e dólar comercial divulgados pela cooperativa (após o fechamento).',
    },
    {
        'nome': 'Coopercam',
        'url': COOPERCAM_URL,
        'descricao': 'Tabela diária de café físico de Campos Gerais/MG, em R$/saca.',
    },
    {
        'nome': 'Cocatrel',
        'url': COCATREL_URL,
        'descricao': 'Café físico COC 01 a 16, com e sem ICMS, e evolução recente (API pública).',
    },
    {
        'nome': 'Banco Central do Brasil',
        'url': 'https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios',
        'descricao': 'PTAX oficial do dia (compra e venda), dados abertos do BCB.',
    },
    {
        'nome': 'AwesomeAPI',
        'url': 'https://docs.awesomeapi.com.br/api-de-moedas',
        'descricao': 'Dólar comercial USD/BRL intraday (compra e venda).',
    },
    {
        'nome': 'ANP Diesel S10',
        'url': maquinario.ANP_URL,
        'descricao': 'Preço médio semanal de revenda do Diesel S10 (dados abertos).',
    },
]


def limpar_cache():
    """Força a próxima leitura a consultar as fontes novamente."""
    _DADOS.update(valor=None, timestamp=None)


def _cache_valido():
    if _DADOS['timestamp'] is None or _DADOS['valor'] is None:
        return False
    return (datetime.now() - _DADOS['timestamp']).total_seconds() < CACHE_MINUTOS * 60


def _numero(valor):
    if valor is None or valor == '':
        return None
    texto = str(valor).replace(' ', '')
    encontrado = re.search(r'-?\d+(?:[.,]\d+)?', texto)
    if not encontrado:
        return None
    try:
        return float(encontrado.group(0).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _numero_br(valor):
    """Converte valores brasileiros como '1.735,00' para float."""
    texto = str(valor).strip().replace(' ', '')
    if '.' in texto and ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    return _numero(texto)


def _chave(fonte, papel):
    papel = (papel or '').upper()
    if fonte == 'Cooxupé':
        if papel.startswith('KC'):
            return 'kc'
        if papel.startswith('ICF'):
            return 'icf'
        if 'DOL' in papel:
            return 'dolcooxupe'
    return None


def _registro(chave, fonte, papel, descricao, valor, unidade, valor_compra=None,
              variacao=None, variacao_percentual=None, data_origem=None):
    return {
        'chave': chave,
        'fonte': fonte,
        'papel': papel,
        'descricao': descricao,
        'valor': valor,
        'valor_compra': valor_compra,
        'unidade': unidade,
        'variacao': variacao,
        'variacao_percentual': variacao_percentual,
        'data_origem': data_origem,
    }


def _coletar_cooxupe():
    resposta = requests.get(COOXUPE_URL, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    # A API responde em UTF-8 mesmo quando o cabeçalho não declara o charset.
    resposta.encoding = 'utf-8'
    payload = resposta.json()
    atualizacao = payload.get('lastUpdate')
    registros = {}
    for item in payload.get('cotacoes') or []:
        papel = str(item.get('Papel') or '').strip()
        chave = _chave('Cooxupé', papel)
        valor = _numero(item.get('Ultimo'))
        if not chave or valor is None:
            continue
        descricoes = {
            'kc': 'Café arábica – Nova York (divulgado pela Cooxupé)',
            'icf': 'Café arábica – B3 (divulgado pela Cooxupé)',
            'dolcooxupe': 'Dólar comercial divulgado pela Cooxupé',
        }
        unidades = {'kc': 'centavos/lb', 'icf': 'US$/saca', 'dolcooxupe': 'R$/US$'}
        registros[chave] = _registro(
            chave, 'Cooxupé', papel, descricoes[chave], valor, unidades[chave],
            variacao=_numero(item.get('Diferenca do Ultimo')),
            variacao_percentual=_numero(item.get('%Ultimo')),
            data_origem=atualizacao,
        )
    if not registros:
        raise ValueError('a API da Cooxupé não trouxe cotações reconhecidas')
    return registros


def _coletar_ptax():
    hoje = datetime.now()
    inicio = hoje - timedelta(days=7)
    params = {
        '@d1': "'" + inicio.strftime('%m-%d-%Y') + "'",
        '@d2': "'" + hoje.strftime('%m-%d-%Y') + "'",
        '$format': 'json',
        '$select': 'cotacaoCompra,cotacaoVenda,dataHoraCotacao',
    }
    resposta = requests.get(BCB_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    valores = resposta.json().get('value') or []
    if not valores:
        raise ValueError('PTAX sem cotações nos últimos 7 dias')
    ultimo = max(valores, key=lambda r: r.get('dataHoraCotacao') or '')
    venda = _numero(ultimo.get('cotacaoVenda'))
    compra = _numero(ultimo.get('cotacaoCompra'))
    if venda is None:
        raise ValueError('PTAX sem valor de venda')
    return {
        'ptax': _registro(
            'ptax', 'Banco Central do Brasil', 'PTAX', 'Dólar PTAX (fechamento)',
            venda, 'R$/US$', valor_compra=compra,
            data_origem=ultimo.get('dataHoraCotacao')),
    }


def _coletar_awesome():
    resposta = requests.get(AWESOME_URL, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    dado = resposta.json().get('USDBRL') or {}
    venda = _numero(dado.get('ask'))
    if venda is None:
        raise ValueError('AwesomeAPI sem valor de venda')
    return {
        'awesome': _registro(
            'awesome', 'AwesomeAPI', 'USD-BRL', 'Dólar comercial (intraday)',
            venda, 'R$/US$', valor_compra=_numero(dado.get('bid')),
            variacao=_numero(dado.get('varBid')),
            variacao_percentual=_numero(dado.get('pctChange')),
            data_origem=dado.get('create_date')),
    }


def _coletar_coopercam():
    """Lê a tabela diária da Coopercam (HTML público)."""
    resposta = requests.get(COOPERCAM_URL, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    resposta.encoding = 'utf-8'
    html = resposta.text
    data = re.search(r'COTAÇÃO:\s*(\d{2}/\d{2}/\d{4})', html, re.I)
    if not data:
        raise ValueError('Coopercam sem data da cotação')
    bloco = html[data.end():data.end() + 4000]
    padrao = r'<a[^>]*>\s*([^<:]+?):\s*<b>\s*R\$\s*([\d.]+,\d{2})\s*</b>\s*</a>'
    registros = {}
    for papel, texto_valor in re.findall(padrao, bloco, re.I):
        papel = papel.strip()
        if papel not in ORDEM_COOPERCAM:
            continue
        valor = _numero_br(texto_valor)
        if valor is None:
            continue
        chave = 'coopercam_' + re.sub(r'[^a-z0-9]+', '_', papel.lower()).strip('_')
        registros[chave] = _registro(
            chave, 'Coopercam', papel, f'Cotação {papel} publicada pela Coopercam',
            valor, 'R$/saca', data_origem=data.group(1),
        )
    if not registros:
        raise ValueError('Coopercam sem classificações reconhecidas')
    return registros


def _coletar_cocatrel():
    """Lê a API pública da Cocatrel (café físico COC 01 a 16)."""
    headers = dict(HEADERS)
    headers['Referer'] = COCATREL_URL
    resposta = requests.get(COCATREL_API, headers=headers, timeout=TIMEOUT)
    resposta.raise_for_status()
    payload = resposta.json()
    data = payload.get('DataCotacao')
    if isinstance(data, str) and len(data) >= 10:
        try:
            data = datetime.strptime(data[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            pass
    registros = {}
    for item in payload.get('CotacaoCafe') or []:
        papel = str(item.get('Classificacao') or '').strip()
        valor = _numero(item.get('ValorCotacao'))
        if not papel or valor is None:
            continue
        chave = 'cocatrel_' + re.sub(r'[^a-z0-9]+', '_', papel.lower()).strip('_')
        # valor_compra é o campo genérico do snapshot; aqui guarda o preço com ICMS.
        registros[chave] = _registro(
            chave, 'Cocatrel', papel, f'Cotação {papel} publicada pela Cocatrel',
            valor, 'R$/saca', valor_compra=_numero(item.get('ValorCotacaoComICMS')),
            data_origem=data,
        )
    if not registros:
        raise ValueError('Cocatrel sem classificações reconhecidas')
    return registros


MONITORAMENTO = {
    'cooxupe': {
        'fonte': 'Cooxupé / Hub do Café',
        'url': FONTES[0]['url'],
        'coletor': _coletar_cooxupe,
    },
    'ptax': {
        'fonte': 'Banco Central do Brasil',
        'url': FONTES[3]['url'],
        'coletor': _coletar_ptax,
    },
    'awesome': {
        'fonte': 'AwesomeAPI',
        'url': FONTES[4]['url'],
        'coletor': _coletar_awesome,
    },
    'coopercam': {
        'fonte': 'Coopercam',
        'url': COOPERCAM_URL,
        'coletor': _coletar_coopercam,
    },
    'cocatrel': {
        'fonte': 'Cocatrel',
        'url': COCATREL_URL,
        'coletor': _coletar_cocatrel,
    },
    'climatempo': {
        'fonte': 'Climatempo',
        'url': f"{clima.BASE_URL}/cidade/{clima.CIDADE_ID}/{clima.CIDADE_SLUG}",
        'coletor': clima.verificar_fonte,
    },
    'anp_diesel': {
        'fonte': 'ANP Diesel S10',
        'url': FONTES[5]['url'],
        'coletor': maquinario.verificar_fonte,
        # A ANP publica por semana: 10 dias evitam "aviso" apenas pela defasagem natural.
        'max_dias': 10,
    },
}


def _limite_config(chave, padrao):
    """Limite de retenção configurável em Configurações > Sistema."""
    try:
        return max(1, int(get_config(chave, str(padrao))))
    except (TypeError, ValueError):
        return padrao


def _data_origem(texto):
    """Extrai uma data de formatos comuns das fontes (dd/mm/aaaa ou ISO)."""
    if not texto:
        return None
    texto = str(texto)
    encontrado = re.search(r'(\d{4})-(\d{2})-(\d{2})', texto)
    if encontrado:
        try:
            return datetime(int(encontrado.group(1)), int(encontrado.group(2)),
                            int(encontrado.group(3))).date()
        except ValueError:
            return None
    encontrado = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto)
    if encontrado:
        try:
            return datetime(int(encontrado.group(3)), int(encontrado.group(2)),
                            int(encontrado.group(1))).date()
        except ValueError:
            return None
    return None


def _avaliar_datas(registros, max_dias=2):
    """Distingue fonte respondendo de fonte respondendo com dados defasados."""
    datas = [d for d in (_data_origem(r.get('data_origem')) for r in registros.values()) if d]
    if not datas:
        return 'aviso', 'A fonte respondeu, mas não informou a data da cotação.'
    mais_recente = max(datas)
    dias = (datetime.now().date() - mais_recente).days
    if dias > max_dias:
        return 'aviso', (f'Última data publicada: {mais_recente.strftime("%d/%m/%Y")} '
                         f'({dias} dias atrás).')
    return 'ok', (f'{len(registros)} registro(s) recebido(s) · '
                  f'{mais_recente.strftime("%d/%m/%Y")}.')


def _geral(itens):
    estados = [item.get('status') for item in itens]
    if 'erro' in estados:
        return 'erro'
    if any(estado in ('aviso', 'pendente') for estado in estados):
        return 'aviso'
    return 'ok'


def _registrar_saude(fonte, status, mensagem, quantidade=0, data_origem=None,
                     duracao_ms=0, url=None):
    """Grava o resultado de uma consulta e mantém apenas os eventos ativos recentes."""
    limite = _limite_config('cotacoes_saude_max', SAUDE_MAX)

    def operacao(cursor):
        cursor.execute("""
            INSERT INTO cotacoes_saude
                (fonte, status, mensagem, quantidade, data_origem, duracao_ms, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (fonte, status, (mensagem or '')[:255], quantidade, data_origem, duracao_ms, url))
        cursor.execute("""
            UPDATE cotacoes_saude SET ativo = FALSE
            WHERE ativo = TRUE
              AND id NOT IN (
                  SELECT id FROM cotacoes_saude
                  WHERE ativo = TRUE
                  ORDER BY verificado_em DESC, id DESC
                  LIMIT %s
              )
        """, (limite,))

    try:
        executar_transacao(operacao)
    except Exception as e:
        logger.error(f"cotacoes._registrar_saude ({fonte}): {e}")


def _monitorar(item, rethrow=False):
    """Executa um coletor, registra o resultado e opcionalmente propaga a falha."""
    inicio = datetime.now()
    try:
        registros = item['coletor']()
        if not registros:
            raise ValueError('nenhuma cotação reconhecida')
        status, mensagem = _avaliar_datas(registros, item.get('max_dias', 2))
        datas = [str(r.get('data_origem')) for r in registros.values() if r.get('data_origem')]
        data_origem = max(datas) if datas else None
        quantidade = len(registros)
    except Exception as e:
        logger.error(f"cotacoes._monitorar ({item['fonte']}): {e}")
        status, mensagem = 'erro', str(e)[:240]
        registros, quantidade, data_origem = {}, 0, None
        duracao_ms = int((datetime.now() - inicio).total_seconds() * 1000)
        _registrar_saude(item['fonte'], status, mensagem, quantidade, data_origem,
                         duracao_ms, item.get('url'))
        if rethrow:
            raise
        return {
            'fonte': item['fonte'], 'url': item.get('url'), 'status': status,
            'mensagem': mensagem, 'quantidade': 0, 'data_origem': None,
            'duracao_ms': duracao_ms,
        }

    duracao_ms = int((datetime.now() - inicio).total_seconds() * 1000)
    _registrar_saude(item['fonte'], status, mensagem, quantidade, data_origem,
                     duracao_ms, item.get('url'))
    return {
        'fonte': item['fonte'], 'url': item.get('url'), 'status': status,
        'mensagem': mensagem, 'quantidade': quantidade, 'data_origem': data_origem,
        'duracao_ms': duracao_ms, 'registros': registros,
    }


def verificar_fontes(force=False):
    """Testa todas as fontes agora e devolve o estado de cada uma."""
    if (not force and _SAUDE['valor'] is not None and _SAUDE['timestamp'] is not None
            and (datetime.now() - _SAUDE['timestamp']).total_seconds() < SAUDE_CACHE_MINUTOS * 60):
        return _SAUDE['valor']

    itens = []
    for item in MONITORAMENTO.values():
        resultado = _monitorar(item)
        itens.append({k: v for k, v in resultado.items() if k != 'registros'})

    valor = {
        'geral': _geral(itens),
        'itens': itens,
        'verificado_em': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }
    _SAUDE.update(valor=valor, timestamp=datetime.now())
    return valor


def resumo_saude():
    """Último estado gravado de cada fonte, sem consultar a rede."""
    itens = []
    try:
        linhas = executar_query("""
            SELECT DISTINCT ON (fonte) fonte, status, mensagem, quantidade,
                   data_origem, duracao_ms, url, verificado_em
            FROM cotacoes_saude
            WHERE ativo = TRUE
            ORDER BY fonte, verificado_em DESC, id DESC
        """, fetch_all=True, dict_cursor=True) or []
        for linha in linhas:
            itens.append({
                'fonte': linha['fonte'], 'status': linha['status'],
                'mensagem': linha['mensagem'], 'quantidade': linha['quantidade'],
                'data_origem': linha['data_origem'], 'duracao_ms': linha['duracao_ms'],
                'url': linha['url'], 'verificado_em': linha['verificado_em'],
            })
    except Exception as e:
        logger.error(f"cotacoes.resumo_saude: {e}")

    conhecidas = {item['fonte'] for item in MONITORAMENTO.values()}
    mapa = {item['fonte'] for item in itens}
    for item in MONITORAMENTO.values():
        if item['fonte'] not in mapa:
            itens.append({
                'fonte': item['fonte'], 'status': 'pendente',
                'mensagem': 'Ainda sem verificação registrada.', 'quantidade': 0,
                'data_origem': None, 'duracao_ms': 0, 'url': item.get('url'),
                'verificado_em': None,
            })
    # Fontes antigas que não estão mais no monitor também aparecem, marcadas.
    for item in itens:
        if item['fonte'] not in conhecidas:
            item['status'] = 'pendente'

    ordem = {item['fonte']: posicao for posicao, item in enumerate(MONITORAMENTO.values())}
    itens.sort(key=lambda item: (ordem.get(item['fonte'], 99), item['fonte']))
    return {
        'geral': _geral(itens),
        'itens': itens,
        'verificado_em': max([item['verificado_em'] for item in itens
                              if item['verificado_em']] or [None]),
    }


def listar_saude_eventos(limite=20, offset=0):
    """Eventos de integridade paginados, mais recentes primeiro."""
    try:
        return executar_query("""
            SELECT fonte, status, mensagem, quantidade, data_origem, duracao_ms,
                   url, verificado_em
            FROM cotacoes_saude
            WHERE ativo = TRUE
            ORDER BY verificado_em DESC, id DESC
            LIMIT %s OFFSET %s
        """, (limite, offset), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"cotacoes.listar_saude_eventos: {e}")
        return []


def contar_saude_eventos():
    try:
        registro = executar_query(
            "SELECT COUNT(*) AS total FROM cotacoes_saude WHERE ativo = TRUE",
            fetch_one=True, dict_cursor=True,
        )
        return int(registro['total']) if registro else 0
    except Exception as e:
        logger.error(f"cotacoes.contar_saude_eventos: {e}")
        return 0


def _salvar_snapshots(registros):
    def operacao(cursor):
        for r in registros.values():
            cursor.execute("""
                INSERT INTO cotacoes_snapshots
                    (chave, fonte, papel, descricao, valor, valor_compra, unidade,
                     variacao, variacao_percentual, data_origem)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                r.get('chave'), r.get('fonte'), r.get('papel'), r.get('descricao'),
                r.get('valor'), r.get('valor_compra'), r.get('unidade'),
                r.get('variacao'), r.get('variacao_percentual'), r.get('data_origem'),
            ))
        # Retenção lógica: mantém ativos apenas os snapshots mais recentes.
        cursor.execute("""
            UPDATE cotacoes_snapshots SET ativo = FALSE
            WHERE ativo = TRUE
              AND id NOT IN (
                  SELECT id FROM cotacoes_snapshots
                  WHERE ativo = TRUE
                  ORDER BY coletado_em DESC, id DESC
                  LIMIT %s
              )
        """, (_limite_config('cotacoes_historico_max', HISTORICO_MAX),))

    try:
        executar_transacao(operacao)
    except Exception as e:
        logger.error(f"cotacoes._salvar_snapshots: {e}")


def _carregar_ultimos():
    try:
        linhas = executar_query("""
            SELECT DISTINCT ON (chave) chave, fonte, papel, descricao, valor,
                   valor_compra, unidade, variacao, variacao_percentual,
                   data_origem, coletado_em
            FROM cotacoes_snapshots
            WHERE ativo = TRUE
            ORDER BY chave, coletado_em DESC
        """, fetch_all=True, dict_cursor=True) or []
        return {r['chave']: r for r in linhas}
    except Exception as e:
        logger.error(f"cotacoes._carregar_ultimos: {e}")
        return {}


def _carregar_prefixo(prefixo):
    """Último snapshot salvo de um grupo (ex.: coopercam_) para fallback."""
    try:
        linhas = executar_query("""
            SELECT DISTINCT ON (chave) chave, fonte, papel, descricao, valor,
                   valor_compra, unidade, variacao, variacao_percentual,
                   data_origem, coletado_em
            FROM cotacoes_snapshots
            WHERE ativo = TRUE AND chave LIKE %s
            ORDER BY chave, coletado_em DESC
        """, (prefixo + '%',), fetch_all=True, dict_cursor=True) or []
        return {r['chave']: r for r in linhas}
    except Exception as e:
        logger.error(f"cotacoes._carregar_prefixo ({prefixo}): {e}")
        return {}


def _val(registro, campo='valor'):
    if not registro or registro.get(campo) is None:
        return None
    try:
        return float(registro[campo])
    except (TypeError, ValueError):
        return None


def _arredondar(valor):
    return round(valor, 2) if valor is not None else None


def _arredondar_cambio(valor):
    return round(valor, 4) if valor is not None else None


def _grupos_cooperativas(registros):
    """Agrupa as classificações das cooperativas para a exibição em destaque."""
    configuracoes = [
        ('coopercam', 'Coopercam', COOPERCAM_URL, ORDEM_COOPERCAM),
        ('cocatrel', 'Cocatrel', COCATREL_URL, ORDEM_COCATREL),
    ]
    grupos = []
    for prefixo, nome, url, ordem in configuracoes:
        itens = []
        for r in registros.values():
            if not str(r.get('chave') or '').startswith(prefixo + '_'):
                continue
            papel = str(r.get('papel') or '')
            itens.append({
                'chave': r.get('chave'),
                'papel': papel,
                'descricao': r.get('descricao'),
                'valor': _val(r),
                'valor_com_icms': _val(r, 'valor_compra'),
                'data_origem': r.get('data_origem'),
            })
        if not itens:
            continue
        itens.sort(key=lambda x: ordem.index(x['papel']) if x['papel'] in ordem else len(ordem))
        grupos.append({
            'nome': nome,
            'url': url,
            'data': itens[0]['data_origem'],
            'itens': itens,
            'destaques': itens[:3],
            'com_icms': prefixo == 'cocatrel',
        })
    return grupos


def _montar(registros, atualizado_em=None, stale=False, erro=None):
    kc = registros.get('kc')
    icf = registros.get('icf')
    ptax = registros.get('ptax')
    awesome = registros.get('awesome')
    dol = registros.get('dolcooxupe')

    ptax_venda = _val(ptax)
    ptax_compra = _val(ptax, 'valor_compra')
    # AwesomeAPI traz compra e venda da mesma fonte; Cooxupé é o fallback.
    comercial = _val(awesome) or _val(dol)
    comercial_compra = _val(awesome, 'valor_compra') or _val(dol)
    comercial_fonte = 'AwesomeAPI' if awesome else 'Cooxupé (DOL COM)'
    comercial_data = (awesome or {}).get('data_origem') if awesome else (dol or {}).get('data_origem')
    taxa = ptax_venda or comercial

    cents = _val(kc)
    ny_usd_saca = cents / 100 * LIBRAS_POR_SACA if cents is not None else None
    cafe_ny = None
    if cents is not None:
        cafe_ny = {
            'papel': kc.get('papel'),
            'cents_lb': round(cents, 2),
            'variacao': _val(kc, 'variacao'),
            'variacao_percentual': _val(kc, 'variacao_percentual'),
            'data_origem': kc.get('data_origem'),
            'usd_saca': _arredondar(ny_usd_saca),
            'brl_saca_ptax': _arredondar(ny_usd_saca * taxa) if ny_usd_saca and taxa else None,
            'brl_saca_comercial': _arredondar(ny_usd_saca * comercial) if ny_usd_saca and comercial else None,
        }

    icf_usd = _val(icf)
    cafe_b3 = None
    if icf_usd is not None:
        cafe_b3 = {
            'papel': icf.get('papel'),
            'usd_saca': round(icf_usd, 2),
            'variacao': _val(icf, 'variacao'),
            'variacao_percentual': _val(icf, 'variacao_percentual'),
            'data_origem': icf.get('data_origem'),
            'brl_saca_ptax': _arredondar(icf_usd * taxa) if taxa else None,
            'brl_saca_comercial': _arredondar(icf_usd * comercial) if comercial else None,
        }

    return {
        'atualizado_em': atualizado_em or datetime.now().strftime('%d/%m/%Y %H:%M'),
        'stale': stale,
        'erro': erro,
        'cafe_ny': cafe_ny,
        'cafe_b3': cafe_b3,
        'dolar': {
            'ptax_compra': _arredondar_cambio(ptax_compra),
            'ptax_venda': _arredondar_cambio(ptax_venda),
            'ptax_data': ptax.get('data_origem') if ptax else None,
            'comercial_compra': _arredondar_cambio(comercial_compra),
            'comercial_venda': _arredondar_cambio(comercial),
            'comercial_fonte': comercial_fonte,
            'comercial_data': comercial_data,
            'comercial_variacao_percentual': _val(awesome, 'variacao_percentual'),
        },
        'taxa_conversao': _arredondar_cambio(taxa),
        'taxa_fonte': 'PTAX (venda)' if ptax_venda else comercial_fonte,
        'cooperativas': _grupos_cooperativas(registros),
        'fontes': FONTES,
    }


def obter_cotacoes(force=False):
    """Retorna as cotações consolidadas, usando cache de 30 minutos."""
    if not force and _cache_valido():
        return _DADOS['valor']

    try:
        registros = _monitorar(MONITORAMENTO['cooxupe'], rethrow=True)['registros']
        registros.update(_monitorar(MONITORAMENTO['ptax'], rethrow=True)['registros'])
        reaproveitados = set()
        for chave, prefixo in (
            ('awesome', None),
            ('coopercam', 'coopercam_'),
            ('cocatrel', 'cocatrel_'),
        ):
            descobertos = _monitorar(MONITORAMENTO[chave])['registros']
            if descobertos:
                registros.update(descobertos)
            elif prefixo:
                for chave_snapshot, registro in _carregar_prefixo(prefixo).items():
                    registros[chave_snapshot] = registro
                    reaproveitados.add(chave_snapshot)

        if not registros.get('kc') and not registros.get('ptax'):
            raise ValueError('nenhuma cotação principal foi obtida')

        _salvar_snapshots({k: v for k, v in registros.items() if k not in reaproveitados})
        dados = _montar(registros)
        _DADOS.update(valor=dados, timestamp=datetime.now())
        return dados
    except Exception as e:
        logger.error(f"cotacoes.obter_cotacoes: {e}")
        dados = _montar(
            _carregar_ultimos(),
            atualizado_em=datetime.now().strftime('%d/%m/%Y %H:%M'),
            stale=True,
            erro=str(e),
        )
        _DADOS.update(valor=dados, timestamp=datetime.now())
        return dados


def listar_historico(limite=20, offset=0):
    """Snapshots ativos paginados, para a tabela da página de cotações."""
    try:
        return executar_query("""
            SELECT chave, fonte, papel, valor, valor_compra, unidade,
                   data_origem, coletado_em
            FROM cotacoes_snapshots
            WHERE ativo = TRUE
            ORDER BY coletado_em DESC, id DESC
            LIMIT %s OFFSET %s
        """, (limite, offset), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"cotacoes.listar_historico: {e}")
        return []


def listar_ultima_coleta():
    """Valores gravados na coleta mais recente (para o monitor das fontes)."""
    try:
        return executar_query("""
            SELECT chave, fonte, papel, valor, unidade, data_origem, coletado_em
            FROM cotacoes_snapshots
            WHERE ativo = TRUE AND coletado_em >= (
                SELECT MAX(coletado_em) - INTERVAL '1 minute'
                FROM cotacoes_snapshots WHERE ativo = TRUE
            )
            ORDER BY fonte, chave
        """, fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"cotacoes.listar_ultima_coleta: {e}")
        return []


def contar_historico():
    try:
        registro = executar_query(
            "SELECT COUNT(*) AS total FROM cotacoes_snapshots WHERE ativo = TRUE",
            fetch_one=True, dict_cursor=True,
        )
        return int(registro['total']) if registro else 0
    except Exception as e:
        logger.error(f"cotacoes.contar_historico: {e}")
        return 0
