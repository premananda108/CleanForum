import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import settings

def setup_logging():
    """Настройка системы логирования."""
    # Проверяем, были ли уже добавлены обработчики, чтобы избежать дублирования
    if logging.getLogger().hasHandlers():
        return

    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s'
    )
    
    # Создаем абсолютный путь к файлу лога
    log_file_path = Path(settings.LOG_FILE)
    log_file_path.parent.mkdir(parents=True, exist_ok=True) # Создаем директорию, если ее нет

    # Настройка файлового обработчика с ротацией
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=2,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    # Настройка консольного обработчика
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG if settings.RELOAD else logging.INFO)

    # Получаем корневой логгер и настраиваем его
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Уменьшаем многословность от сторонних библиотек
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info("Система логирования настроена.")
