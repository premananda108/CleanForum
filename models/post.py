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

class Post:
    """Класс для работы с постами"""

    @staticmethod
    def calculate_reading_time(content: str) -> int:
        """Рассчитать время чтения (примерно 200 слов в минуту)"""
        word_count = len(content.split())
        return max(1, word_count // 200)

    @staticmethod
    async def create(post_data: PostCreate, author_id: str) -> str:
        """Создать новый пост"""
        post_id = str(uuid.uuid4())
        now = datetime.now()

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": post_data.content,
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": PostStatus.PUBLISHED.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": 0,
            "comment_count": 0,
            "vote_score": 0,
            "is_spam": False,
            "spam_score": 0.0,
            "reading_time": Post.calculate_reading_time(post_data.content)
        }

        # Сохраняем пост
        await db.hset(f"post:{post_id}", post_info)

        # Добавляем в индексы
        timestamp = now.timestamp()
        await db.zadd("posts:all", {post_id: timestamp})
        await db.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
        await db.zadd(f"posts:author:{author_id}", {post_id: timestamp})

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

    @staticmethod
    async def update_comment_count(post_id: str, delta: int = 1):
        """Обновить количество комментариев"""
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return

        new_count = int(post_data.get("comment_count", 0)) + delta
        await db.hset(f"post:{post_id}", {"comment_count": max(0, new_count)})
