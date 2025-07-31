"""
API для панели модератора с антиспам функциями
"""
from fastapi import APIRouter, HTTPException, Query
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import json
from datetime import datetime

from config import settings
from models.database import db
from models.post import Post, PostResponse
from models.comment import Comment, CommentResponse
from services.vector_classifier import vector_classifier
from services.spam_detector import spam_detector
from services.redis_manager import vector_manager
import sys
import platform
from fastapi import __version__ as fastapi_version

router = APIRouter()

# --- Модели данных для API ---
class ModerationAction(BaseModel):
    entity_id: str
    action: str  # "approve", "mark_spam"
    moderator_id: str = "moderator_demo"

class SpamAnalysisResponse(BaseModel):
    entity_id: str
    spam_score: float
    is_spam: bool
    reasons: List[str]
    heuristic_score: float
    vector_score: float
    vector_prediction: str
    vector_confidence: float
    similar_posts_count: int
    analyzed_at: Optional[str] = None

# --- Эндпоинты для постов ---

@router.get("/pending-posts", response_model=List[PostResponse])
async def get_pending_posts(limit: int = Query(50, le=100)):
    """Получить все посты для модерации."""
    return await Post.get_all_for_moderation(limit=limit)

@router.get("/posts/{post_id}/analysis", response_model=SpamAnalysisResponse)
async def get_post_analysis(post_id: str):
    """Получить детальный анализ спама для поста."""
    analysis_data = await db.hgetall(f"vector_analysis:post:{post_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Анализ для поста не найден.")

    return SpamAnalysisResponse(
        entity_id=analysis_data.get("entity_id"),
        spam_score=float(analysis_data.get("spam_score", 0)),
        is_spam=analysis_data.get("is_spam") == "True",
        reasons=json.loads(analysis_data.get("reasons", "[]")),
        heuristic_score=float(analysis_data.get("heuristic_score", 0)),
        vector_score=float(analysis_data.get("vector_score", 0)),
        vector_prediction=analysis_data.get("vector_prediction", "unknown"),
        vector_confidence=float(analysis_data.get("vector_confidence", 0)),
        similar_posts_count=int(analysis_data.get("similar_posts_count", 0)),
        analyzed_at=analysis_data.get("analyzed_at")
    )

