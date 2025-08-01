"""
API роуты для работы с постами
"""
from fastapi import APIRouter, HTTPException, Depends, Query
import logging
from typing import List, Optional
from models.post import Post, PostCreate, PostUpdate, PostResponse
from models.category import Category
from models.user import User, UserRole
from services.vector_classifier import vector_classifier
import uuid

router = APIRouter()

# Временная функция для получения текущего пользователя
async def get_current_user_id() -> str:
    """Временная заглушка для получения ID пользователя. Всегда возвращает одного и того же пользователя."""
    # В реальном приложении здесь будет JWT авторизация
    return "user_demo_12345"

@router.post("/posts", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    current_user: str = Depends(get_current_user_id)
):
    """Создать новый пост"""
    logging.info(f"Попытка создания поста от пользователя {current_user}")
    logging.debug(f"Данные поста: {post_data.model_dump_json()}")

    # Проверяем существование категории
    category = await Category.get_by_id(post_data.category_id)
    if not category:
        logging.warning(f"Категория {post_data.category_id} не найдена.")
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Создаем пост
    try:
        post_id = await Post.create(post_data, current_user)
        if post_id is None:
            logging.warning(f"Пост от {current_user} был отклонен как спам.")
            raise HTTPException(
                status_code=422,
                detail="Ваш пост был определен как спам и не может быть опубликован."
            )
        logging.info(f"Пост {post_id} успешно создан.")
    except Exception as e:
        # Перехватываем и наш HTTPException
        if isinstance(e, HTTPException):
            raise e
        logging.error(f"Ошибка при создании поста в БД: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при создании поста")

    # Обновляем счетчик постов в категории
    await Category.update_post_count(post_data.category_id, 1)

    # Получаем созданный пост
    post = await Post.get_by_id(post_id)
    if not post:
        # Эта ситуация маловероятна, если post_id был получен
        logging.error(f"Не удалось получить пост {post_id} после создания.")
        raise HTTPException(status_code=500, detail="Ошибка получения поста после создания")

    logging.info(f"Пост {post_id} успешно обработан и возвращен клиенту.")
    return post

@router.get("/posts", response_model=List[PostResponse])
async def get_posts(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[str] = None
):
    """Получить список постов"""

    if category_id:
        posts = await Post.get_by_category(category_id, limit, offset)
    else:
        posts = await Post.get_all(limit, offset)

    return posts

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: str, increment_views: bool = True):
    """Получить пост по ID"""

    post = await Post.get_by_id(post_id, increment_views)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    # Получаем похожие посты
    similar_posts = await Post.get_similar_posts(post_id)
    post.similar_posts = similar_posts

    return post

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    post_data: PostUpdate,
    current_user: str = Depends(get_current_user_id)
):
    """Обновить пост"""

    # Проверяем существование поста
    existing_post = await Post.get_by_id(post_id)
    if not existing_post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    # Проверяем права на редактирование
    if existing_post.author_id != current_user:
        raise HTTPException(status_code=403, detail="У вас нет прав для редактирования этого поста")

    # Обновляем пост
    success = await Post.update(post_id, post_data)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка обновления поста")

    # Если обновился контент, повторно анализируем на спам
    if post_data.content is not None or post_data.title is not None:
        updated_post = await Post.get_by_id(post_id)
        if updated_post:
            text_for_analysis = Post._extract_text_from_editorjs(updated_post.content)
            spam_analysis = await vector_classifier.analyze_with_vectors(
                post_id, updated_post.title, text_for_analysis, 
                updated_post.tags, updated_post.author_id
            )

            if spam_analysis["is_spam"]:
                await Post.mark_as_spam(post_id, spam_analysis["spam_score"], True)

    # Возвращаем обновленный пост
    post = await Post.get_by_id(post_id)
    return post

@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Удалить пост. Доступно только автору поста.
    """
    logging.info(f"Попытка удаления поста {post_id} пользователем {current_user_id}")

    # 1. Проверяем существование поста
    existing_post = await Post.get_by_id(post_id, increment_views=False)
    if not existing_post:
        logging.warning(f"Попытка удаления несуществующего поста {post_id}")
        raise HTTPException(status_code=404, detail="Пост не найден")

    # 2. Проверяем права на удаление
    if existing_post.author_id != current_user_id:
        logging.error(f"Пользователь {current_user_id} пытался удалить чужой пост {post_id} (автор: {existing_post.author_id})")
        raise HTTPException(status_code=403, detail="У вас нет прав для удаления этого поста")

    # 3. Помечаем пост как удаленный
    success = await Post.mark_as_deleted(post_id)
    if not success:
        # Эта ошибка может произойти, если пост был удален между get_by_id и mark_as_deleted
        logging.error(f"Произошла ошибка при попытке пометить пост {post_id} как удаленный")
        raise HTTPException(status_code=500, detail="Ошибка при удалении поста")

    logging.info(f"Пост {post_id} успешно помечен как удаленный пользователем {current_user_id}")
    
    # Возвращаем 204 No Content, как принято для DELETE запросов
    return

@router.get("/posts/{post_id}/spam-analysis")
async def get_spam_analysis(post_id: str):
    """Получить результаты анализа спама для поста"""

    from models.database import db

    # Получаем анализ спама
    analysis_data = await db.hgetall(f"vector_analysis:{post_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Анализ спама не найден")

    return {
        "post_id": analysis_data.get("post_id"),
        "spam_score": float(analysis_data.get("spam_score", 0)),
        "is_spam": analysis_data.get("is_spam") == "True",
        "heuristic_score": float(analysis_data.get("heuristic_score", 0)),
        "vector_score": float(analysis_data.get("vector_score", 0)),
        "vector_prediction": analysis_data.get("vector_prediction"),
        "vector_confidence": float(analysis_data.get("vector_confidence", 0)),
        "similar_posts_count": int(analysis_data.get("similar_posts_count", 0)),
        "analyzed_at": analysis_data.get("analyzed_at")
    }
