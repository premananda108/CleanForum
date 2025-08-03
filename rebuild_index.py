import asyncio
import logging
from models.database import db
from models.post import Post
from services.redis_manager import vector_manager

logging.basicConfig(level=logging.INFO)


async def main():
    """
    This script rebuilds the search index from scratch.
    It deletes the old index and then re-indexes all published posts.
    """
    logging.info("Connecting to database...")
    await db.connect()
    await vector_manager.connect()

    index_name = vector_manager.index_name
    logging.warning(f"This will delete and rebuild the '{index_name}' index.")

    try:
        logging.info(f"Deleting existing index '{index_name}'...")
        await db.redis_client.execute_command("FT.DROPINDEX", index_name)
        logging.info("Index deleted successfully.")
    except Exception as e:
        logging.warning(f"Could not delete index (it might not exist): {e}")

    logging.info("Starting to rebuild index by re-indexing all posts...")
    await Post.recreate_search_index()

    logging.info("Index rebuild process completed.")

    await db.disconnect()
    await vector_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
