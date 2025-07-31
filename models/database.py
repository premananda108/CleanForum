"""
Менеджер базы данных Redis
"""
import redis.asyncio as redis
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.config import settings

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
        print(f"✅ Подключен к Redis {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            await self.redis_client.close()

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

    async def zrevrange(self, key: str, start: int = 0, end: int = -1, 
                       withscores: bool = False) -> List:
        """Получить элементы из отсортированного множества (по убыванию)"""
        return await self.redis_client.zrevrange(key, start, end, withscores=withscores)

# Глобальный экземпляр базы данных
db = RedisDatabase()
