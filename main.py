"""
Main FastAPI application for CleanForum.
Handles API endpoints, serves the frontend, and integrates the spam classifier.
"""
import logging
import time
import json
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

# Import project modules
import db
from models import *
from core.classification import SpamClassifier, VECTOR_DIM, INDEX_NAME, INDEX_PREFIX
from core.training import ModelTrainer

# --- Application Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CleanForum API",
    description="A modern forum with integrated spam protection.",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Global State ---
# This dictionary will hold our application's state, like the Redis client and classifier
app_state = {}

# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """Initialize resources on application startup."""
    logger.info("Application starting up...")
    redis_client = await db.RedisClient.get_instance()
    if redis_client:
        await db.create_redis_index(redis_client, INDEX_NAME, VECTOR_DIM, INDEX_PREFIX)
        classifier = SpamClassifier(redis_client)
        app_state["redis"] = redis_client
        app_state["classifier"] = classifier
        logger.info("Spam classifier initialized.")
    else:
        logger.error("Failed to initialize Redis. Spam classifier will not be available.")
        app_state["redis"] = None
        app_state["classifier"] = None
    logger.info("Startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    if app_state.get("redis"):
        await app_state["redis"].close()
        logger.info("Redis connection closed.")
    logger.info("Application shutting down.")

# --- Helper Functions ---
def get_classifier() -> SpamClassifier:
    """Dependency injector for the spam classifier."""
    classifier = app_state.get("classifier")
    if not classifier:
        raise HTTPException(status_code=503, detail="Spam classifier is not available due to Redis connection issue.")
    return classifier

def get_redis() -> Redis:
    """Dependency injector for the Redis client."""
    redis_client = app_state.get("redis")
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis service is unavailable.")
    return redis_client

# --- Frontend Routes ---
@app.get("/", response_class=HTMLResponse)
async def serve_forum(request: Request):
    """Serves the main forum page."""
    return templates.TemplateResponse("forum.html", {"request": request})

# --- Forum API Routes ---
@app.get("/api/posts", response_model=List[Post])
async def get_forum_posts():
    """Retrieves all forum posts."""
    redis_client = get_redis()
    posts_json = await db.get_all_posts(redis_client)
    # Parse JSON strings into Post objects
    posts = [Post.model_validate_json(p) for p in posts_json]
    # Sort by timestamp descending
    posts.sort(key=lambda x: x.timestamp, reverse=True)
    return posts

@app.post("/api/posts", response_model=Post, status_code=201)
async def create_forum_post(post_data: CreatePostRequest):
    """Creates a new forum post after checking for spam."""
    classifier = get_classifier()
    
    # Adapt the forum post to the format expected by the classifier
    dev_to_post_format = DevToPost(
        id=int(time.time()),
        title=post_data.title,
        description=post_data.content,
        user={"name": post_data.author}
    )

    # Classify the post
    is_spam, confidence, reasoning, _ = await classifier.classify(dev_to_post_format)

    if is_spam:
        logger.warning(f"Spam detected (Confidence: {confidence:.2f}): {reasoning}")
        raise HTTPException(
            status_code=403,
            detail=f"Post rejected as spam. Reason: {', '.join(reasoning)}"
        )

    # If not spam, create and save the post
    new_post = Post(
        id=int(time.time() * 1000),
        author=post_data.author,
        title=post_data.title,
        content=post_data.content,
        timestamp=datetime.now()
    )
    
    redis_client = get_redis()
    await db.save_post(redis_client, str(new_post.id), new_post.model_dump_json())
    logger.info(f"New post '{new_post.title}' by {new_post.author} created.")
    
    return new_post

# --- Spam Guard Management API Routes ---
@app.post("/api/train", status_code=202)
async def trigger_training(background_tasks: BackgroundTasks):
    """Starts the model training process in the background."""
    classifier = get_classifier()
    trainer = ModelTrainer(classifier)
    
    logger.info("Adding model training to background tasks.")
    background_tasks.add_task(trainer.run_training_pipeline)
    
    return {"message": "Model training started in the background."}

@app.get("/api/stats", response_model=StatsResponse)
async def get_system_stats():
    """Gets statistics about the system."""
    redis_client = get_redis()
    
    # These could be tracked more formally, here's a simple way
    total_classified = await redis_client.get("stats:total_classified") or 0
    spam_detected = await redis_client.get("stats:spam_detected") or 0
    
    # Get number of vectors from index info
    num_vectors = 0
    try:
        index_info = await redis_client.ft(INDEX_NAME).info()
        num_vectors = index_info.get('num_docs', 0)
    except Exception:
        logger.warning(f"Could not get info for index '{INDEX_NAME}'. It might not exist yet.")

    # Accuracy and last training run would be stored after a training run
    last_run_data = await redis_client.get("stats:last_training_run")
    last_run_info = json.loads(last_run_data) if last_run_data else {}

    return StatsResponse(
        total_classified=int(total_classified),
        spam_detected=int(spam_detected),
        vectors_in_db=int(num_vectors),
        last_training_run=last_run_info.get("timestamp"),
        model_accuracy=last_run_info.get("accuracy")
    )

@app.get("/api/health", response_model=HealthCheckResponse)
async def health_check():
    """Performs a health check of the service."""
    redis_status = "connected" if app_state.get("redis") else "disconnected"
    return HealthCheckResponse(
        status="healthy" if redis_status == "connected" else "degraded",
        redis=redis_status,
        timestamp=datetime.now()
    )