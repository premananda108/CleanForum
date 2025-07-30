"""
Main FastAPI application for CleanForum.
Handles API endpoints, serves the frontend, and integrates the spam classifier.
"""
import logging
import time
import json
from datetime import datetime
from contextlib import asynccontextmanager
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

# This dictionary will hold our application's state, like the Redis client and classifier
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown events."""
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
    
    yield
    
    logger.info("Application shutting down...")
    if app_state.get("redis"):
        await app_state["redis"].aclose()
        logger.info("Redis connection closed.")
    logger.info("Shutdown complete.")

app = FastAPI(
    title="CleanForum API",
    description="A modern forum with integrated spam protection.",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
@app.get("/api/posts", response_model=List[Message])
async def get_forum_posts():
    """Retrieves all non-spam forum posts."""
    redis_client = get_redis()
    posts_json = await db.get_all_posts(redis_client)
    
    all_messages = [Message.model_validate_json(p) for p in posts_json]
    
    # Filter out spam messages for the public view
    non_spam_messages = [msg for msg in all_messages if not msg.is_spam]
    
    non_spam_messages.sort(key=lambda x: x.timestamp, reverse=True)
    return non_spam_messages

@app.post("/api/posts", response_model=Message, status_code=201)
async def create_forum_post(post_data: CreatePostRequest):
    """
    Creates a new forum post.
    It first classifies the post. If it's spam, it's saved to the DB
    but an error is returned. If not, it's saved and returned.
    """
    classifier = get_classifier()
    
    # Adapt the forum post to the format expected by the classifier
    # Note: The classifier uses a different model (DevToPost). This is a bit awkward.
    # For this example, we'll assume the text is the most important part.
    # A more robust solution would unify the models.
    dev_to_post_format = DevToPost(
        id=int(time.time()),
        title="Forum Post", # Title is not in our simple message model
        description=post_data.content, # Using content as description
        user={"name": "user"} # Author is not in our simple message model
    )

    # Classify the post
    is_spam, confidence, reasoning, _ = await classifier.classify(dev_to_post_format)

    # --- Update Statistics ---
    redis_client = get_redis()
    await redis_client.incr("stats:total_classified")

    # Create the message object regardless of spam status
    new_message = Message(
        text=post_data.content,
        is_spam=is_spam,
        timestamp=datetime.now()
    )
    
    # Save the message to Redis
    message_id = str(int(time.time() * 1000))
    await db.save_post(redis_client, message_id, new_message.model_dump_json())
    logger.info(f"New message {message_id} saved with spam status: {is_spam}.")

    if is_spam:
        await redis_client.incr("stats:spam_detected")
        logger.warning(f"Spam detected (Confidence: {confidence:.2f}): {reasoning}")
        # Raise error AFTER saving, so it exists for moderation
        raise HTTPException(
            status_code=403,
            detail=f"Post rejected as spam. Reason: {', '.join(reasoning)}"
        )

    # If not spam, return the created message
    return new_message

# --- Spam Guard Management API Routes ---
@app.post("/api/train", status_code=202)
async def trigger_training(background_tasks: BackgroundTasks, background: bool = True):
    """
    Starts the model training process.
    By default, runs in the background. For testing, can be run in the foreground.
    """
    classifier = get_classifier()
    trainer = ModelTrainer(classifier)
    
    if background:
        logger.info("Adding model training to background tasks.")
        background_tasks.add_task(trainer.run_training_pipeline)
        return {"message": "Model training started in the background."}
    else:
        logger.info("Running model training in foreground for testing.")
        result = await trainer.run_training_pipeline()
        return {"message": "Model training completed.", "result": result}

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


# --- Moderation API Routes ---

@app.get("/moderation-panel", response_class=HTMLResponse)
async def serve_moderation_panel(request: Request):
    """Serves the moderation panel page."""
    return templates.TemplateResponse("moderation.html", {"request": request})

@app.get("/api/moderation", response_model=List[ModerationMessage])
async def get_all_messages_for_moderation():
    """Retrieves all messages, including spam, for the moderation panel."""
    redis_client = get_redis()
    posts_dict = await db.get_all_posts_with_ids(redis_client)
    
    messages = []
    for post_id, post_json in posts_dict.items():
        try:
            message_data = Message.model_validate_json(post_json)
            mod_message = ModerationMessage(
                id=post_id,
                text=message_data.text,
                is_spam=message_data.is_spam,
                timestamp=message_data.timestamp
            )
            messages.append(mod_message)
        except Exception as e:
            logger.error(f"Could not parse post with ID {post_id}. It might be in an old format. Error: {e}")
            continue
            
    messages.sort(key=lambda x: x.timestamp, reverse=True)
    return messages

@app.post("/api/moderation/update/{message_id}", status_code=200)
async def update_message_status(message_id: str, update_data: dict):
    """Updates the spam status of a message."""
    is_spam = update_data.get("is_spam")
    if is_spam is None:
        raise HTTPException(status_code=400, detail="Missing 'is_spam' field.")

    redis_client = get_redis()
    post_key = f"forum_post:{message_id}"
    
    post_json = await redis_client.get(post_key)
    if not post_json:
        raise HTTPException(status_code=404, detail="Message not found.")

    # Assuming the stored model is `Message`
    message = Message.model_validate_json(post_json)
    message.is_spam = is_spam
    
    await redis_client.set(post_key, message.model_dump_json())
    logger.info(f"Updated message {message_id} spam status to {is_spam}.")
    return {"message": "Update successful", "id": message_id, "is_spam": is_spam}

@app.delete("/api/moderation/delete/{message_id}", status_code=200)
async def delete_message(message_id: str):
    """Deletes a message from the database."""
    redis_client = get_redis()
    post_key = f"forum_post:{message_id}"
    
    deleted_count = await redis_client.delete(post_key)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found.")
        
    logger.info(f"Deleted message {message_id}.")
    return {"message": "Delete successful", "id": message_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
