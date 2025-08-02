import asyncio
from models.post import Post
from models.database import db
from services.vector_classifier import vector_classifier
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def reindex_all_posts():
    logging.info("Запуск переиндексации всех постов...")
    await db.connect()
    await vector_classifier.initialize()
    await Post.recreate_search_index()
    await db.disconnect()
    logging.info("Переиндексация завершена.")

if __name__ == "__main__":
    asyncio.run(reindex_all_posts())
