import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import settings

def setup_logging():
    """Logging system setup."""
    # Check if handlers have already been added to avoid duplication
    if logging.getLogger().hasHandlers():
        return

    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s'
    )
    
    # Create an absolute path to the log file
    log_file_path = Path(settings.LOG_FILE)
    log_file_path.parent.mkdir(parents=True, exist_ok=True) # Create the directory if it doesn't exist

    # File handler setup with rotation
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=2,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    # Console handler setup
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG if settings.RELOAD else logging.INFO)

    # Get the root logger and configure it
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce verbosity from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info("Logging system configured.")
    logging.is_configured = True