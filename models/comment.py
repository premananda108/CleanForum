"""
Модель комментария
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum
from models.database import db

class CommentStatus(str, Enum):
    """Статус комментария"""
    PUBLISHED = "published"
    MODERATED = "moderated"
    SPAM = "spam"
    DELETED = "deleted"

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    post_id: str

class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentResponse(BaseModel):
    id: str
    content: str
    post_id: str
    author_id: str
    author_username: str = ""
    created_at: datetime
    updated_at: datetime
    vote_score: int = 0
    is_spam: bool = False
    spam_score: float = 0.0
    status: CommentStatus

class Comment:
    """Класс для работы с комментариями"""

    @staticmethod
    async def create(comment_data: CommentCreate, author_id: str) -> str:
        """Создать новый комментарий с немедленным анализом на спам."""
        comment_id = str(uuid.uuid4())
        now = datetime.now()

        # Проводим анализ, чтобы получить оценку спама
        from services.vector_classifier import vector_classifier
        analysis_results = await vector_classifier.analyze_comment(
            comment_id, comment_data.content, author_id
        )

        is_spam = analysis_results.get("is_spam", False)
        spam_score = analysis_results.get("spam_score", 0.0)
        status = CommentStatus.SPAM if is_spam else CommentStatus.PUBLISHED

        comment_info = {
            "id": comment_id,
            "content": comment_data.content,
            "post_id": comment_data.post_id,
            "author_id": author_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "vote_score": 0,
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "status": status.value
        }

        # Сохраняем комментарий и его анализ в одной транзакции
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"comment:{comment_id}", mapping=comment_info)
            timestamp = now.timestamp()
            pipe.zadd("comments:all", {comment_id: timestamp})
            pipe.zadd(f"comments:post:{comment_data.post_id}", {comment_id: timestamp})
            pipe.zadd(f"comments:author:{author_id}", {comment_id: timestamp})
            if is_spam:
                pipe.sadd("comments:spam", comment_id)
            # Обновляем счетчик комментариев в посте
            if not is_spam:
                 pipe.hincrby(f"post:{comment_data.post_id}", "comment_count", 1)
            await pipe.execute()

        return comment_id

    @staticmethod
    async def get_by_id(comment_id: str) -> Optional[CommentResponse]:
        """Получить комментарий по ID"""
        comment_data = await db.hgetall(f"comment:{comment_id}")
        if not comment_data:
            return None

        from models.user import User
        author = await User.get_by_id(comment_data["author_id"])

        return CommentResponse(
            id=comment_data["id"],
            content=comment_data["content"],
            post_id=comment_data["post_id"],
            author_id=comment_data["author_id"],
            author_username=author.username if author else "Unknown",
            created_at=datetime.fromisoformat(comment_data["created_at"]),
            updated_at=datetime.fromisoformat(comment_data["updated_at"]),
            vote_score=int(comment_data.get("vote_score", 0)),
            is_spam=comment_data.get("is_spam", "False") == "True",
            spam_score=float(comment_data.get("spam_score", 0.0)),
            status=CommentStatus(comment_data.get("status", "published"))
        )

    @staticmethod
    async def get_by_post(post_id: str, limit: int = 50, offset: int = 0) -> List[CommentResponse]:
        """Получить комментарии к посту (только опубликованные)"""
        comment_ids = await db.zrange(f"comments:post:{post_id}", offset, offset + limit - 1)

        comments = []
        for comment_id in comment_ids:
            comment = await Comment.get_by_id(comment_id)
            if comment and comment.status == CommentStatus.PUBLISHED:
                comments.append(comment)

        return comments

    @staticmethod
    async def get_all_for_moderation(limit: int = 50, offset: int = 0) -> List[CommentResponse]:
        """Получить все комментарии для модерации, включая спам."""
        comment_ids = await db.zrevrange("comments:all", offset, offset + limit - 1)

        comments = []
        for comment_id in comment_ids:
            comment = await Comment.get_by_id(comment_id)
            if comment:
                comments.append(comment)
        return comments

    @staticmethod
    async def update(comment_id: str, comment_data: CommentUpdate) -> bool:
        """Обновить комментарий"""
        update_fields = {
            "content": comment_data.content,
            "updated_at": datetime.now().isoformat(),
            "status": CommentStatus.PUBLISHED.value, # Сбрасываем статус при обновлении
            "is_spam": str(False),
            "spam_score": 0.0
        }
        await db.hset(f"comment:{comment_id}", mapping=update_fields)
        # Удаляем из спам-листа, если он там был
        await db.srem("comments:spam", comment_id)
        return True

    @staticmethod
    async def mark_as_spam(comment_id: str, spam_score: float, is_spam: bool):
        """Отметить комментарий как спам и обновить его статус."""
        status = CommentStatus.SPAM if is_spam else CommentStatus.PUBLISHED
        await db.hset(f"comment:{comment_id}", mapping={
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "status": status.value
        })

        if is_spam:
            await db.sadd("comments:spam", comment_id)
        else:
            await db.srem("comments:spam", comment_id)

    @staticmethod
    async def count_all() -> int:
        """Подсчитать общее количество комментариев."""
        return await db.zcard("comments:all")

    @staticmethod
    async def count_spam() -> int:
        """Подсчитать количество спам-комментариев."""
        return await db.scard("comments:spam")
