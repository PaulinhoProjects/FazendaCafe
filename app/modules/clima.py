"""
Módulo de Clima e Previsão do Tempo
Integração com OpenWeatherMap API
"""

import requests
from datetime import datetime, timedelta
import os

# Configurações
API_KEY = "386faf8e19c5a12ccf3fc1d9635f3ea0"
CIDADE = "Campos Gerais"
UF = "MG"
PAIS = "BR"

def get_coordenadas(cidade, uf, pais):
    """Obtém coordenadas da cidade"""
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={cidade},{uf},{pais}&limit=1&appid={API_KEY}"
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

def get_clima_atual():
    """Obtém clima atual com prints de debug"""
    print("="*50)
    print("🔍 INICIANDO BUSCA DE CLIMA")
    print("="*50)
    
    try:
        # Primeiro pegar coordenadas
        print(f"📍 Buscando coordenadas para: {CIDADE}, {UF}, {PAIS}")
        coords = get_coordenadas(CIDADE, UF, PAIS)
        
        if not coords:
            print("❌ Não foi possível obter coordenadas")
            return None
            
        print(f"✅ Coordenadas encontradas: {coords}")
        
        # Buscar clima atual
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={coords['lat']}&lon={coords['lon']}&appid={API_KEY}&units=metric&lang=pt_br"
        print(f"🌐 URL da API: {url}")
        
        response = requests.get(url)
        print(f"📡 Status code: {response.status_code}")
        
        data = response.json()
        print(f"📦 Resposta da API: {data}")
        
        if response.status_code == 200:
            print("✅ API respondeu com sucesso!")
            
            clima = {
                'cidade': coords['nome'],
                'temperatura': round(data['main']['temp'], 1),
                'sensacao': round(data['main']['feels_like'], 1),
                'umidade': data['main']['humidity'],
                'pressao': data['main']['pressure'],
                'vento_velocidade': round(data['wind']['speed'] * 3.6, 1),
                'vento_direcao': data['wind']['deg'] if 'deg' in data['wind'] else 0,
                'descricao': data['weather'][0]['description'].capitalize(),
                'icone': data['weather'][0]['icon'],
                'codigo': data['weather'][0]['main'],
                'nascer_sol': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%H:%M'),
                'por_sol': datetime.fromtimestamp(data['sys']['sunset']).strftime('%H:%M'),
                'atualizacao': datetime.now().strftime('%H:%M')
            }
            
            # Adicionar alertas
            clima['alertas'] = gerar_alertas(clima)
            
            print(f"✅ Clima processado: {clima['temperatura']}°C, {clima['descricao']}")
            return clima
        else:
            print(f"❌ Erro na API. Código: {response.status_code}")
            print(f"❌ Mensagem: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Exceção ao buscar clima: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_previsao():
    """Obtém previsão para os próximos dias"""
    try:
        coords = get_coordenadas(CIDADE, UF, PAIS)
        if not coords:
            return None
        
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={coords['lat']}&lon={coords['lon']}&appid={API_KEY}&units=metric&lang=pt_br"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            previsoes = []
            dias_vistos = set()
            
            for item in data['list']:
                data_hora = datetime.fromtimestamp(item['dt'])
                dia = data_hora.strftime('%Y-%m-%d')
                
                # Pegar apenas uma previsão por dia (por volta do meio-dia)
                if dia not in dias_vistos and data_hora.hour >= 11 and data_hora.hour <= 14:
                    dias_vistos.add(dia)
                    
                    previsoes.append({
                        'data': data_hora.strftime('%d/%m'),
                        'dia_semana': data_hora.strftime('%A').capitalize(),
                        'temp_min': round(item['main']['temp_min'], 1),
                        'temp_max': round(item['main']['temp_max'], 1),
                        'umidade': item['main']['humidity'],
                        'descricao': item['weather'][0]['description'].capitalize(),
                        'icone': item['weather'][0]['icon'],
                        'chuva': item.get('rain', {}).get('3h', 0),
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