"""
Модель комментария
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from models.database import db

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=5, max_length=2000)
    post_id: str

class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=5, max_length=2000)

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

class Comment:
    """Класс для работы с комментариями"""

    @staticmethod
    async def create(comment_data: CommentCreate, author_id: str) -> str:
        """Создать новый комментарий"""
        comment_id = str(uuid.uuid4())
        now = datetime.now()

        comment_info = {
            "id": comment_id,
            "content": comment_data.content,
            "post_id": comment_data.post_id,
            "author_id": author_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "vote_score": 0,
            "is_spam": False
        }

        # Сохраняем комментарий
        await db.hset(f"comment:{comment_id}", comment_info)

        # Добавляем в индексы
        timestamp = now.timestamp()
        await db.zadd(f"comments:post:{comment_data.post_id}", {comment_id: timestamp})
        await db.zadd(f"comments:author:{author_id}", {comment_id: timestamp})

        # Обновляем счетчик комментариев в посте
        await db.hincrby(f"post:{comment_data.post_id}", "comment_count", 1)

        return comment_id

    @staticmethod
    async def get_by_id(comment_id: str) -> Optional[CommentResponse]:
        """Получить комментарий по ID"""
        comment_data = await db.hgetall(f"comment:{comment_id}")
        if not comment_data:
            return None

        # Получаем информацию об авторе
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
            is_spam=comment_data.get("is_spam", "False") == "True"
        )

    @staticmethod
    async def get_by_post(post_id: str, limit: int = 50, offset: int = 0) -> List[CommentResponse]:
        """Получить комментарии к посту"""
        comment_ids = await db.zrange(f"comments:post:{post_id}", offset, offset + limit - 1)

        comments = []
        for comment_id in comment_ids:
            comment = await Comment.get_by_id(comment_id)
            if comment and not comment.is_spam:
                comments.append(comment)

        return comments

    @staticmethod
    async def update(comment_id: str, comment_data: CommentUpdate) -> bool:
        """Обновить комментарий"""
        existing_data = await db.hgetall(f"comment:{comment_id}")
        if not existing_data:
            return False

        update_fields = {
            "content": comment_data.content,
            "updated_at": datetime.now().isoformat()
        }

        await db.hset(f"comment:{comment_id}", update_fields)
        return True
