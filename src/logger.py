import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(base_dir):
    """Setup application loggers"""
    # Create logs directory structure
    logs_dir = os.path.join(base_dir, 'logs')
    info_dir = os.path.join(logs_dir, 'info')
    error_dir = os.path.join(logs_dir, 'error')
    os.makedirs(info_dir, exist_ok=True)
    os.makedirs(error_dir, exist_ok=True)

    # Setup formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Setup INFO logger
    info_logger = logging.getLogger('info')
    info_logger.setLevel(logging.INFO)
    info_handler = RotatingFileHandler(
        os.path.join(info_dir, 'info.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    info_handler.setFormatter(formatter)
    info_logger.addHandler(info_handler)

    # Setup ERROR logger
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    error_handler = RotatingFileHandler(
        os.path.join(error_dir, 'error.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setFormatter(formatter)
    error_logger.addHandler(error_handler)

    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    info_logger.addHandler(console_handler)
    error_logger.addHandler(console_handler)

    return info_logger, error_logger 