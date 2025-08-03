import pytest
import pytest_asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from models.user import User, UserCreate
from models.category import Category, CategoryCreate
from models.post import Post, PostCreate, PostUpdate, PostStatus
from config import settings
from models.database import db
from services.redis_manager import vector_manager
from services.vector_classifier import vector_classifier


# Фикстура для создания тестового пользователя и категории
@pytest_asyncio.fixture(scope="function")
async def setup_data(monkeypatch):
    # Принудительно устанавливаем тестовые настройки
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    # Подключаемся к основной БД и к менеджеру векторов
    await db.connect()
    await vector_manager.connect()

    # Очищаем основную БД и удаляем/создаем индекс
    await db.flush_db()
    try:
        await vector_manager.redis_client.execute_command("FT.DROPINDEX", settings.VECTOR_INDEX_NAME, "DD")
    except Exception as e:
        if "no such index" not in str(e).lower():
            raise e
    await vector_manager.create_index()

    # Создаем пользователя
    user_data = UserCreate(username="testuser_posts", email="test_posts@example.com", password="password123")
    user_id = await User.create(user_data)

    # Создаем категорию
    category_data = CategoryCreate(name="Test Category", description="A category for testing")
    category_id = await Category.create(category_data)

    yield user_id, category_id

    # Отключаемся от БД
    await vector_manager.disconnect()
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


@pytest.mark.asyncio
async def test_update_post(setup_data, monkeypatch):
    """Тест успешного обновления поста."""
    user_id, category_id = setup_data

    # Мокаем анализ спама для создания и обновления
    mock_analyze = AsyncMock(return_value={"is_spam": False, "spam_score": 0.1})
    monkeypatch.setattr("services.vector_classifier.vector_classifier.analyze_with_vectors", mock_analyze)

    # 1. Создаем пост для обновления
    initial_post_data = PostCreate(
        title="Original Title",
        content='{"blocks": [{"data": {"text": "Original content."}}]}',
        category_id=category_id,
        tags=["original"]
    )
    post_id = await Post.create(initial_post_data, author_id=user_id)
    assert post_id is not None

    # 2. Обновляем пост
    update_data = PostUpdate(
        title="Updated Title",
        content='{"blocks": [{"data": {"text": "Updated content."}}]}'
    )
    success = await Post.update(post_id, update_data)
    assert success is True

    # 3. Проверяем, что данные обновились
    updated_post = await Post.get_by_id(post_id)
    assert updated_post is not None
    assert updated_post.title == "Updated Title"
    assert "Updated content." in updated_post.content
    # Проверяем, что updated_at изменилось (с небольшой погрешностью)
    from datetime import datetime, timedelta
    assert updated_post.updated_at > updated_post.created_at
    assert updated_post.updated_at > (datetime.now() - timedelta(seconds=5))


@pytest.mark.asyncio
async def test_search_by_text(setup_data, monkeypatch):
    """Тест полнотекстового поиска по постам."""
    user_id, category_id = setup_data

    # Мокаем создание вектора, чтобы не использовать реальную ML модель
    mock_create_vector = MagicMock(return_value=np.random.rand(settings.VECTOR_DIM).astype(np.float32))
    monkeypatch.setattr("services.vector_classifier.VectorSpamClassifier.create_vector", mock_create_vector)

    # Мокаем эвристический анализ, чтобы он не помечал пост как спам
    mock_heuristic = AsyncMock(return_value={"is_spam": False, "spam_score": 0.1, "reasons": []})
    monkeypatch.setattr("services.spam_detector.spam_detector.analyze_post", mock_heuristic)

    # Мокаем векторный поиск, т.к. в индексе еще ничего нет
    mock_vector_search = AsyncMock(return_value=[])
    monkeypatch.setattr("services.redis_manager.vector_manager.search_similar", mock_vector_search)

    # 1. Создаем несколько постов для поиска
    post1_data = PostCreate(
        title="First post about Python",
        content='{"blocks": [{"data": {"text": "This is a post about Python language"}}]}',
        category_id=category_id, tags=[]
    )
    post1_id = await Post.create(post1_data, user_id)

    post2_data = PostCreate(
        title="Second post about FastAPI",
        content='{"blocks": [{"data": {"text": "FastAPI is a modern web framework for Python"}}]}',
        category_id=category_id, tags=[]
    )
    post2_id = await Post.create(post2_data, user_id)

    post3_data = PostCreate(
        title="A post about Redis",
        content='{"blocks": [{"data": {"text": "Redis is an in-memory data store"}}]}',
        category_id=category_id, tags=[]
    )
    await Post.create(post3_data, user_id)

    # Небольшая задержка, чтобы Redis успел проиндексировать
    import asyncio
    await asyncio.sleep(3)

    # 2. Тестируем поиск
    # Поиск по одному слову в заголовке
    results_python = await Post.search_by_text("Python")
    assert len(results_python) == 2
    assert {p.id for p in results_python} == {post1_id, post2_id}

    # Поиск по одному слову в контенте
    results_framework = await Post.search_by_text("framework")
    assert len(results_framework) == 1
    assert results_framework[0].id == post2_id

    # Поиск, который ничего не должен найти
    results_none = await Post.search_by_text("nonexistentword")
    assert len(results_none) == 0
