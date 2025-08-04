import asyncio
from models.database import db
from config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def drop_redis_index():
    logging.info(f"Attempting to drop index '{settings.VECTOR_INDEX_NAME}'...")
    await db.connect()
    try:
        await db.redis_client.execute_command("FT.DROPINDEX", settings.VECTOR_INDEX_NAME)
        logging.info(f"Index '{settings.VECTOR_INDEX_NAME}' dropped successfully.")
    except Exception as e:
        logging.warning(f"Failed to drop index '{settings.VECTOR_INDEX_NAME}'. It might not exist: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(drop_redis_index())