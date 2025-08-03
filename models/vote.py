"""
Модель голосования
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid
from models.database import db

class VoteType(str, Enum):
    UP = "up"
    DOWN = "down"

class VoteTarget(str, Enum):
    POST = "post"
    COMMENT = "comment"

class VoteCreate(BaseModel):
    target_type: VoteTarget
    target_id: str
    vote_type: VoteType

class Vote:
    """Класс для работы с голосованием"""

    @staticmethod
    async def vote(user_id: str, vote_data: VoteCreate) -> bool:
        """Поставить голос"""
        vote_key = f"vote:{user_id}:{vote_data.target_type.value}:{vote_data.target_id}"

        # Проверяем, есть ли уже голос от этого пользователя
        existing_vote = await db.get(vote_key)

        # Если голос такой же, удаляем его (отмена голоса)
        if existing_vote == vote_data.vote_type.value:
            await db.delete(vote_key)
            await Vote._update_score(vote_data.target_type, vote_data.target_id, 
                                   -1 if vote_data.vote_type == VoteType.UP else 1)
            return True

        # Если голос противоположный, меняем его
        if existing_vote:
            delta = 2 if vote_data.vote_type == VoteType.UP else -2
        else:
            delta = 1 if vote_data.vote_type == VoteType.UP else -1

        # Сохраняем новый голос
        await db.set(vote_key, vote_data.vote_type.value)
        await Vote._update_score(vote_data.target_type, vote_data.target_id, delta)

        return True

    @staticmethod
    async def _update_score(target_type: VoteTarget, target_id: str, delta: int):
        """Обновить рейтинг цели"""
        if target_type == VoteTarget.POST:
            post_data = await db.hgetall(f"post:{target_id}")
            if post_data:
                new_score = int(post_data.get("vote_score", 0)) + delta
                await db.hset(f"post:{target_id}", {"vote_score": new_score})

        elif target_type == VoteTarget.COMMENT:
            comment_data = await db.hgetall(f"comment:{target_id}")
            if comment_data:
                new_score = int(comment_data.get("vote_score", 0)) + delta
                await db.hset(f"comment:{target_id}", {"vote_score": new_score})

    @staticmethod
    async def get_user_vote(user_id: str, target_type: VoteTarget, target_id: str) -> Optional[VoteType]:
        """Получить голос пользователя"""
        vote_key = f"vote:{user_id}:{target_type.value}:{target_id}"
        vote = await db.get(vote_key)
        return VoteType(vote) if vote else None
