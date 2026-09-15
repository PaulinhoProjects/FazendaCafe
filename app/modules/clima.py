"""
Módulo de Clima e Previsão do Tempo
Integração com OpenWeatherMap API
"""

import requests
from datetime import datetime, timedelta
import os

# Configurações
API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
CIDADE = "Campos Gerais"
UF = "MG"
PAIS = "BR"

# Cache de 30 minutos para reduzir chamadas à API
_CACHE = {'clima': None, 'previsao': None, 'timestamp': None}
TEMPO_CACHE_SEGUNDOS = 30 * 60

def _cache_valido():
    if _CACHE['timestamp'] is None:
        return False
    return (datetime.now() - _CACHE['timestamp']).total_seconds() < TEMPO_CACHE_SEGUNDOS

def get_coordenadas(cidade, uf, pais):
    """Obtém coordenadas da cidade"""
    try:
        url = f"https://api.openweathermap.org/geo/1.0/direct?q={cidade},{uf},{pais}&limit=1&appid={API_KEY}"
        response = requests.get(url)
        data = response.json()

        if data and len(data) > 0:
            return {
                'lat': data[0]['lat'],
                'lon': data[0]['lon'],
                'nome': data[0]['name']
            }
        return None
    except Exception as e:
        print(f"Erro ao obter coordenadas: {e}")
        return None

