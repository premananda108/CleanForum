"""API for comments"""
from fastapi import APIRouter, HTTPException, Depends
import logging
from typing import List
from models.comment import Comment, CommentCreate, CommentResponse
import uuid

router = APIRouter()

async def get_current_user_id() -> str:
    """Temporary stub to get the user ID. Always returns the same user."""
    return "user_demo_12345"

@router.post("/comments", response_model=CommentResponse)
async def create_comment(comment_data: CommentCreate, current_user: str = Depends(get_current_user_id)):
    try:
        comment_id = await Comment.create(comment_data, current_user)
        if comment_id is None:
            logging.warning(f"Comment from {current_user} was rejected as spam.")
            raise HTTPException(
                status_code=422,
                detail="Your comment was identified as spam and cannot be published."
            )
        
        comment = await Comment.get_by_id(comment_id)
        if not comment:
            raise HTTPException(status_code=500, detail="Error retrieving comment after creation")
        
        return comment

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error creating comment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error creating comment")

@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_post_comments(post_id: str):
    logging.info(f"Requesting comments for post {post_id}")
    return await Comment.get_by_post(post_id)
