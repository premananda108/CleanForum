"""
Модель поста
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid
import json
from models.database import db
from config import settings

class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    MODERATED = "moderated"
    SPAM = "spam"
    DELETED = "deleted"

class PostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10)
    category_id: str
    tags: List[str] = Field(default_factory=list, max_items=10)

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_items=10)

class PostResponse(BaseModel):
    id: str
    title: str
    content: str
    category_id: str
    category_name: str = ""
    author_id: str
    author_username: str = ""
    tags: List[str]
    status: PostStatus
    created_at: datetime
    updated_at: datetime
    view_count: int = 0
    comment_count: int = 0
    vote_score: int = 0
    is_spam: bool = False
    spam_score: float = 0.0
    reading_time: int = 0  # в минутах
    similar_posts: Optional[List['PostResponse']] = None

class Post:
    """Класс для работы с постами"""

    @staticmethod
    def calculate_reading_time(content: str) -> int:
        """Рассчитать время чтения (примерно 200 слов в минуту)"""
        word_count = len(content.split())
        return max(1, word_count // 200)

    @staticmethod
    async def create(post_data: PostCreate, author_id: str) -> Optional[str]:
        """
        Создать новый пост с немедленным анализом на спам.
        Если пост определен как спам, он не сохраняется и возвращается None.
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()

        # Сначала проводим анализ, чтобы получить оценку спама
        from services.vector_classifier import vector_classifier
        analysis_results = await vector_classifier.analyze_with_vectors(
            post_id, post_data.title, post_data.content, post_data.tags, author_id
        )

        is_spam = analysis_results.get("is_spam", False)

        # Если пост - спам, не сохраняем его
        if is_spam:
            import logging
            logging.warning(f"Пост от {author_id} с заголовком '{post_data.title}' определен как спам и не будет сохранен.")
            # Можно дополнительно сохранить информацию о спаме для анализа
            # await db.hset(f"spam_attempt:{post_id}", mapping=analysis_results)
            return None

        spam_score = analysis_results.get("spam_score", 0.0)
        status = PostStatus.PUBLISHED

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": post_data.content,
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": 0,
            "comment_count": 0,
            "vote_score": 0,
            "is_spam": str(is_spam), # будет всегда False здесь
            "spam_score": spam_score,
            "reading_time": Post.calculate_reading_time(post_data.content)
        }

        # Сохраняем пост и его анализ в одной транзакции
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = now.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            await pipe.execute()

        return post_id

    @staticmethod
    async def get_by_id(post_id: str, increment_views: bool = False) -> Optional[PostResponse]:
        """Получить пост по ID"""
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return None

        # Увеличиваем счетчик просмотров
        if increment_views:
            new_view_count = int(post_data.get("view_count", 0)) + 1
            await db.hset(f"post:{post_id}", {"view_count": new_view_count})
            post_data["view_count"] = str(new_view_count)

        # Получаем дополнительную информацию
        from models.category import Category
        from models.user import User

        category = await Category.get_by_id(post_data["category_id"])
        author = await User.get_by_id(post_data["author_id"])

        return PostResponse(
            id=post_data["id"],
            title=post_data["title"],
            content=post_data["content"],
            category_id=post_data["category_id"],
            category_name=category.name if category else "Unknown",
            author_id=post_data["author_id"],
            author_username=author.username if author else "Unknown",
            tags=json.loads(post_data.get("tags", "[]")),
            status=PostStatus(post_data["status"]),
            created_at=datetime.fromisoformat(post_data["created_at"]),
            updated_at=datetime.fromisoformat(post_data["updated_at"]),
            view_count=int(post_data.get("view_count", 0)),
            comment_count=int(post_data.get("comment_count", 0)),
            vote_score=int(post_data.get("vote_score", 0)),
            is_spam=post_data.get("is_spam", "False") == "True",
            spam_score=float(post_data.get("spam_score", 0.0)),
            reading_time=int(post_data.get("reading_time", 1))
        )

    @staticmethod
    async def get_all(limit: int = 20, offset: int = 0) -> List[PostResponse]:
        """Получить список постов"""
        # Получаем ID постов, отсортированных по времени создания
        post_ids = await db.zrevrange("posts:all", offset, offset + limit - 1)

        posts = []
        for post_id in post_ids:
            post = await Post.get_by_id(post_id)
            if post and post.status == PostStatus.PUBLISHED:
                posts.append(post)

        return posts

    @staticmethod
    async def get_by_category(category_id: str, limit: int = 20, offset: int = 0) -> List[PostResponse]:
        """Получить посты по категории"""
        post_ids = await db.zrevrange(f"posts:category:{category_id}", offset, offset + limit - 1)

        posts = []
        for post_id in post_ids:
            post = await Post.get_by_id(post_id)
            if post and post.status == PostStatus.PUBLISHED:
                posts.append(post)

        return posts

    @staticmethod
    async def get_all_for_moderation(limit: int = 50, offset: int = 0) -> List[PostResponse]:
        """Получить все посты для модерации, включая спам."""
        post_ids = await db.zrevrange("posts:all", offset, offset + limit - 1)

        posts = []
        for post_id in post_ids:
            post = await Post.get_by_id(post_id)
            if post:
                posts.append(post)
        return posts

    @staticmethod
    async def update(post_id: str, post_data: PostUpdate) -> bool:
        """Обновить пост"""
        existing_data = await db.hgetall(f"post:{post_id}")
        if not existing_data:
            return False

        update_fields = {}

        if post_data.title is not None:
            update_fields["title"] = post_data.title
        if post_data.content is not None:
            update_fields["content"] = post_data.content
            update_fields["reading_time"] = Post.calculate_reading_time(post_data.content)
        if post_data.category_id is not None:
            update_fields["category_id"] = post_data.category_id
        if post_data.tags is not None:
            update_fields["tags"] = json.dumps(post_data.tags)

        if update_fields:
            update_fields["updated_at"] = datetime.now().isoformat()
            await db.hset(f"post:{post_id}", update_fields)

        return True

    @staticmethod
    async def mark_as_spam(post_id: str, spam_score: float, is_spam: bool = True):
        """Отметить пост как спам и обновить его статус."""
        status = PostStatus.SPAM.value if is_spam else PostStatus.PUBLISHED.value
        await db.hset(f"post:{post_id}", {
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "status": status
        })

        if is_spam:
            await db.sadd("posts:spam", post_id)
        else:
            await db.srem("posts:spam", post_id)

    @staticmethod
    async def update_comment_count(post_id: str, delta: int = 1):
        """Обновить количество комментариев"""
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return

        new_count = int(post_data.get("comment_count", 0)) + delta
        await db.hset(f"post:{post_id}", {"comment_count": max(0, new_count)})

    @staticmethod
    async def count_all() -> int:
        """Подсчитать общее количество постов."""
        return await db.zcard("posts:all")

    @staticmethod
    async def count_spam() -> int:
        """Подсчитать количество спам-постов."""
        return await db.scard("posts:spam")

    @staticmethod
    async def get_similar_posts(post_id: str, limit: int = 5) -> List['PostResponse']:
        """Найти похожие посты, используя векторный поиск"""
        from services.redis_manager import vector_manager

        # 1. Получаем вектор для текущего поста
        post_vector = await vector_manager.get_vector_by_id(post_id)
        if post_vector is None:
            return []

        # 2. Ищем похожие посты. Запрашиваем на один больше, т.к. сам пост может вернуться
        similar_results = await vector_manager.search_similar(post_vector, k=limit + 1)

        # 3. Фильтруем и получаем посты
        similar_posts = []
        for result in similar_results:
            # Пропускаем сам пост
            if result['doc_id'] == post_id:
                continue

            # Получаем данные поста
            post = await Post.get_by_id(result['doc_id'])
            if post and post.status == PostStatus.PUBLISHED:
                similar_posts.append(post)

            # Прерываем, если набрали нужное количество
            if len(similar_posts) >= limit:
                break

        return similar_posts


    @staticmethod
    async def search_by_text(query: str, limit: int = 20, offset: int = 0) -> List['PostResponse']:
        """Полнотекстовый поиск постов с использованием RediSearch."""

        # Экранируем спецсимволы, которые могут сломать запрос RediSearch
        terms = query.replace("-", "\\-").split()

        # Для каждого слова создаем отдельный блок запроса для поиска в обоих полях
        # например, (@title:word*|@content:word*)
        sub_queries = []
        for term in terms:
            if term: # Пропускаем пустые строки, если есть двойные пробелы
                sub_queries.append(f"(@title:{term}*|@content:{term}*)")

        # Объединяем подзапросы через ИЛИ
        if not sub_queries:
            return []
        redis_query = "|".join(sub_queries)

        try:
            # Выполняем поиск, возвращая только doc_id
            search_results = await db.redis_client.execute_command(
                "FT.SEARCH",
                settings.VECTOR_INDEX_NAME,
                redis_query,
                "LIMIT", offset, limit,
                "RETURN", "1", "doc_id"
            )
        except Exception as e:
            # В случае ошибки (например, индекс не создан) возвращаем пустой список
            import logging
            logging.error(f"Ошибка полнотекстового поиска: {e}")
            return []

        # Результат: [количество_результатов, doc_id_1, ['doc_id', 'vector:uuid'], ...]
        if not search_results or search_results[0] == 0:
            return []

        # Извлекаем ID постов из результата
        post_ids = [
            result[1].replace("vector:", "")
            for result in search_results[1:]
        ]

        # Получаем полные данные постов по найденным ID
        posts = []
        for post_id in post_ids:
            post = await Post.get_by_id(post_id)
            # Добавляем только опубликованные посты
            if post and post.status == PostStatus.PUBLISHED:
                posts.append(post)

        return posts


# Это нужно для обновления ссылок в Pydantic моделях после определения всех классов
PostResponse.model_rebuild()
