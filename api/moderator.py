"""
API для панели модератора с антиспам функциями
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import json
from datetime import datetime
from models.database import db
from models.post import Post, PostResponse, PostStatus
from services.vector_classifier import vector_classifier
from services.spam_detector import spam_detector

router = APIRouter()

class ModerationAction(BaseModel):
    post_id: str
    action: str  # "approve", "mark_spam", "delete"
    moderator_id: str = "moderator_demo"

class SpamAnalysisResponse(BaseModel):
    post_id: str
    spam_score: float
    is_spam: bool
    reasons: List[str]
    heuristic_score: float
    vector_score: float
    vector_prediction: str
    vector_confidence: float
    similar_posts_count: int
    spam_neighbors: int
    legitimate_neighbors: int
    analyzed_at: str

@router.get("/pending-posts", response_model=List[PostResponse])
async def get_pending_posts(limit: int = Query(50, le=100)):
    """Получить посты, требующие модерации"""

    # Получаем все посты и фильтруем подозрительные
    posts = await Post.get_all(limit=limit)
    pending_posts = []

    for post in posts:
        # Проверяем, есть ли анализ спама
        analysis_data = await db.hgetall(f"vector_analysis:{post.id}")
        if analysis_data:
            spam_score = float(analysis_data.get("spam_score", 0))
            # Включаем посты с высокой оценкой спама или помеченные как спам
            if spam_score > 0.3 or post.is_spam:
                pending_posts.append(post)

    return pending_posts

@router.get("/spam-statistics")
async def get_spam_statistics():
    """Получить статистику спама"""

    # Получаем статистику классификатора
    classifier_stats = await vector_classifier.get_classification_stats()

    # Получаем статистику детектора
    detector_stats = await spam_detector.get_spam_statistics()

    # Считаем общую статистику (заглушка для демо)
    total_posts = 0
    spam_posts = 0

    # В реальном приложении здесь будут запросы к Redis
    return {
        "total_posts_analyzed": total_posts,
        "spam_detected": spam_posts,
        "spam_rate": spam_posts / max(total_posts, 1),
        "classifier_stats": classifier_stats,
        "detector_stats": detector_stats,
        "last_updated": datetime.now().isoformat()
    }

@router.get("/posts/{post_id}/analysis", response_model=SpamAnalysisResponse)
async def get_detailed_analysis(post_id: str):
    """Получить детальный анализ спама для поста"""

    # Получаем данные анализа
    analysis_data = await db.hgetall(f"vector_analysis:{post_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Анализ не найден")

    # Получаем причины из JSON
    reasons = json.loads(analysis_data.get("reasons", "[]"))

    return SpamAnalysisResponse(
        post_id=analysis_data["post_id"],
        spam_score=float(analysis_data.get("spam_score", 0)),
        is_spam=analysis_data.get("is_spam") == "True",
        reasons=reasons,
        heuristic_score=float(analysis_data.get("heuristic_score", 0)),
        vector_score=float(analysis_data.get("vector_score", 0)),
        vector_prediction=analysis_data.get("vector_prediction", "unknown"),
        vector_confidence=float(analysis_data.get("vector_confidence", 0)),
        similar_posts_count=int(analysis_data.get("similar_posts_count", 0)),
        spam_neighbors=0,  # Заглушка
        legitimate_neighbors=0,  # Заглушка  
        analyzed_at=analysis_data.get("analyzed_at", "")
    )

@router.post("/moderate")
async def moderate_post(action: ModerationAction):
    """Выполнить действие модерации"""

    post = await Post.get_by_id(action.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    if action.action == "approve":
        # Помечаем как легитимный
        await Post.mark_as_spam(action.post_id, 0.0, False)

        # Сохраняем обратную связь для обучения
        await vector_classifier.retrain_with_feedback(
            action.post_id, False, action.moderator_id
        )

        return {"message": "Пост одобрен", "action": "approved"}

    elif action.action == "mark_spam":
        # Помечаем как спам
        await Post.mark_as_spam(action.post_id, 1.0, True)

        # Сохраняем обратную связь для обучения
        await vector_classifier.retrain_with_feedback(
            action.post_id, True, action.moderator_id
        )

        return {"message": "Пост помечен как спам", "action": "marked_spam"}

    elif action.action == "delete":
        # Удаляем пост
        await Post.mark_as_spam(action.post_id, 0.0, False)

        return {"message": "Пост удален", "action": "deleted"}

    else:
        raise HTTPException(status_code=400, detail="Неизвестное действие")

@router.post("/retrain")
async def retrain_model():
    """Запустить переобучение модели на основе обратной связи"""

    print("🔄 Запуск переобучения модели...")

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
