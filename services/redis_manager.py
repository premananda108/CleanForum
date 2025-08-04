"""
Redis manager for working with Vector Sets
"""
import redis.asyncio as redis
import numpy as np
from typing import List, Dict, Any, Optional
import json
import logging
from config import settings

class RedisVectorManager:
    """Manager for working with Redis Vector Sets"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.index_name = settings.VECTOR_INDEX_NAME
        self.vector_dim = settings.VECTOR_DIM

    async def connect(self):
        """Connect to Redis"""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            decode_responses=False  # Important! For working with binary data
        )

        await self.redis_client.ping()
        logging.info("Vector Manager: successfully connected to Redis.")

        # Create the index if it doesn't exist
        await self.create_index()

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.aclose()

    async def create_index(self):
        """Create an index for vector search"""
        try:
            # Check if the index exists
            await self.redis_client.execute_command("FT.INFO", self.index_name)
            logging.info(f"Index {self.index_name} already exists")
        except:
            # Create a new index
            schema = [
                "vector", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(self.vector_dim),
                "DISTANCE_METRIC", "COSINE",
                "title", "TEXT",
                "content", "TEXT"
            ]

            await self.redis_client.execute_command(
                "FT.CREATE", self.index_name,
                "ON", "HASH",
                "PREFIX", "2", "vector:post:", "vector:comment:",
                "SCHEMA", *schema
            )
            logging.info(f"Created vector index {self.index_name}")

    async def add_vector(self, doc_id: str, vector: np.ndarray,
                        title: str, content: str) -> bool:
        """Add a vector to the index"""
        try:
            doc_key = f"vector:{doc_id}"

            # Prepare the data
            vector_bytes = vector.astype(np.float32).tobytes()

            # Save the document
            await self.redis_client.hset(doc_key, mapping={
                "vector": vector_bytes,
                "title": title.encode('utf-8'),
                "content": content[:500].encode('utf-8'),  # Limit and encode
                "doc_id": doc_id.encode('utf-8')
            })

            return True

        except Exception as e:
            logging.error(f"Vector Manager: error adding vector {doc_id}: {e}")
            return False

    async def search_similar(
        self, query_vector: np.ndarray, k: int = 9, pre_filter: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors with the possibility of pre-filtering.
        pre_filter: Dictionary for filtering, e.g., {"label": "published"}
        """
        try:
            query_bytes = query_vector.astype(np.float32).tobytes()

            # Form the filter string if it exists
            filter_str = "*"
            if pre_filter:
                # Example: (@label:{published})
                filter_parts = [f"(@{field}:{{{value}}})" for field, value in pre_filter.items()]
                filter_str = "".join(filter_parts)

            # Combine the filter with the KNN query
            query = f"{filter_str}=>[KNN {k} @vector $blob AS score]"

            logging.debug(f"Executing vector search query: {query}")

            results = await self.redis_client.execute_command(
                "FT.SEARCH", self.index_name, query,
                "PARAMS", "2", "blob", query_bytes,
                "DIALECT", "2",
                "RETURN", "3", "score", "title", "doc_id"
            )

            # Parse the results
            parsed_results = []
            if len(results) > 1:
                for i in range(1, len(results), 2):
                    if i + 1 < len(results):
                        doc_data = results[i + 1]
                        if len(doc_data) >= 6:
                            parsed_results.append({
                                "doc_id": doc_data[5].decode(errors='ignore'),
                                "score": float(doc_data[1]),
                                "title": doc_data[3].decode(errors='ignore')
                            })
            return parsed_results

        except Exception as e:
            logging.error(f"Vector Manager: search error: {e}", exc_info=True)
            return []

    async def get_index_info(self) -> Dict[str, Any]:
        """Get information about the index"""
        try:
            info = await self.redis_client.execute_command("FT.INFO", self.index_name)

            # Parse the index information
            index_info = {}
            for i in range(0, len(info), 2):
                if i + 1 < len(info):
                    key = info[i].decode() if isinstance(info[i], bytes) else info[i]
                    value = info[i + 1]
                    if isinstance(value, bytes):
                        value = value.decode()
                    index_info[key] = value

            return index_info

        except Exception as e:
            logging.error(f"Vector Manager: error getting index information: {e}")
            return {}

    async def get_vector_by_id(self, doc_id: str) -> Optional[np.ndarray]:
        """Get a vector by document ID"""
        try:
            doc_key = f"vector:{doc_id}"
            vector_bytes = await self.redis_client.hget(doc_key, "vector")

            if not vector_bytes:
                logging.warning(f"Vector Manager: vector for {doc_id} not found.")
                return None

            return np.frombuffer(vector_bytes, dtype=np.float32)

        except Exception as e:
            logging.error(f"Vector Manager: error getting vector {doc_id}: {e}")
            return None

    async def delete_vector(self, doc_id: str) -> bool:
        """Delete a vector from the index"""
        try:
            doc_key = f"vector:{doc_id}"
            await self.redis_client.delete(doc_key)
            return True
        except Exception as e:
            logging.error(f"Vector Manager: error deleting vector {doc_id}: {e}")
            return False

# Global manager instance
vector_manager = RedisVectorManager()