@router.post("/moderate-post")
async def moderate_post(action: ModerationAction):
    """Выполнить действие модерации над постом."""
    post = await Post.get_by_id(action.entity_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    if action.action == "approve":
        await Post.mark_as_spam(action.entity_id, 0.0, False)
        await vector_classifier.retrain_with_feedback(action.entity_id, "post", False, action.moderator_id)
        return {"message": "Пост одобрен"}
    elif action.action == "mark_spam":
        await Post.mark_as_spam(action.entity_id, 1.0, True)
        await vector_classifier.retrain_with_feedback(action.entity_id, "post", True, action.moderator_id)
        return {"message": "Пост помечен как спам"}
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")

# --- Эндпоинты для комментариев ---

@router.get("/pending-comments", response_model=List[CommentResponse])
async def get_pending_comments(limit: int = Query(50, le=100)):
    """Получить все комментарии для модерации."""
    return await Comment.get_all_for_moderation(limit=limit)

@router.get("/comments/{comment_id}/analysis", response_model=SpamAnalysisResponse)
async def get_comment_analysis(comment_id: str):
    """Получить детальный анализ спама для комментария."""
    analysis_data = await db.hgetall(f"vector_analysis:comment:{comment_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Анализ для комментария не найден.")

    return SpamAnalysisResponse(
        entity_id=analysis_data.get("entity_id"),
        spam_score=float(analysis_data.get("spam_score", 0)),
        is_spam=analysis_data.get("is_spam") == "True",
        reasons=json.loads(analysis_data.get("reasons", "[]")),
        heuristic_score=float(analysis_data.get("heuristic_score", 0)),
        vector_score=float(analysis_data.get("vector_score", 0)),
        vector_prediction=analysis_data.get("vector_prediction", "unknown"),
        vector_confidence=float(analysis_data.get("vector_confidence", 0)),
        similar_posts_count=int(analysis_data.get("similar_posts_count", 0)),
        analyzed_at=analysis_data.get("analyzed_at")
    )

@router.post("/moderate-comment")
async def moderate_comment(action: ModerationAction):
    """Выполнить действие модерации над комментарием."""
    comment = await Comment.get_by_id(action.entity_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    if action.action == "approve":
        await Comment.mark_as_spam(action.entity_id, 0.0, False)
        await vector_classifier.retrain_with_feedback(action.entity_id, "comment", False, action.moderator_id)
        return {"message": "Комментарий одобрен"}
    elif action.action == "mark_spam":
        await Comment.mark_as_spam(action.entity_id, 1.0, True)
        await vector_classifier.retrain_with_feedback(action.entity_id, "comment", True, action.moderator_id)
        return {"message": "Комментарий помечен как спам"}
    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")

@router.post("/analyze-all-posts")
async def analyze_all_posts():
    """Запускает фоновый анализ всех постов, у которых нет анализа."""
    logging.info("Запрос на анализ всех постов")
    posts = await Post.get_all_for_moderation(limit=1000) # Ограничение, чтобы избежать перегрузки
    analyzed_count = 0
    skipped_count = 0

    for post in posts:
        # Проверяем, существует ли уже анализ
        if not await db.exists(f"vector_analysis:{post.id}"):
            await vector_classifier.analyze_with_vectors(
                post.id, post.title, post.content, post.tags, post.author_id
            )
            analyzed_count += 1
        else:
            skipped_count += 1

    return {
        "message": f"Анализ завершен. Проанализировано: {analyzed_count}, пропущено: {skipped_count}",
        "analyzed": analyzed_count,
        "skipped": skipped_count
    }

@router.post("/retrain")
async def retrain_model():
    """Запустить переобучение модели на основе обратной связи"""
    logging.info("🔄 Запуск переобучения модели...")
    # В реальном приложении здесь был бы код переобучения
    # на основе собранных данных обратной связи

    return {
        "message": "Переобучение запущено",
        "status": "in_progress",
        "started_at": datetime.now().isoformat()
    }

@router.get("/training-logs")
async def get_training_logs(limit: int = Query(100, le=500)):
    """Получить логи обучения"""

    # Заглушка для демо
    logs = [
        {
            "timestamp": datetime.now().isoformat(),
            "event": "Model initialized",
            "details": "SentenceTransformer loaded successfully"
        },
        {
            "timestamp": datetime.now().isoformat(),
            "event": "Vector index created", 
            "details": f"Created index with dimension 384"
        }
    ]

    return {"logs": logs, "total": len(logs)}

@router.get("/feedback-stats")
async def get_feedback_statistics():
    """Получить статистику обратной связи модераторов"""

    # В реальном приложении здесь анализ feedback данных из Redis
    return {
        "total_feedback": 0,
        "spam_confirmations": 0,
        "false_positives": 0,
        "accuracy_improvement": 0.0,
        "last_feedback": None
    }

@router.post("/analyze-post/{post_id}")
async def reanalyze_post(post_id: str):
    """Повторно проанализировать пост на спам"""

    post = await Post.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    # Проводим повторный анализ
    analysis = await vector_classifier.analyze_with_vectors(
        post_id, post.title, post.content, post.tags, post.author_id
    )

    # Обновляем статус поста если нужно
    if analysis["is_spam"] != post.is_spam:
        await Post.mark_as_spam(post_id, analysis["spam_score"], analysis["is_spam"])

    return {
        "post_id": post_id,
        "analysis": analysis,
        "updated": True
    }

@router.get("/system-stats")
async def get_system_stats():
    """Получить системную статистику и информацию о приложении."""
    logging.info("Запрос системной статистики")
    try:
        redis_info = await db.get_server_info()
        vector_index_info = await vector_manager.get_index_info()

        # Статистика по постам
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()

        # Статистика по комментариям
        total_comments = await Comment.count_all()
        spam_comments = await Comment.count_spam()

        # Общая статистика
        total_content = total_posts + total_comments
        total_spam = spam_posts + spam_comments
        spam_percentage = (total_spam / total_content * 100) if total_content > 0 else 0

        return {
            # Статистика контента
            "total_posts": total_posts,
            "spam_posts": spam_posts,
            "total_comments": total_comments,
            "spam_comments": spam_comments,
            "spam_percentage": round(spam_percentage, 2),
            
            # Системная информация
            "redis_version": redis_info.get("redis_version"),
            "used_memory": redis_info.get("used_memory_human"),
            "vector_count": vector_index_info.get("num_docs", 0),
            "python_version": platform.python_version(),
            "fastapi_version": fastapi_version,
            "app_version": settings.APP_VERSION
        }
    except Exception as e:
        logging.error(f"Ошибка при сборе системной статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось собрать статистику")
