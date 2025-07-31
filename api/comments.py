"""API для комментариев"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models.comment import Comment, CommentCreate, CommentResponse
import uuid

router = APIRouter()

async def get_current_user_id() -> str:
    return "user_demo_" + str(uuid.uuid4())[:8]

@router.post("/comments", response_model=CommentResponse)
async def create_comment(comment_data: CommentCreate, current_user: str = Depends(get_current_user_id)):
    comment_id = await Comment.create(comment_data, current_user)
    return await Comment.get_by_id(comment_id)

@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_post_comments(post_id: str):
    return await Comment.get_by_post(post_id)
