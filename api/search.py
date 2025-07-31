"""API для поиска"""
from fastapi import APIRouter, Query
import logging
from typing import List
from models.post import Post, PostResponse

router = APIRouter()

@router.get("/search", response_model=List[PostResponse])
async def search_posts(q: str = Query(..., min_length=2)):
    logging.info(f"Выполняется полнотекстовый поиск по запросу: '{q}'")
    results = await Post.search_by_text(q)
    logging.info(f"Найдено {len(results)} постов по запросу '{q}'")
    return results
