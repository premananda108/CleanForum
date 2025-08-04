"""
Main FastAPI Application
"""
from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from logging_config import setup_logging

from config import settings
from models.database import db
from services.vector_classifier import vector_classifier
from api import posts, comments, categories, moderator, search, users

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    # Configure logging
    setup_logging()
    logging.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Connect to Redis
    await db.connect()

    # Initialize the vector classifier
    await vector_classifier.initialize()

    # Create default categories if they don't exist
    from models.category import Category, CategoryCreate
    existing_categories = await Category.get_all()
    if not existing_categories:
        print("Creating default categories")
        default_categories = [
            CategoryCreate(name="General", description="Conversations on any topic"),
            CategoryCreate(name="Technology", description="All about high-tech"),
            CategoryCreate(name="Off-topic", description="For non-serious discussions")
        ]
        for cat_data in default_categories:
            await Category.create(cat_data)

    yield

    # Shutdown
    logging.info("Shutting down the application")
    await db.disconnect()

# Create the application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A modern forum with advanced spam protection",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(posts.router, prefix="/api", tags=["posts"])
app.include_router(comments.router, prefix="/api", tags=["comments"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(moderator.router, prefix="/api/moderator", tags=["moderator"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(users.router, prefix="/api", tags=["users"])

@app.get("/api/logs")
async def get_logs():
    """Returns the last 100 lines of the log file"""
    try:
        with open("logs/forum.log", "r", encoding="utf-8") as f:
            lines = f.readlines()[-100:]
        return Response(content="".join(lines), media_type="text/plain")
    except FileNotFoundError:
        return Response(content="Log file not found.", status_code=404, media_type="text/plain")

@app.get("/")
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/posts/{post_id}")
async def post_detail(request: Request, post_id: str):
    """Post page"""
    return templates.TemplateResponse("post_detail.html", {
        "request": request,
        "post_id": post_id
    })

@app.get("/posts/{post_id}/edit")
async def edit_post_page(request: Request, post_id: str):
    """Edit post page"""
    from models.post import Post
    post = await Post.get_by_id(post_id, increment_views=False)
    if not post:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("edit_post.html", {"request": request, "post": post})


@app.get("/create")
async def create_post_page(request: Request):
    """Create post page"""
    return templates.TemplateResponse("create_post.html", {"request": request})

@app.get("/moderator")
async def moderator_panel_page(request: Request):
    """Moderator panel"""
    return templates.TemplateResponse("moderator_panel.html", {"request": request})

@app.get("/search")
async def search_page(request: Request):
    """Search page"""
    return templates.TemplateResponse("search_results.html", {"request": request})

@app.get("/category/{category_id}")
async def category_page(request: Request, category_id: str):
    """Category page"""
    from models.category import Category
    category = await Category.get_by_id(category_id)
    if not category:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("category.html", {
        "request": request,
        "category": category
    })

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )