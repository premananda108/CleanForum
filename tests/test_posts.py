
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from models.user import User, UserCreate
from models.category import Category, CategoryCreate
from models.post import Post, PostCreate
from config import settings
from models.database import db

# Фикстура для создания тестового пользователя и категории
@pytest_asyncio.fixture(scope="function")
async def setup_data(monkeypatch):
    # Принудительно устанавливаем тестовые настройки
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    # Подключаемся к БД
    await db.connect()
    # Очищаем БД
    await db.flush_db()

    # Создаем пользователя
    user_data = UserCreate(username="testuser_posts", email="test_posts@example.com", password="password123")
    user_id = await User.create(user_data)

    # Создаем категорию
    category_data = CategoryCreate(name="Test Category", description="A category for testing")
    category_id = await Category.create(category_data)

    yield user_id, category_id

    # Отключаемся от БД
    await db.disconnect()

@pytest.mark.asyncio
async def test_create_post_success(setup_data, monkeypatch):
    """Тест успешного создания поста, который не является спамом."""
    user_id, category_id = setup_data

    # Мокаем (заменяем) функцию анализа на спам, чтобы она всегда возвращала "не спам"
    mock_analyze = AsyncMock(return_value={
        "is_spam": False, 
        "spam_score": 0.1, 
        "details": "Not spam"
    })
    monkeypatch.setattr("services.vector_classifier.vector_classifier.analyze_with_vectors", mock_analyze)

    post_data = PostCreate(
        title="This is a test post title",
        content='{"time": 1629890400000, "blocks": [{"type": "paragraph", "data": {"text": "This is the content of the test post."}}], "version": "2.22.2"}',
        category_id=category_id,
        tags=["test", "pytest"]
    )

    # Создаем пост
    post_id = await Post.create(post_data, author_id=user_id)

    # Проверяем, что пост был создан
    assert post_id is not None

    # Проверяем, что мок был вызван
    mock_analyze.assert_called_once()

    # Получаем пост из БД и проверяем его данные
    created_post = await Post.get_by_id(post_id)
    assert created_post is not None
    assert created_post.title == post_data.title
    assert created_post.author_id == user_id
    assert created_post.category_id == category_id
    assert "This is the content of the test post." in created_post.content

@pytest.mark.asyncio
async def test_create_post_is_spam(setup_data, monkeypatch):
    """Тест, в котором пост определяется как спам и не должен быть создан."""
    user_id, category_id = setup_data

    # Мокаем функцию анализа на спам, чтобы она всегда возвращала "спам"
    mock_analyze = AsyncMock(return_value={
        "is_spam": True, 
        "spam_score": 0.9, 
        "details": "This is definitely spam"
    })
    monkeypatch.setattr("services.vector_classifier.vector_classifier.analyze_with_vectors", mock_analyze)

    post_data = PostCreate(
        title="WIN A MILLION DOLLARS NOW!!!",
        content='{"blocks": [{"data": {"text": "Click here for free money!"}}]}',
        category_id=category_id,
        tags=["spam", "money"]
    )

    # Пытаемся создать пост
    post_id = await Post.create(post_data, author_id=user_id)

    # Проверяем, что пост НЕ был создан (должен вернуться None)
    assert post_id is None

    # Проверяем, что мок был вызван
    mock_analyze.assert_called_once()
