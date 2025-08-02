"""
Конфигурация приложения
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
# Это должно быть в самом верху, до первого обращения к os.getenv
load_dotenv()

class Settings:
    # Основные настройки
    APP_NAME: str = "CleanForum"
    APP_VERSION: str = "0.1.0"
    RELOAD: bool = True

    # Настройки логирования
    LOG_FILE: str = "logs/forum.log"

    # Redis настройки
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"
    if TESTING:
        REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6380))
    else:
        REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    # Vector Settings
    VECTOR_INDEX_NAME: str = "forum_posts_index"
    VECTOR_DIM: int = 384  # для all-MiniLM-L6-v2
    SIMILARITY_THRESHOLD: float = 0.25 # Порог для определения похожих постов (чем меньше, тем строже)

    # Spam Detection
    SPAM_THRESHOLD: float = 0.7
    MIN_USER_AGE_DAYS: int = 7  # минимальный возраст аккаунта

    # Секретные ключи (в продакшене использовать переменные окружения)
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("Необходимо установить переменную окружения SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()
