"""
Cotações de café e dólar de fontes públicas, sem login e sem chave de API.

Fontes:
- Cooxupé / Hub do Café: API JSON pública /api/cotacao-cafe
- Banco Central do Brasil: PTAX (dados abertos, OData)
- AwesomeAPI: dólar comercial USD/BRL

Atualização preguiçosa com cache de 30 minutos (COTACOES_CACHE_MINUTOS) e botão
para forçar no painel admin. Cada coleta grava um snapshot no banco para histórico.
"""
import logging
import os
import re
import sys
from datetime import datetime, timedelta

import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config')))
from database import executar_query, executar_transacao

logger = logging.getLogger(__name__)

COOXUPE_URL = "https://hubdocafe.cooxupe.com.br/api/cotacao-cafe"
BCB_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
           "CotacaoDolarPeriodo(dataInicial=@d1,dataFinalCotacao=@d2)")
AWESOME_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 15
LIBRAS_POR_SACA = 132.27736  # 60 kg (saca de café) convertidos para libras

try:
    CACHE_MINUTOS = max(1, int(os.getenv("COTACOES_CACHE_MINUTOS", "30")))
except (TypeError, ValueError):
    CACHE_MINUTOS = 30

_DADOS = {"valor": None, "timestamp": None}

FONTES = [
    {
        'nome': 'Cooxupé / Hub do Café',
        'url': 'https://hubdocafe.cooxupe.com.br/cotacoes',
        'descricao': 'Café Nova York, B3 e dólar comercial divulgados pela cooperativa (após o fechamento).',
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
            ORDER BY chave, coletado_em DESC
        """, fetch_all=True, dict_cursor=True) or []
        return {r['chave']: r for r in linhas}
    except Exception as e:
        logger.error(f"cotacoes._carregar_ultimos: {e}")
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
        'fontes': FONTES,
    }


def obter_cotacoes(force=False):
    """Retorna as cotações consolidadas, usando cache de 30 minutos."""
    if not force and _cache_valido():
        return _DADOS['valor']

    try:
        registros = _coletar_cooxupe()
        registros.update(_coletar_ptax())
        try:
            registros.update(_coletar_awesome())
        except Exception as e:
            logger.error(f"cotacoes.obter_cotacoes (AwesomeAPI): {e}")

        if not registros.get('kc') and not registros.get('ptax'):
            raise ValueError('nenhuma cotação principal foi obtida')

        _salvar_snapshots(registros)
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


def listar_historico(limite=40):
    """Últimos snapshots coletados, para a tabela da página de cotações."""
    try:
        return executar_query("""
            SELECT chave, fonte, papel, valor, valor_compra, unidade,
                   data_origem, coletado_em
            FROM cotacoes_snapshots
            ORDER BY coletado_em DESC, id DESC
            LIMIT %s
        """, (limite,), fetch_all=True, dict_cursor=True) or []
    except Exception as e:
        logger.error(f"cotacoes.listar_historico: {e}")
        return []
