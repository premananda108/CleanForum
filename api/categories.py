"""API для категорий"""
from fastapi import APIRouter, HTTPException
import logging
from typing import List
from models.category import Category, CategoryCreate, CategoryResponse

router = APIRouter()

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories():
    return await Category.get_all()

@router.post("/categories", response_model=CategoryResponse)
async def create_category(category_data: CategoryCreate):
    logging.info(f"Попытка создания категории: {category_data.name}")
    try:
        category_id = await Category.create(category_data)
        logging.info(f"Категория '{category_data.name}' (id: {category_id}) успешно создана.")
        category = await Category.get_by_id(category_id)
        if not category:
            logging.error(f"Не удалось получить категорию {category_id} после создания.")
            raise HTTPException(status_code=500, detail="Ошибка создания категории")
        return category
    except Exception as e:
        logging.error(f"Ошибка при создании категории '{category_data.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка")
