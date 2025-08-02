"""
Менеджер базы данных Redis
"""
import redis.asyncio as redis
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import settings

class RedisDatabase:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        """Подключение к Redis"""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

        # Тестируем подключение
        await self.redis_client.ping()
        logging.info(f"Подключен к Redis {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.aclose()
            logging.info("Отключен от Redis.")

    async def get(self, key: str) -> Optional[str]:
        """Получить значение по ключу"""
        return await self.redis_client.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Установить значение по ключу"""
        return await self.redis_client.set(key, value, ex=ex)

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Получить поле из хеша"""
        return await self.redis_client.hget(key, field)

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        """Установить поля в хеше"""
        # Конвертируем все значения в строки
        str_mapping = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                      for k, v in mapping.items()}
        return await self.redis_client.hset(key, mapping=str_mapping)

    async def hgetall(self, key: str) -> Dict[str, str]:
        """Получить все поля хеша"""
        return await self.redis_client.hgetall(key)

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """Увеличить значение поля в хеше"""
        return await self.redis_client.hincrby(key, field, amount)

    async def delete(self, *keys: str) -> int:
        """Удалить ключи"""
        return await self.redis_client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа"""
        return bool(await self.redis_client.exists(key))

    async def incr(self, key: str) -> int:
        """Увеличить счетчик"""
        return await self.redis_client.incr(key)

    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Добавить в отсортированное множество"""
        return await self.redis_client.zadd(key, mapping)

    async def zrange(self, key: str, start: int = 0, end: int = -1, 
                      withscores: bool = False) -> List:
        """Получить элементы из отсортированного множества (по возрастанию)"""
        return await self.redis_client.zrange(key, start, end, withscores=withscores)

    async def zrevrange(self, key: str, start: int = 0, end: int = -1, 
                       withscores: bool = False) -> List:
        """Получить элементы из отсортированного множества (по убыванию)"""
        return await self.redis_client.zrevrange(key, start, end, withscores=withscores)

    async def zcard(self, key: str) -> int:
        """Получить количество элементов в отсортированном множестве."""
        return await self.redis_client.zcard(key)

    async def get_server_info(self) -> Dict[str, Any]:
        """Получить информацию о сервере Redis"""
        return await self.redis_client.info()

    async def scard(self, key: str) -> int:
        """Получить количество элементов в множестве"""
        return await self.redis_client.scard(key)

    async def sadd(self, key: str, *values: str) -> int:
        """Добавить элементы в множество"""
        return await self.redis_client.sadd(key, *values)

    async def srem(self, key: str, *values: str) -> int:
        """Удалить элементы из множества"""
        return await self.redis_client.srem(key, *values)

    async def flush_db(self):
        """Очистить текущую базу данных"""
        if self.redis_client:
            await self.redis_client.flushdb()

# Глобальный экземпляр базы данных
db = RedisDatabase()
