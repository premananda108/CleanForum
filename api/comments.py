"""API для комментариев"""
from fastapi import APIRouter, HTTPException, Depends
import logging
from typing import List
from models.comment import Comment, CommentCreate, CommentResponse
import uuid

router = APIRouter()

async def get_current_user_id() -> str:
    """Временная заглушка для получения ID пользователя. Всегда возвращает одного и того же пользователя."""
    return "user_demo_12345"

@router.post("/comments", response_model=CommentResponse)
async def create_comment(comment_data: CommentCreate, current_user: str = Depends(get_current_user_id)):
    try:
        comment_id = await Comment.create(comment_data, current_user)
        if comment_id is None:
            logging.warning(f"Комментарий от {current_user} был отклонен как спам.")
            raise HTTPException(
                status_code=422,
                detail="Ваш комментарий был определен как спам и не может быть опубликован."
            )
        
        comment = await Comment.get_by_id(comment_id)
        if not comment:
            raise HTTPException(status_code=500, detail="Ошибка получения комментария после создания")
        
        return comment

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Ошибка при создании комментария: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при создании комментария")

@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_post_comments(post_id: str):
    logging.info(f"Запрос комментариев для поста {post_id}")
    return await Comment.get_by_post(post_id)
