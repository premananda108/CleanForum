"""
Redis менеджер для работы с Vector Sets
"""
import redis.asyncio as redis
import numpy as np
from typing import List, Dict, Any, Optional
import json
import logging
from config import settings

class RedisVectorManager:
    """Менеджер для работы с Redis Vector Sets"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.index_name = settings.VECTOR_INDEX_NAME
        self.vector_dim = settings.VECTOR_DIM

    async def connect(self):
        """Подключение к Redis"""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=False  # Важно! Для работы с бинарными данными
        )

        await self.redis_client.ping()
        logging.info("Vector Manager: успешно подключен к Redis.")

        # Создаем индекс если его нет
        await self.create_index()

    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.aclose()

    async def create_index(self):
        """Создать индекс для векторного поиска"""
        try:
            # Проверяем, существует ли индекс
            await self.redis_client.execute_command("FT.INFO", self.index_name)
            logging.info(f"Индекс {self.index_name} уже существует")
        except:
            # Создаем новый индекс
            schema = [
                "vector", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(self.vector_dim),
                "DISTANCE_METRIC", "COSINE",
                "label", "TAG",
                "title", "TEXT",
                "content", "TEXT"
            ]

            await self.redis_client.execute_command(
                "FT.CREATE", self.index_name,
                "ON", "HASH",
                "PREFIX", "2", "vector:post:", "vector:comment:",
                "SCHEMA", *schema
            )
            logging.info(f"Создан векторный индекс {self.index_name}")

    async def add_vector(self, doc_id: str, vector: np.ndarray, 
                        label: str, title: str, content: str) -> bool:
        """Добавить вектор в индекс"""
        try:
            doc_key = f"vector:{doc_id}"

            # Подготавливаем данные
            vector_bytes = vector.astype(np.float32).tobytes()

            # Сохраняем документ
            await self.redis_client.hset(doc_key, mapping={
                "vector": vector_bytes,
                "label": label,
                "title": title,
                "content": content[:500],  # Ограничиваем длину для индексации
                "doc_id": doc_id
            })

            return True

        except Exception as e:
            logging.error(f"Vector Manager: ошибка добавления вектора {doc_id}: {e}")
            return False

    async def search_similar(
        self, query_vector: np.ndarray, k: int = 9, pre_filter: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов с возможностью предварительной фильтрации.
        pre_filter: Словарь для фильтрации, например, {"label": "published"}
        """
        try:
            query_bytes = query_vector.astype(np.float32).tobytes()

            # Формируем строку фильтра, если она есть
            filter_str = "*"
            if pre_filter:
                # Пример: (@label:{published})
                filter_parts = [f"(@{field}:{{{value}}})" for field, value in pre_filter.items()]
                filter_str = "".join(filter_parts)

            # Объединяем фильтр с KNN запросом
            query = f"{filter_str}=>[KNN {k} @vector $blob AS score]"
            
            logging.debug(f"Executing vector search query: {query}")

            results = await self.redis_client.execute_command(
                "FT.SEARCH", self.index_name, query,
                "PARAMS", "2", "blob", query_bytes,
                "DIALECT", "2",
                "RETURN", "4", "score", "label", "title", "doc_id"
            )

            # Парсим результаты
            parsed_results = []
            if len(results) > 1:
                for i in range(1, len(results), 2):
                    if i + 1 < len(results):
                        doc_data = results[i + 1]
                        if len(doc_data) >= 8:
                            parsed_results.append({
                                "doc_id": doc_data[7].decode(errors='ignore'),
                                "score": float(doc_data[1]),
                                "label": doc_data[3].decode(errors='ignore'),
                                "title": doc_data[5].decode(errors='ignore')
                            })
            return parsed_results

        except Exception as e:
            logging.error(f"Vector Manager: ошибка поиска: {e}", exc_info=True)
            return []

    async def get_index_info(self) -> Dict[str, Any]:
        """Получить информацию об индексе"""
        try:
            info = await self.redis_client.execute_command("FT.INFO", self.index_name)

            # Парсим информацию об индексе
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
            logging.error(f"Vector Manager: ошибка получения информации об индексе: {e}")
            return {}

    async def get_vector_by_id(self, doc_id: str) -> Optional[np.ndarray]:
        """Получить вектор по ID документа"""
        try:
            doc_key = f"vector:{doc_id}"
            vector_bytes = await self.redis_client.hget(doc_key, "vector")

            if not vector_bytes:
                logging.warning(f"Vector Manager: вектор для {doc_id} не найден.")
                return None

            return np.frombuffer(vector_bytes, dtype=np.float32)

        except Exception as e:
            logging.error(f"Vector Manager: ошибка получения вектора {doc_id}: {e}")
            return None

    async def delete_vector(self, doc_id: str) -> bool:
        """Удалить вектор из индекса"""
        try:
            doc_key = f"vector:{doc_id}"
            await self.redis_client.delete(doc_key)
            return True
        except Exception as e:
            logging.error(f"Vector Manager: ошибка удаления вектора {doc_id}: {e}")
            return False

    async def update_vector_label(self, doc_id: str, new_label: str) -> bool:
        """Обновить метку (label) для существующего вектора."""
        try:
            doc_key = f"vector:{doc_id}"
            # Проверяем, существует ли документ
            if not await self.redis_client.exists(doc_key):
                logging.warning(f"Vector Manager: попытка обновить несуществующий вектор {doc_id}")
                return False

            # Обновляем только поле label
            await self.redis_client.hset(doc_key, "label", new_label)
            logging.info(f"Vector Manager: метка для вектора {doc_id} обновлена на '{new_label}'.")
            return True
        except Exception as e:
            logging.error(f"Vector Manager: ошибка обновления метки для вектора {doc_id}: {e}")
            return False

# Глобальный экземпляр менеджера
vector_manager = RedisVectorManager()