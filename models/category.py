"""
Модель категории
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from models.database import db

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., max_length=500)
    color: str = Field(default="#007bff")  # Bootstrap цвет по умолчанию

class CategoryResponse(BaseModel):
    id: str
    name: str
    description: str
    color: str
    post_count: int = 0
    created_at: datetime
    is_active: bool = True

class Category:
    """Класс для работы с категориями"""

    @staticmethod
    async def create(category_data: CategoryCreate) -> str:
        """Создать новую категорию"""
        category_id = str(uuid.uuid4())

        # Проверяем уникальность имени
        if await Category.get_by_name(category_data.name):
            raise ValueError("Категория с таким названием уже существует")

        category_info = {
            "id": category_id,
            "name": category_data.name,
            "description": category_data.description,
            "color": category_data.color,
            "post_count": 0,
            "created_at": datetime.now().isoformat(),
            "is_active": True
        }

        # Сохраняем категорию
        await db.hset(f"category:{category_id}", category_info)

        # Создаем индекс для поиска по имени
        await db.set(f"category_name:{category_data.name}", category_id)

        # Добавляем в список всех категорий
        await db.zadd("categories:all", {category_id: datetime.now().timestamp()})

        return category_id

    @staticmethod
    async def get_by_id(category_id: str) -> Optional[CategoryResponse]:
        """Получить категорию по ID"""
        category_data = await db.hgetall(f"category:{category_id}")
        if not category_data:
            return None

        return CategoryResponse(
            id=category_data["id"],
            name=category_data["name"],
            description=category_data["description"],
            color=category_data["color"],
            post_count=int(category_data.get("post_count", 0)),
            created_at=datetime.fromisoformat(category_data["created_at"]),
            is_active=category_data.get("is_active", "True") == "True"
        )

    @staticmethod
    async def get_by_name(name: str) -> Optional[CategoryResponse]:
        """Получить категорию по имени"""
        category_id = await db.get(f"category_name:{name}")
        if not category_id:
            return None
        return await Category.get_by_id(category_id)

    @staticmethod
    async def get_all() -> List[CategoryResponse]:
        """Получить все активные категории"""
        category_ids = await db.zrevrange("categories:all")
        categories = []

        for category_id in category_ids:
            category = await Category.get_by_id(category_id)
            if category and category.is_active:
                categories.append(category)

        return categories

    @staticmethod
    async def update_post_count(category_id: str, delta: int = 1):
        """Обновить количество постов в категории"""
        category_data = await db.hgetall(f"category:{category_id}")
        if not category_data:
            return

        new_count = int(category_data.get("post_count", 0)) + delta
        await db.hset(f"category:{category_id}", {"post_count": max(0, new_count)})
