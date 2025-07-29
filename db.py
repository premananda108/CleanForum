"""
Database connection and utilities.
Handles all interactions with the Redis database.
"""
import os
import logging
from redis import asyncio as redis
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.field import VectorField, TagField, TextField
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# --- Redis Client Singleton ---
class RedisClient:
    _instance = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6380")
            logger.info(f"Connecting to Redis at {redis_url}...")
            try:
                client = redis.from_url(redis_url, decode_responses=True)
                await client.ping()
                cls._instance = client
                logger.info("Successfully connected to Redis.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                cls._instance = None
        return cls._instance

async def create_redis_index(
    redis_client: redis.Redis,
    index_name: str,
    vector_dim: int,
    prefix: str = "post_vector:"
):
    """Creates a RediSearch index for vector search if it doesn't exist."""
    try:
        await redis_client.ft(index_name).info()
        logger.info(f"Index '{index_name}' already exists.")
    except Exception:
        logger.info(f"Index '{index_name}' not found, creating new one.")
        schema = (
            VectorField("vector", "HNSW", {"TYPE": "FLOAT32", "DIM": vector_dim, "DISTANCE_METRIC": "COSINE"}),
            TagField("label"),
            TextField("title"),
            TagField("url")
        )
        definition = IndexDefinition(prefix=[prefix], index_type=IndexType.HASH)
        await redis_client.ft(index_name).create_index(fields=schema, definition=definition)
        logger.info(f"Index '{index_name}' created successfully.")

async def get_all_posts(redis_client: redis.Redis, prefix: str = "forum_post:"):
    """Retrieves all forum posts from Redis."""
    try:
        post_keys = [key async for key in redis_client.scan_iter(f"{prefix}*")]
        if not post_keys:
            return []
        posts_json = await redis_client.mget(post_keys)
        # Filter out potential None values if a key expires between scan and mget
        return [post for post in posts_json if post is not None]
    except Exception as e:
        logger.error(f"Error fetching posts from Redis: {e}")
        return []

async def save_post(redis_client: redis.Redis, post_id: str, post_data: str, prefix: str = "forum_post:"):
    """Saves a single forum post to Redis."""
    try:
        await redis_client.set(f"{prefix}{post_id}", post_data)
    except Exception as e:
        logger.error(f"Error saving post to Redis: {e}")
        raise

