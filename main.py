"""
Основное приложение FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from models.database import db
from services.vector_classifier import vector_classifier
from api import posts, comments, categories, moderator, search

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск
    print(f"🚀 Запуск {settings.APP_NAME} v{settings.APP_VERSION}")

    # Подключаемся к Redis
    await db.connect()

    # Инициализируем векторный классификатор
    await vector_classifier.initialize()

    # Создаем категории по умолчанию, если их нет
    from models.category import Category, CategoryCreate
    existing_categories = await Category.get_all()
    if not existing_categories:
        print("Создаем категории по умолчанию")
        default_categories = [
            CategoryCreate(name="Общие", description="Разговоры на любые темы"),
            CategoryCreate(name="Технологии", description="Все о высоких технологиях"),
            CategoryCreate(name="Флуд", description="Для несерьезных обсуждений")
        ]
        for cat_data in default_categories:
            await Category.create(cat_data)

    yield

    # Завершение
    print("🔚 Завершение работы приложения")
    await db.disconnect()

# Создаем приложение
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Современный форум с продвинутой защитой от спама",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory="templates")

# Подключаем роуты API
app.include_router(posts.router, prefix="/api", tags=["posts"])
app.include_router(comments.router, prefix="/api", tags=["comments"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(moderator.router, prefix="/api/moderator", tags=["moderator"])
app.include_router(search.router, prefix="/api", tags=["search"])

@app.get("/")
async def home(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/posts/{post_id}")
async def post_detail(request: Request, post_id: str):
    """Страница поста"""
    return templates.TemplateResponse("post_detail.html", {
        "request": request,
        "post_id": post_id
    })

@app.get("/create")
async def create_post_page(request: Request):
    """Страница создания поста"""
    return templates.TemplateResponse("create_post.html", {"request": request})

@app.get("/moderator")
async def moderator_panel_page(request: Request):
    """Панель модератора"""
    return templates.TemplateResponse("moderator_panel.html", {"request": request})

@app.get("/search")
async def search_page(request: Request):
    """Страница поиска"""
    return templates.TemplateResponse("search_results.html", {"request": request})

@app.get("/category/{category_id}")
async def category_page(request: Request, category_id: str):
    """Страница категории"""
    return templates.TemplateResponse("category.html", {
        "request": request,
        "category_id": category_id
    })

@app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
