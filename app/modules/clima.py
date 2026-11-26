"""
Módulo de Clima e Previsão do Tempo.

Fonte: Climatempo (páginas públicas de previsão). Não exige chave de API.
Os dados são buscados no máximo a cada 3 horas (configurável por
CLIMATEMPO_CACHE_HORAS) e reaproveitados em todas as telas.
"""

import html as htmlmod
import json
import logging
import os
import re
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.climatempo.com.br/previsao-do-tempo"
CIDADE_ID = os.getenv("CLIMATEMPO_CIDADE_ID", "2037")
CIDADE_SLUG = os.getenv("CLIMATEMPO_CIDADE_SLUG", "camposgerais-mg")
CIDADE_NOME = os.getenv("CLIMATEMPO_CIDADE_NOME", "Campos Gerais/MG")
FONTE = "Climatempo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
}
TIMEOUT_SEGUNDOS = 15

try:
    CACHE_HORAS = max(1, int(os.getenv("CLIMATEMPO_CACHE_HORAS", "3")))
except (TypeError, ValueError):
    CACHE_HORAS = 3

_DADOS = {"metas": None, "dias": None, "timestamp": None}

_METAS = (
    "tmomento", "tmin", "tmax", "cmomento", "iconoi", "chuvamm",
    "urmin", "urmax", "gust", "gustDirection", "uvmax", "idCidade",
)


def _cache_valido():
    if _DADOS["timestamp"] is None:
        return False
    return (datetime.now() - _DADOS["timestamp"]).total_seconds() < CACHE_HORAS * 3600


def limpar_cache():
    """Força a próxima leitura a buscar dados novos do Climatempo."""
    _DADOS.update(metas=None, dias=None, timestamp=None)


def _buscar_pagina(url):
    resposta = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    resposta.encoding = "utf-8"
    return resposta.text


def _meta(pagina, nome):
    padrao = r'<meta\s+name=["\']' + re.escape(nome) + r'["\']\s+content=["\']([^"\']*)["\']'
    encontrado = re.search(padrao, pagina, re.IGNORECASE)
    if not encontrado:
        return None
    return htmlmod.unescape(encontrado.group(1)).strip()


