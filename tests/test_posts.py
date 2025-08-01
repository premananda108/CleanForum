import pytest
import httpx
import asyncio
import os

# Устанавливаем переменную окружения для тестов
os.environ['TESTING'] = 'true'

from main import app
from models.database import db
from services.redis_manager import vector_manager # Импортируем vector_manager

@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        # Очищаем базу данных
        await db.redis_client.flushdb()
        # Создаем поисковый индекс
        await vector_manager.create_index()
        
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client

@pytest.mark.anyio
async def test_get_similar_posts(client: httpx.AsyncClient):
    """
    Тестирует получение похожих постов.
    """
    # --- Подготовка: Создаем категории ---
    category_1_data = {"name": "Технологии", "description": "Все о технологиях"}
    category_2_data = {"name": "Наука", "description": "Все о науке"}

    response_cat_1 = await client.post("/api/categories", json=category_1_data)
    assert response_cat_1.status_code == 200
    category_1 = response_cat_1.json()

    response_cat_2 = await client.post("/api/categories", json=category_2_data)
    assert response_cat_2.status_code == 200
    category_2 = response_cat_2.json()

    # --- Подготовка: Создаем посты ---
    post_a_data = {
        "title": "Лучшие рецепты итальянской пиццы",
        "content": "Секреты теста, соуса и начинок.",
        "category_id": category_1['id'],
        "tags": ["пицца", "рецепты"]
    }
    post_b_data = {
        "title": "Как приготовить идеальное тесто для пиццы",
        "content": "Пошаговый рецепт эластичного теста.",
        "category_id": category_1['id'],
        "tags": ["тесто", "пицца"]
    }
    post_c_data = {
        "title": "Введение в квантовую механику",
        "content": "Кот Шрёдингера и принцип неопределенности.",
        "category_id": category_2['id'],
        "tags": ["физика", "наука"]
    }

    response_a = await client.post("/api/posts", json=post_a_data)
    assert response_a.status_code == 200
    post_a = response_a.json()

    response_b = await client.post("/api/posts", json=post_b_data)
    assert response_b.status_code == 200
    
    response_c = await client.post("/api/posts", json=post_c_data)
    assert response_c.status_code == 200

    await asyncio.sleep(2) # Пауза для индексации

    # --- Действие: Получаем пост А и проверяем похожие ---
    response_get_a = await client.get(f"/api/posts/{post_a['id']}")
    assert response_get_a.status_code == 200
    post_a_details = response_get_a.json()

    # --- Проверка ---
    assert 'similar_posts' in post_a_details
    similar_posts = post_a_details['similar_posts']
    assert isinstance(similar_posts, list)
    assert len(similar_posts) > 0, "Список похожих постов не должен быть пустым"
    
    similar_titles = [p['title'] for p in similar_posts]
    assert post_b_data['title'] in similar_titles, "Похожий пост B не найден"
    assert post_c_data['title'] not in similar_titles, "Непохожий пост C ошибочно найден"