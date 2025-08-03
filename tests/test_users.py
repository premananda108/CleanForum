import pytest
import pytest_asyncio
import asyncio
from models.user import User, UserCreate
from models.database import db
from config import settings

# Фикстура для управления циклом событий asyncio
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Фикстура для управления базой данных
@pytest_asyncio.fixture(scope="function", autouse=True)
async def database(monkeypatch):
    # Принудительно устанавливаем тестовые настройки
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    # Подключаемся к БД перед каждым тестом
    await db.connect()
    # Очищаем БД перед каждым тестом
    await db.flush_db()
    yield
    # Отключаемся от БД после каждого теста
    await db.disconnect()

@pytest.mark.asyncio
async def test_create_user():
    """Тест создания нового пользователя"""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="password123"
    )
    
    # Создаем пользователя
    user_id = await User.create(user_data)
    
    # Проверяем, что пользователь был создан
    assert user_id is not None
    
    # Получаем пользователя по ID
    created_user = await User.get_by_id(user_id)
    
    # Проверяем данные пользователя
    assert created_user is not None
    assert created_user.username == user_data.username
    assert created_user.email == user_data.email