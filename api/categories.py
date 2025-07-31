"""API для категорий"""
from fastapi import APIRouter, HTTPException
from typing import List
from app.models.category import Category, CategoryCreate, CategoryResponse

router = APIRouter()

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories():
    return await Category.get_all()

@router.post("/categories", response_model=CategoryResponse)
async def create_category(category_data: CategoryCreate):
    category_id = await Category.create(category_data)
    return await Category.get_by_id(category_id)
