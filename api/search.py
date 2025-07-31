"""API для поиска"""
from fastapi import APIRouter, Query
import logging
from typing import List
from models.post import Post, PostResponse

router = APIRouter()

@router.get("/search", response_model=List[PostResponse])
async def search_posts(q: str = Query(..., min_length=2)):
    logging.info(f"Выполняется поиск по запросу: '{q}'")
    # Простой поиск по заголовку (в реальном приложении - полнотекстовый поиск)
    posts = await Post.get_all(limit=100)
    results = [post for post in posts if q.lower() in post.title.lower() or q.lower() in post.content.lower()]
    logging.info(f"Найдено {len(results)} постов по запросу '{q}'")
    return results
