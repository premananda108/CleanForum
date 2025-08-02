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
    tags: List[str] = Field(default_factory=list, max_length=10)

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_length=10)

class PostResponse(BaseModel):
    id: str
    title: str
    content: str  # Это будет чистый текст для превью и SEO
    content_json: Optional[str] = None  # Это будет исходный JSON от EditorJS для рендеринга
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
    def _extract_text_from_editorjs(content: str) -> str:
        """Извлекает чистый текст из JSON-структуры Editor.js."""
        try:
            data = json.loads(content)
            # Собираем текст из всех блоков, где он может быть
            text_parts = []
            for block in data.get('blocks', []):
                block_data = block.get('data', {})
                text = block_data.get('text', '')
                if text:
                    text_parts.append(text)
                # Дополнительно можно обрабатывать списки, заголовки и т.д.
                items = block_data.get('items', [])
                if items:
                    text_parts.extend(items)
            return " ".join(text_parts)
        except (json.JSONDecodeError, TypeError):
            # Если это не JSON, возвращаем как есть
            return content

    @staticmethod
    def calculate_reading_time(text_content: str) -> int:
        """Рассчитать время чтения (примерно 200 слов в минуту) на основе чистого текста."""
        word_count = len(text_content.split())
        return max(1, word_count // 200)

    @staticmethod
    async def create(post_data: PostCreate, author_id: str) -> Optional[str]:
        """
        Создать новый пост с немедленным анализом на спам.
        Если пост определен как спам, он не сохраняется и возвращается None.
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()

        # Извлекаем чистый текст для анализа, поиска и вычисления времени чтения
        text_for_analysis = Post._extract_text_from_editorjs(post_data.content)

        # Проводим анализ на спам
        from services.vector_classifier import vector_classifier
        analysis_results = await vector_classifier.analyze_with_vectors(
            post_id, post_data.title, text_for_analysis, post_data.tags, author_id
        )

        is_spam = analysis_results.get("is_spam", False)

        # Если пост - спам, не сохраняем его
        if is_spam:
            import logging
            spam_score = analysis_results.get("spam_score", 0.0)
            logging.warning(f"Пост от {author_id} определен как СПАМ (score: {spam_score:.2f}) и не будет сохранен.")
            return None

        spam_score = analysis_results.get("spam_score", 0.0)
        status = PostStatus.PUBLISHED

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": text_for_analysis,  # Чистый текст для поиска и превью
            "content_json": post_data.content,  # Исходный JSON для рендеринга
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": 0,
            "comment_count": 0,
            "vote_score": 0,
            "is_spam": str(is_spam), # будет всегда False
            "spam_score": spam_score,
            "reading_time": Post.calculate_reading_time(text_for_analysis)
        }

        # Сохраняем пост
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = now.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
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
            content_json=post_data.get("content_json"),
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
        reanalyze_spam = False

        if post_data.title is not None:
            update_fields["title"] = post_data.title
            reanalyze_spam = True
        if post_data.content is not None:
            text_content = Post._extract_text_from_editorjs(post_data.content)
            update_fields["content"] = text_content
            update_fields["content_json"] = post_data.content
            update_fields["reading_time"] = Post.calculate_reading_time(text_content)
            reanalyze_spam = True
        if post_data.category_id is not None:
            update_fields["category_id"] = post_data.category_id
        if post_data.tags is not None:
            update_fields["tags"] = json.dumps(post_data.tags)
            reanalyze_spam = True

        if update_fields:
            update_fields["updated_at"] = datetime.now().isoformat()
            # Сбрасываем статус спама при любом обновлении, чтобы запустить повторную проверку
            if reanalyze_spam:
                update_fields["is_spam"] = str(False)
                update_fields["spam_score"] = 0.0
                update_fields["status"] = PostStatus.PUBLISHED.value
            
            await db.hset(f"post:{post_id}", mapping=update_fields)

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
    async def mark_as_deleted(post_id: str) -> bool:
        """
        Помечает пост как удаленный (мягкое удаление).
        Удаляет пост из всех списков, обновляет счетчики и удаляет вектор.
        """
        # 1. Получаем данные поста, чтобы знать author_id и category_id
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return False  # Пост не найден

        author_id = post_data.get("author_id")
        category_id = post_data.get("category_id")

        # 2. Используем транзакцию для атомарности
        async with db.redis_client.pipeline(transaction=True) as pipe:
            # Помечаем пост как удаленный
            pipe.hset(f"post:{post_id}", "status", PostStatus.DELETED.value)

            # Удаляем ID поста из всех отсортированных множеств
            pipe.zrem("posts:all", post_id)
            if category_id:
                pipe.zrem(f"posts:category:{category_id}", post_id)
            if author_id:
                pipe.zrem(f"posts:author:{author_id}", post_id)

            # Удаляем из множества спама, если он там был
            pipe.srem("posts:spam", post_id)

            # Выполняем транзакцию
            await pipe.execute()

        # 3. Обновляем счетчик постов в категории (вне транзакции)
        if category_id:
            from models.category import Category
            await Category.update_post_count(category_id, -1)

        # 4. Удаляем вектор из поискового индекса (вне транзакции)
        from services.redis_manager import vector_manager
        await vector_manager.delete_vector(f"post:{post_id}")
        
        import logging
        logging.info(f"Пост {post_id} был помечен как удаленный.")

        return True

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
        """Найти похожие посты, используя векторный поиск с фильтрацией по статусу."""
        import logging
        from services.redis_manager import vector_manager

        logging.info(f"Начинаем поиск похожих постов для post_id: {post_id}")

        vector_doc_id = f"post:{post_id}"
        post_vector = await vector_manager.get_vector_by_id(vector_doc_id)

        if post_vector is None:
            logging.warning(f"Вектор для {vector_doc_id} не найден. Невозможно найти похожие посты.")
            return []

        logging.info(f"Вектор для {vector_doc_id} успешно получен.")

        # Ищем похожие посты, фильтруя только опубликованные (`published`)
        try:
            # Запрашиваем на один больше, т.к. сам пост может вернуться
            similar_results = await vector_manager.search_similar(
                post_vector, 
                k=limit + 1, 
                pre_filter={"label": PostStatus.PUBLISHED.value}
            )
            logging.info(f"Найдено {len(similar_results)} похожих и опубликованных результатов для {vector_doc_id}.")
        except Exception as e:
            logging.error(f"Ошибка при поиске похожих векторов для {vector_doc_id}: {e}", exc_info=True)
            return []

        similar_posts = []
        for result in similar_results:
            # Пропускаем сам пост
            similar_post_id = result.get('doc_id', '').replace('post:', '')
            if not similar_post_id or similar_post_id == post_id:
                continue

            # Проверяем порог схожести
            score = result.get('score', 1.0)
            if score > settings.SIMILARITY_THRESHOLD:
                continue

            post = await Post.get_by_id(similar_post_id)
            if post:
                similar_posts.append(post)
            else:
                logging.warning(f"Не удалось получить данные для похожего поста {similar_post_id}, хотя он был найден в поиске.")

            if len(similar_posts) >= limit:
                break
        
        logging.info(f"Возвращаем {len(similar_posts)} похожих постов для {post_id}.")
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
