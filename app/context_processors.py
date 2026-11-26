"""
Context processors do Kaldi.
Disponibiliza configurações do sistema para todos os templates.
"""
from config.database import get_config

def config_context():
    """Disponibiliza configurações do sistema para todos os templates."""
    configs = {
        'sis_nome': 'Kaldi',
        'sis_slogan': 'Tecnologia que Colhe Resultados',
    }
    try:
        configs['sis_nome'] = get_config('nome_sistema', 'Kaldi') or 'Kaldi'
        configs['sis_slogan'] = get_config('slogan', 'Tecnologia que Colhe Resultados') or 'Tecnologia que Colhe Resultados'
    except Exception:
        pass
    return {'sis_config': configs}