def _vento_cardinal(graus):
    """Converte graus (0-360) em direção cardinal (N, NE, L, SE...)."""
    direcoes = ['N', 'NE', 'L', 'SE', 'S', 'SO', 'O', 'NO']
    if graus is None:
        return '-'
    try:
        idx = int(((graus % 360) + 22.5) // 45) % 8
        return direcoes[idx]
    except (TypeError, ValueError):
        return '-'

def get_clima_atual():
    """Obtém clima atual com dados completos para o dashboard."""
    try:
        coords = get_coordenadas(CIDADE, UF, PAIS)
        if not coords:
            return None

        url = f"https://api.openweathermap.org/data/2.5/weather?lat={coords['lat']}&lon={coords['lon']}&appid={API_KEY}&units=metric&lang=pt_br"
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code == 200:
            vento_deg = data['wind'].get('deg')
            clima = {
                'cidade': coords['nome'],
                'temperatura': round(data['main']['temp'], 1),
                'sensacao': round(data['main']['feels_like'], 1),
                'temp_min': round(data['main'].get('temp_min', data['main']['temp']), 1),
                'temp_max': round(data['main'].get('temp_max', data['main']['temp']), 1),
                'umidade': data['main']['humidity'],
                'pressao': data['main']['pressure'],
                'nebulosidade': data.get('clouds', {}).get('all', 0),
                'vento_velocidade': round(data['wind']['speed'] * 3.6, 1),
                'vento_direcao': vento_deg if vento_deg is not None else 0,
                'vento_cardinal': _vento_cardinal(vento_deg),
                'descricao': data['weather'][0]['description'].capitalize(),
                'condition': data['weather'][0]['main'],
                'nascer_sol': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%H:%M'),
                'por_sol': datetime.fromtimestamp(data['sys']['sunset']).strftime('%H:%M'),
                'atualizacao': datetime.now().strftime('%H:%M')
            }

            clima['alertas'] = gerar_alertas(clima)
            return clima
        else:
            print(f"Erro na API de clima. Código: {response.status_code}")
            return None

    except Exception as e:
        print(f"Exceção ao buscar clima: {e}")
        return None

def get_previsao():
    """Obtém previsão para os próximos dias."""
    try:
        coords = get_coordenadas(CIDADE, UF, PAIS)
        if not coords:
            return None

        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={coords['lat']}&lon={coords['lon']}&appid={API_KEY}&units=metric&lang=pt_br"
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code == 200:
            previsoes = []
            dias_vistos = set()

            for item in data['list']:
                data_hora = datetime.fromtimestamp(item['dt'])
                dia = data_hora.strftime('%Y-%m-%d')
                if dia not in dias_vistos and 11 <= data_hora.hour <= 14:
                    dias_vistos.add(dia)
                    previsoes.append({
                        'data': data_hora.strftime('%d/%m'),
                        'dia_semana': data_hora.strftime('%A').capitalize(),
                        'temp_min': round(item['main']['temp_min'], 1),
                        'temp_max': round(item['main']['temp_max'], 1),
                        'umidade': item['main']['humidity'],
                        'descricao': item['weather'][0]['description'].capitalize(),
                        'condition': item['weather'][0]['main'],
                        'chuva': round(item.get('rain', {}).get('3h', 0), 1),
                        'vento': round(item['wind']['speed'] * 3.6, 1)
                    })
                    if len(previsoes) >= 5:
                        break

            return previsoes
        return None
    except Exception as e:
        print(f"Erro ao buscar previsão: {e}")
        return None

def gerar_alertas(clima):
    """Gera alertas baseados nas condições climáticas"""
    alertas = []
    
    # Alerta de frio
    if clima['temperatura'] < 10:
        alertas.append({
            'tipo': 'frio',
            'severidade': 'alto',
            'mensagem': f'Temperatura baixa: {clima["temperatura"]}°C. Proteja as plantas!'
        })
    elif clima['temperatura'] < 15:
        alertas.append({
            'tipo': 'frio',
            'severidade': 'medio',
            'mensagem': f'Temperatura amena: {clima["temperatura"]}°C. Fique atento.'
        })
    
    # Alerta de calor extremo
    if clima['temperatura'] > 35:
        alertas.append({
            'tipo': 'calor',
            'severidade': 'alto',
            'mensagem': f'Calor intenso: {clima["temperatura"]}°C. Risco de estresse hídrico!'
        })
    elif clima['temperatura'] > 30:
        alertas.append({
            'tipo': 'calor',
            'severidade': 'medio',
            'mensagem': f'Temperatura elevada: {clima["temperatura"]}°C.'
        })
    
    # Alerta de chuva
    if 'chuva' in clima or clima.get('codigo') == 'Rain':
        alertas.append({
            'tipo': 'chuva',
            'severidade': 'medio',
            'mensagem': 'Chuva prevista. Evite pulverizações.'
        })
    
    # Alerta de vento forte
    if clima['vento_velocidade'] > 40:
        alertas.append({
            'tipo': 'vento',
            'severidade': 'alto',
            'mensagem': f'Ventos fortes: {clima["vento_velocidade"]} km/h. Cuidado com aplicações!'
        })
    elif clima['vento_velocidade'] > 25:
        alertas.append({
            'tipo': 'vento',
            'severidade': 'medio',
            'mensagem': f'Ventos moderados: {clima["vento_velocidade"]} km/h.'
        })
    
    # Alerta de umidade baixa
    if clima['umidade'] < 30:
        alertas.append({
            'tipo': 'umidade',
            'severidade': 'alto',
            'mensagem': f'Umidade muito baixa: {clima["umidade"]}%. Risco de incêndio!'
        })
    elif clima['umidade'] < 50:
        alertas.append({
            'tipo': 'umidade',
            'severidade': 'baixo',
            'mensagem': f'Umidade baixa: {clima["umidade"]}%.'
        })
    
    return alertas

def get_icone_clima(codigo):
    """Retorna ícone Bootstrap baseado no código do clima"""
    icones = {
        'Clear': 'bi-brightness-high',
        'Clouds': 'bi-cloud',
        'Rain': 'bi-cloud-rain',
        'Drizzle': 'bi-cloud-drizzle',
        'Thunderstorm': 'bi-cloud-lightning-rain',
        'Snow': 'bi-snow',
        'Mist': 'bi-cloud-haze',
        'Fog': 'bi-cloud-haze2',
        'default': 'bi-cloud'
    }
    return icones.get(codigo, icones['default'])