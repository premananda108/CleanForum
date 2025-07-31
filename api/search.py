"""API для поиска"""
from fastapi import APIRouter, Query
from typing import List
from app.models.post import Post, PostResponse

router = APIRouter()

@router.get("/search", response_model=List[PostResponse])
async def search_posts(q: str = Query(..., min_length=2)):
    # Простой поиск по заголовку (в реальном приложении - полнотекстовый поиск)
    posts = await Post.get_all(limit=100)
    return [post for post in posts if q.lower() in post.title.lower() or q.lower() in post.content.lower()]
