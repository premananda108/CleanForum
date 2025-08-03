import asyncio
from models.database import db
from config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def drop_redis_index():
    logging.info(f"Попытка удаления индекса '{settings.VECTOR_INDEX_NAME}'...")
    await db.connect()
    try:
        await db.redis_client.execute_command("FT.DROPINDEX", settings.VECTOR_INDEX_NAME)
        logging.info(f"Индекс '{settings.VECTOR_INDEX_NAME}' успешно удален.")
    except Exception as e:
        logging.warning(f"Не удалось удалить индекс '{settings.VECTOR_INDEX_NAME}'. Возможно, он не существует: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(drop_redis_index())
