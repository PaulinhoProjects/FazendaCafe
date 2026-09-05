import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template

def get_logger(name='fazenda_cafe'):
    """
    Retorna um logger configurado com handler de arquivo rotativo
    e handler de console. Usa padrão singleton — não duplica handlers.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Formato do log
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler de arquivo (rotativo — 5MB por arquivo, máximo 5 backups)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'fazenda_cafe.log'),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler de console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def register_error_handlers(app):
    """
    Registra handlers de erro globais na aplicação Flask.
    Exibe páginas amigáveis ao usuário e loga os erros em arquivo.
    """
    logger = get_logger()

    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 - Página não encontrada: {error}")
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        logger.warning(f"403 - Acesso negado: {error}")
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 - Erro interno do servidor: {error}", exc_info=True)
        return render_template('errors/500.html'), 500

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        logger.error(f"Erro não tratado: {error}", exc_info=True)
        return render_template('errors/500.html'), 500
