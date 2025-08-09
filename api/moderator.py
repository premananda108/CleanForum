"""
API for the moderator panel with anti-spam functions
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

# --- API Data Models ---
class ModerationAction(BaseModel):
    entity_id: str
    action: str  # "approve", "mark_spam", "delete"
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
    neighbors: List[PostResponse] = []

# --- Post Endpoints ---

@router.get("/pending-posts", response_model=List[PostResponse])
async def get_pending_posts(limit: int = Query(50, le=100)):
    """Get all posts for moderation."""
    return await Post.get_all_for_moderation(limit=limit)

@router.get("/posts/{post_id}/analysis", response_model=SpamAnalysisResponse)
async def get_post_analysis(post_id: str):
    """Get detailed spam analysis for a post."""
    analysis_data = await db.hgetall(f"vector_analysis:post:{post_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Analysis for the post not found.")

    # Get the neighbors used in the analysis
    neighbors_json = analysis_data.get("neighbors", "[]")
    neighbors = []
    try:
        neighbors_data = json.loads(neighbors_json)
        logging.info(f"Loaded {len(neighbors_data)} neighbors from cache for post {post_id}")
        for neighbor_data in neighbors_data:
            neighbor_id = neighbor_data.get("id")
            if neighbor_id:
                # Fetch the full post object to ensure all fields are present
                full_neighbor = await Post.get_by_id(neighbor_id)
                if full_neighbor:
                    neighbors.append(full_neighbor)
                else:
                    logging.warning(f"Could not fetch full data for neighbor post {neighbor_id}")
    except (json.JSONDecodeError, TypeError) as e:
        logging.error(f"Error decoding neighbor data for post {post_id}: {e}")

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
        analyzed_at=analysis_data.get("analyzed_at"),
        neighbors=neighbors
    )

@router.post("/moderate-post")
async def moderate_post(action: ModerationAction):
    """Perform a moderation action on a post."""
    post = await Post.get_by_id(action.entity_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if action.action == "approve":
        await Post.mark_as_spam(action.entity_id, 0.0, False, moderated=False)
        await db.hset(f"post:{action.entity_id}", {"moderated": "True"})
        await vector_classifier.retrain_with_feedback(action.entity_id, "post", False, action.moderator_id)
        await db.hset(f"vector_analysis:post:{action.entity_id}", mapping={
            "spam_score": 0.0,
            "is_spam": "False",
            "vector_prediction": "legitimate"
        })
        return {"message": "Post approved"}
    elif action.action == "mark_spam":
        await Post.mark_as_spam(action.entity_id, 1.0, True)
        await vector_classifier.retrain_with_feedback(action.entity_id, "post", True, action.moderator_id)
        await db.hset(f"vector_analysis:post:{action.entity_id}", mapping={
            "spam_score": 1.0,
            "is_spam": "True",
            "vector_prediction": "spam"
        })
        return {"message": "Post marked as spam"}
    elif action.action == "delete":
        await Post.hard_delete(action.entity_id)
        await vector_manager.delete_vector(f"post:{action.entity_id}")
        return {"message": "Post permanently deleted"}
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

# --- Comment Endpoints ---

@router.get("/pending-comments", response_model=List[CommentResponse])
async def get_pending_comments(limit: int = Query(50, le=100)):
    """Get all comments for moderation."""
    return await Comment.get_all_for_moderation(limit=limit)

@router.get("/comments/{comment_id}/analysis", response_model=SpamAnalysisResponse)
async def get_comment_analysis(comment_id: str):
    """Get detailed spam analysis for a comment."""
    analysis_data = await db.hgetall(f"vector_analysis:comment:{comment_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Analysis for the comment not found.")

    # Comments do not have 'similar posts' in the same sense as posts,
    # so neighbors here will be empty or contain comments,
    # which we will not try to convert to PostResponse.
    # Leaving it empty for consistency.
    neighbors = []

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
        analyzed_at=analysis_data.get("analyzed_at"),
        neighbors=neighbors
    )

@router.post("/moderate-comment")
async def moderate_comment(action: ModerationAction):
    """Perform a moderation action on a comment."""
    comment = await Comment.get_by_id(action.entity_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if action.action == "approve":
        await Comment.mark_as_spam(action.entity_id, 0.0, False)
        await vector_classifier.retrain_with_feedback(action.entity_id, "comment", False, action.moderator_id)
        await db.hset(f"vector_analysis:comment:{action.entity_id}", mapping={
            "spam_score": 0.0,
            "is_spam": "False",
            "vector_prediction": "legitimate"
        })
        return {"message": "Comment approved"}
    elif action.action == "mark_spam":
        await Comment.mark_as_spam(action.entity_id, 1.0, True)
        await vector_classifier.retrain_with_feedback(action.entity_id, "comment", True, action.moderator_id)
        await db.hset(f"vector_analysis:comment:{action.entity_id}", mapping={
            "spam_score": 1.0,
            "is_spam": "True",
            "vector_prediction": "spam"
        })
        return {"message": "Comment marked as spam"}
    elif action.action == "delete":
        await Comment.hard_delete(action.entity_id)
        await vector_manager.delete_vector(f"comment:{action.entity_id}")
        return {"message": "Comment permanently deleted"}
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

@router.post("/analyze-all-posts")
async def analyze_all_posts():
    """Triggers a background analysis of all posts that do not have an analysis."""
    logging.info("Request to analyze all posts")
    posts = await Post.get_all_for_moderation(limit=1000) # Limit to avoid overload
    analyzed_count = 0
    skipped_count = 0

    for post in posts:
        # Check if an analysis already exists
        if not await db.exists(f"vector_analysis:{post.id}"):
            await vector_classifier.analyze_with_vectors(
                post.id, post.title, post.content, post.tags, post.author_id
            )
            analyzed_count += 1
        else:
            skipped_count += 1

    return {
        "message": f"Analysis complete. Analyzed: {analyzed_count}, skipped: {skipped_count}",
        "analyzed": analyzed_count,
        "skipped": skipped_count
    }

@router.post("/retrain")
async def retrain_model():
    """Start model retraining based on feedback"""
    logging.info("🔄 Starting model retraining...")
    # In a real application, there would be code here for retraining
    # based on the collected feedback data

    return {
        "message": "Retraining started",
        "status": "in_progress",
        "started_at": datetime.now().isoformat()
    }

@router.get("/training-logs")
async def get_training_logs(limit: int = Query(100, le=500)):
    """Get training logs"""

    # Stub for demo
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
    """Get moderator feedback statistics"""

    # In a real application, this would analyze feedback data from Redis
    return {
        "total_feedback": 0,
        "spam_confirmations": 0,
        "false_positives": 0,
        "accuracy_improvement": 0.0,
        "last_feedback": None
    }

@router.post("/analyze-post/{post_id}")
async def reanalyze_post(post_id: str):
    """Re-analyze a post for spam"""

    post = await Post.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Perform re-analysis
    analysis = await vector_classifier.analyze_with_vectors(
        post_id, post.title, post.content, post.tags, post.author_id
    )

    # Update the post status if needed
    if analysis["is_spam"] != post.is_spam:
        await Post.mark_as_spam(post_id, analysis["spam_score"], analysis["is_spam"])

    return {
        "post_id": post_id,
        "analysis": analysis,
        "updated": True
    }

@router.get("/system-stats")
async def get_system_stats():
    """Get system statistics and application information."""
    logging.info("Requesting system statistics")
    try:
        redis_info = await db.get_server_info()
        vector_index_info = await vector_manager.get_index_info()

        # Post statistics
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        published_posts = await Post.count_published()

        # Comment statistics
        total_comments = await Comment.count_all()
        spam_comments = await Comment.count_spam()

        # Overall statistics
        total_content = total_posts + total_comments
        total_spam = spam_posts + spam_comments
        spam_percentage = (total_spam / total_content * 100) if total_content > 0 else 0

        return {
            # Content statistics
            "total_posts": total_posts,
            "published_posts": published_posts,
            "spam_posts": spam_posts,
            "total_comments": total_comments,
            "spam_comments": spam_comments,
            "spam_percentage": round(spam_percentage, 2),

            # System information
            "redis_version": redis_info.get("redis_version"),
            "used_memory": redis_info.get("used_memory_human"),
            "vector_count": vector_index_info.get("num_docs", 0),
            "python_version": platform.python_version(),
            "fastapi_version": fastapi_version,
            "app_version": settings.APP_VERSION
        }
    except Exception as e:
        logging.error(f"Error collecting system statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not collect statistics")
