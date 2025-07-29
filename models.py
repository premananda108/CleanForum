"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Forum Models ---

class Post(BaseModel):
    """Represents a forum post stored in the database."""
    id: int
    title: str
    content: str
    author: str
    timestamp: datetime

class CreatePostRequest(BaseModel):
    """Request model for creating a new forum post."""
    author: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=10)

# --- Spam Classification Models ---

class DevToPost(BaseModel):
    """
    Represents the structure of a post used for classification,
    mimicking the dev.to API structure for compatibility with the training model.
    """
    id: int
    title: str
    description: Optional[str] = None
    tag_list: List[str] = []
    reading_time_minutes: int = 0
    public_reactions_count: int = 0
    comments_count: int = 0
    user: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    published_at: Optional[str] = None

class SimilarPostInfo(BaseModel):
    """Information about a post found to be similar during classification."""
    post_id: str
    title: str
    url: str
    score: float
    label: str

class ClassificationResult(BaseModel):
    """The final result of a spam classification check."""
    post_id: int
    is_spam: bool
    confidence: float
    recommendation: str
    reasoning: List[str]
    processing_time_ms: float
    similar_posts: List[SimilarPostInfo] = []

# --- Statistics Models ---

class StatsResponse(BaseModel):
    """Statistics about the classifier's performance."""
    total_classified: int
    spam_detected: int
    vectors_in_db: int
    last_training_run: Optional[datetime] = None
    model_accuracy: Optional[float] = None

class HealthCheckResponse(BaseModel):
    """Health status of the service and its dependencies."""
    status: str
    redis: str
    timestamp: datetime