def _numero(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _carregar(force=False):
    """Carrega metas do tempo atual e o JSON dos 15 dias, com cache."""
    if not force and _cache_valido() and _DADOS["metas"] and _DADOS["dias"]:
        return _DADOS["metas"], _DADOS["dias"]
    try:
        pagina_hoje = _buscar_pagina(f"{BASE_URL}/cidade/{CIDADE_ID}/{CIDADE_SLUG}")
        pagina_15_dias = _buscar_pagina(
            f"{BASE_URL}/15-dias/cidade/{CIDADE_ID}/{CIDADE_SLUG}"
        )

        metas = {chave: _meta(pagina_hoje, chave) for chave in _METAS}
        bloco = re.search(r'data-infos="([^"]+)"', pagina_15_dias)
        if not bloco:
            raise ValueError("bloco de previsão (data-infos) não encontrado no Climatempo")
        dias = json.loads(htmlmod.unescape(bloco.group(1)))
        if not isinstance(dias, list) or not dias:
            raise ValueError("previsão do Climatempo veio vazia")

        _DADOS.update(metas=metas, dias=dias, timestamp=datetime.now())
        return metas, dias
    except Exception as e:
        logger.error(f"clima._carregar: {e}")
        if _DADOS["metas"] and _DADOS["dias"]:
            return _DADOS["metas"], _DADOS["dias"]
        return None, None


def _condicao(texto):
    """Normaliza a descrição do Climatempo para um código de ícone estável."""
    descricao = (texto or "").lower()
    if any(p in descricao for p in ("temporal", "trovoad", "raio")):
        return "Thunderstorm"
    if any(p in descricao for p in ("neve", "granizo")):
        return "Snow"
    if any(p in descricao for p in ("chuva", "chove", "pancad")):
        return "Rain"
    if any(p in descricao for p in ("neblina", "névoa", "nvoeir")):
        return "Mist"
    if any(p in descricao for p in ("nublado", "nuvens", "nuvem")):
        return "Clouds"
    if any(p in descricao for p in ("sol", "aberto", "limpo")):
        return "Clear"
    return "Clouds"


def _descricao_dia(dia):
    textos = (dia.get("textIcon") or {}).get("text") or {}
    return textos.get("reducedPhrasePt") or textos.get("pt") or ""


def _umidade_dia(dia):
    umidade = dia.get("humidity") or {}
    valores = [_numero(umidade.get("min")), _numero(umidade.get("max"))]
    validos = [v for v in valores if v is not None]
    return round(sum(validos) / len(validos)) if validos else None


def get_clima_atual(force=False):
    """Retorna o clima atual de Campos Gerais com dados do Climatempo."""
    metas, dias = _carregar(force=force)
    if not metas or not dias:
        return None

    hoje = dias[0]
    temperaturas = hoje.get("temperature") or {}
    vento = hoje.get("wind") or {}
    chuva_dia = hoje.get("rain") or {}
    sol = hoje.get("sun") or {}
    sensacao_bruta = (hoje.get("thermalSensation") or {}).get("thermalSensation")

    temperatura = _numero(metas.get("tmomento"))
    if temperatura is None:
        temperatura = _numero(temperaturas.get("min")) or _numero(temperaturas.get("max"))

    umidade_min = _numero(metas.get("urmin")) or _numero((hoje.get("humidity") or {}).get("min"))
    umidade_max = _numero(metas.get("urmax")) or _numero((hoje.get("humidity") or {}).get("max"))
    if umidade_min is not None and umidade_max is not None:
        umidade = round((umidade_min + umidade_max) / 2)
    else:
        umidade = umidade_min if umidade_min is not None else umidade_max

    velocidade_ms = _numero(vento.get("avgVelocity"))
    velocidade_kmh = round(velocidade_ms * 3.6, 1) if velocidade_ms is not None else 0.0
    rajada = _numero(metas.get("gust"))
    if rajada is None:
        rajada = _numero(vento.get("maxGust"))

    descricao = _descricao_dia(hoje) or (metas.get("cmomento") or "").capitalize()
    atualizacao = _DADOS["timestamp"] or datetime.now()

    clima = {
        "cidade": CIDADE_NOME,
        "fonte": FONTE,
        "temperatura": round(temperatura, 1) if temperatura is not None else 0.0,
        "sensacao": round(_numero(sensacao_bruta), 1) if _numero(sensacao_bruta) is not None else temperatura,
        "temp_min": _numero(metas.get("tmin")) or _numero(temperaturas.get("min")) or 0.0,
        "temp_max": _numero(metas.get("tmax")) or _numero(temperaturas.get("max")) or 0.0,
        "umidade": int(umidade) if umidade is not None else 0,
        "umidade_min": int(umidade_min) if umidade_min is not None else None,
        "umidade_max": int(umidade_max) if umidade_max is not None else None,
        "pressao": None,
        "nebulosidade": None,
        "vento_velocidade": velocidade_kmh,
        "vento_direcao": _numero(vento.get("direction_degrees")),
        "vento_cardinal": metas.get("gustDirection") or vento.get("direction") or "-",
        "vento_rajada": round(rajada, 1) if rajada is not None else None,
        "descricao": descricao,
        "condition": _condicao(f"{descricao} {metas.get('cmomento') or ''}"),
        "codigo": metas.get("iconoi")
                  or ((hoje.get("textIcon") or {}).get("icon") or {}).get("day")
                  or "Clouds",
        "chuva_mm": _numero(metas.get("chuvamm")) or _numero(chuva_dia.get("precipitation")) or 0.0,
        "probabilidade_chuva": int(_numero(chuva_dia.get("probability")) or 0),
        "indice_uv": _numero(metas.get("uvmax")),
        "nascer_sol": str(sol.get("sunshine") or "")[:5] or "-",
        "por_sol": str(sol.get("sunset") or "")[:5] or "-",
        "atualizacao": atualizacao.strftime("%H:%M"),
    }
    clima["alertas"] = gerar_alertas(clima)
    return clima


def get_previsao(force=False):
    """Retorna a previsão diária do Climatempo (até 15 dias)."""
    _, dias = _carregar(force=force)
    if not dias:
        return None

    previsoes = []
    for dia in dias[:15]:
        descricao = _descricao_dia(dia)
        temperaturas = dia.get("temperature") or {}
        vento = dia.get("wind") or {}
        chuva = dia.get("rain") or {}
        sol = dia.get("sun") or {}
        velocidade_ms = _numero(vento.get("avgVelocity"))
        umidade = _umidade_dia(dia)

        previsoes.append({
            "data": dia.get("day") or "",
            "dia_semana": dia.get("dayWeekFullMin") or dia.get("dayWeek") or "",
            "temp_min": _numero(temperaturas.get("min")) or 0.0,
            "temp_max": _numero(temperaturas.get("max")) or 0.0,
            "umidade": int(umidade) if umidade is not None else 0,
            "descricao": descricao,
            "condition": _condicao(descricao),
            "icone": ((dia.get("textIcon") or {}).get("icon") or {}).get("day"),
            "chuva": _numero(chuva.get("precipitation")) or 0.0,
            "probabilidade_chuva": int(_numero(chuva.get("probability")) or 0),
            "vento": round(velocidade_ms * 3.6, 1) if velocidade_ms is not None else 0.0,
            "rajada": _numero(vento.get("maxGust")),
            "nascer_sol": str(sol.get("sunshine") or "")[:5] or "-",
            "por_sol": str(sol.get("sunset") or "")[:5] or "-",
        })
    return previsoes


def gerar_alertas(clima):
    """Gera alertas agronômicos baseados nas condições climáticas."""
    if not clima:
        return []
    alertas = []
    temperatura = clima.get("temperatura") or 0
    vento = clima.get("vento_velocidade") or 0
    rajada = clima.get("vento_rajada") or 0
    umidade = clima.get("umidade") or 0

    if temperatura < 10:
        alertas.append({
            "tipo": "frio", "severidade": "alto",
            "mensagem": f"Temperatura baixa: {temperatura}°C. Proteja as plantas!"
        })
    elif temperatura < 15:
        alertas.append({
            "tipo": "frio", "severidade": "medio",
            "mensagem": f"Temperatura amena: {temperatura}°C. Fique atento."
        })

    if temperatura > 35:
        alertas.append({
            "tipo": "calor", "severidade": "alto",
            "mensagem": f"Calor intenso: {temperatura}°C. Risco de estresse hídrico!"
        })
    elif temperatura > 30:
        alertas.append({
            "tipo": "calor", "severidade": "medio",
            "mensagem": f"Temperatura elevada: {temperatura}°C."
        })

    if clima.get("condition") in ("Rain", "Drizzle", "Thunderstorm") \
            or (clima.get("probabilidade_chuva") or 0) >= 70:
        alertas.append({
            "tipo": "chuva", "severidade": "medio",
            "mensagem": f"Chuva prevista ({clima.get('probabilidade_chuva', 0)}%). Evite pulverizações."
        })

    if vento > 40 or rajada > 55:
        alertas.append({
            "tipo": "vento", "severidade": "alto",
            "mensagem": f"Ventos fortes: {vento} km/h (rajadas de {rajada or '-'} km/h). Cuidado com aplicações!"
        })
    elif vento > 25:
        alertas.append({
            "tipo": "vento", "severidade": "medio",
            "mensagem": f"Ventos moderados: {vento} km/h."
        })

    if umidade and umidade < 30:
        alertas.append({
            "tipo": "umidade", "severidade": "alto",
            "mensagem": f"Umidade muito baixa: {umidade}%. Risco de incêndio!"
        })
    elif umidade and umidade < 50:
        alertas.append({
            "tipo": "umidade", "severidade": "baixo",
            "mensagem": f"Umidade baixa: {umidade}%."
        })

    return alertas


_ICONE_CONDICAO = {
    "Clear": "bi-sun-fill",
    "Clouds": "bi-cloud-fill",
    "Rain": "bi-cloud-rain-fill",
    "Drizzle": "bi-cloud-drizzle",
    "Thunderstorm": "bi-cloud-lightning-rain-fill",
    "Snow": "bi-snow",
    "Mist": "bi-cloud-fog-fill",
    "default": "bi-cloud-fill",
}

# Códigos usados pelo OpenWeather (mantidos para compatibilidade com telas antigas)
_ICONE_OPENWEATHER = {
    "01d": "bi-sun-fill", "01n": "bi-moon-stars-fill",
    "02d": "bi-cloud-sun-fill", "02n": "bi-cloud-moon-fill",
    "03d": "bi-cloud-fill", "03n": "bi-cloud-fill",
    "04d": "bi-clouds-fill", "04n": "bi-clouds-fill",
    "09d": "bi-cloud-rain-heavy-fill", "09n": "bi-cloud-rain-heavy-fill",
    "10d": "bi-cloud-rain-fill", "10n": "bi-cloud-rain-fill",
    "11d": "bi-cloud-lightning-rain-fill", "11n": "bi-cloud-lightning-rain-fill",
    "13d": "bi-snow", "13n": "bi-snow",
    "50d": "bi-cloud-fog-fill", "50n": "bi-cloud-fog-fill",
}

# Códigos de ícone do Climatempo (ex.: 6n, 4t)
_ICONE_CLIMATEMPO = {
    "1": "bi-sun-fill",
    "2": "bi-cloud-sun-fill",
    "3": "bi-cloud-fill",
    "4": "bi-cloud-sun-fill",
    "5": "bi-cloud-rain-fill",
    "6": "bi-clouds-fill",
    "7": "bi-snow",
    "8": "bi-cloud-lightning-rain-fill",
    "9": "bi-cloud-fog-fill",
}


def get_icone_clima(codigo):
    """Retorna o ícone Bootstrap para condição ou código do Climatempo."""
    chave = str(codigo or "").strip().lower()
    if chave in _ICONE_OPENWEATHER:
        return _ICONE_OPENWEATHER[chave]
    if chave in _ICONE_CONDICAO:
        return _ICONE_CONDICAO[chave]
    numeros = re.match(r"^(\d+)", chave)
    if numeros:
        return _ICONE_CLIMATEMPO.get(numeros.group(1), "bi-cloud-fill")
    return _ICONE_CONDICAO.get(_condicao(chave), "bi-cloud-fill")
