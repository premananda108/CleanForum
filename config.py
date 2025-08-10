"""
Application Configuration
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
# This should be at the very top, before the first call to os.getenv
load_dotenv()

class Settings:
    # Main settings
    APP_NAME: str = "CleanForum"
    APP_VERSION: str = "0.4.0"
    RELOAD: bool = True

    # Logging settings
    LOG_FILE: str = "logs/forum.log"

    # Redis settings
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"
    if TESTING:
        REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6380))
    else:
        REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    # Vector Settings
    VECTOR_INDEX_NAME: str = "forum_posts_index"
    VECTOR_DIM: int = 384  # for all-MiniLM-L6-v2
    SIMILARITY_THRESHOLD: float = 0.5 # Threshold for determining similar posts (the lower, the stricter)

    # Spam Detection
    SPAM_THRESHOLD: float = 0.7
    MIN_USER_AGE_DAYS: int = 7  # minimum account age

    # Secret keys (use environment variables in production)
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("The SECRET_KEY environment variable must be set")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()