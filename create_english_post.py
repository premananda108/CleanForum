import asyncio
from models.post import Post, PostCreate
from models.database import db
from models.category import Category, CategoryCreate
from services.vector_classifier import vector_classifier
import logging
import uuid

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def create_english_post():
    logging.info("Создание нового поста на английском языке...")
    await db.connect()
    await vector_classifier.initialize()

    # Создаем или получаем категорию
    category_name = "English Posts"
    category = await Category.get_by_name(category_name)
    if not category:
        category_data = CategoryCreate(name=category_name, description="Posts in English")
        category_id = await Category.create(category_data)
        logging.info(f"Создана категория: {category_name}")
    else:
        category_id = category.id
        logging.info(f"Категория {category_name} уже существует.")

    # Создаем пост
    post_data = PostCreate(
        title="Exploring RediSearch with English Text",
        content="This is a test post to explore the capabilities of RediSearch with English text. We will search for words like 'RediSearch', 'English', and 'text'.",
        category_id=category_id,
        tags=["redis", "search", "english"]
    )
    author_id = f"user_english_{uuid.uuid4().hex[:8]}"

    post_id = await Post.create(post_data, author_id)

    if post_id:
        logging.info(f"Новый английский пост успешно создан с ID: {post_id}")
    else:
        logging.error("Не удалось создать английский пост.")

    await db.disconnect()
    logging.info("Создание поста завершено.")

if __name__ == "__main__":
    asyncio.run(create_english_post())
