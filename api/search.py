"""API for search"""
from fastapi import APIRouter, Query
import logging
from typing import List
from models.post import Post, PostResponse

router = APIRouter()

@router.get("/search", response_model=List[PostResponse])
async def search_posts(q: str = Query(..., min_length=2)):
    logging.info(f"Performing full-text search for query: '{q}'")
    results = await Post.search_by_text(q)
    logging.info(f"Found {len(results)} posts for query '{q}'")
    return results
