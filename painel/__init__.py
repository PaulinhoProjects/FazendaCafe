"""Kaldi Servidor: painel de controle, vigia anti-travamento e servidor de produção."""
import os
import sys


def _pasta_projeto():
    """Pasta do sistema (onde está o run.py). No .exe, é a pasta do executável ou a de cima."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        for candidato in (base, os.path.dirname(base), os.path.dirname(os.path.dirname(base))):
            if os.path.exists(os.path.join(candidato, 'run.py')):
                return candidato
        return base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PASTA_PROJETO = _pasta_projeto()
PASTA_PAINEL = os.path.join(PASTA_PROJETO, 'painel')
ARQUIVO_MANUTENCAO = os.path.join(PASTA_PROJETO, 'storage', 'manutencao.json')
ROTA_INTERNA = '/__kaldi'
VERSAO_PAINEL = '1.0'
