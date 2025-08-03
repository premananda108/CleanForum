#!/usr/bin/env python3
"""
Скрипт для очистки базы данных Redis
ВНИМАНИЕ: Удаляет ВСЕ данные из базы!
"""
import asyncio
import logging
from models.database import db
from services.redis_manager import vector_manager
from config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def clear_database():
    """Полная очистка базы данных"""
    logging.warning("🚨 ВНИМАНИЕ: Начинается полная очистка базы данных!")
    
    # Подключаемся к Redis
    await db.connect()
    
    try:
        # Получаем статистику до очистки
        keys_count = await db.redis_client.dbsize()
        logging.info(f"📊 Количество ключей в базе до очистки: {keys_count}")
        
        # Удаляем векторный индекс
        try:
            await db.redis_client.execute_command("FT.DROPINDEX", settings.VECTOR_INDEX_NAME)
            logging.info("✓ Векторный индекс удален")
        except Exception as e:
            logging.info(f"Векторный индекс не найден или уже удален: {e}")
        
        # Очищаем всю базу данных
        await db.redis_client.flushdb()
        logging.info("✓ База данных полностью очищена")
        
        # Проверяем результат
        keys_count_after = await db.redis_client.dbsize()
        logging.info(f"📊 Количество ключей в базе после очистки: {keys_count_after}")
        
        logging.info("✅ Очистка базы данных завершена успешно!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка при очистке базы данных: {e}", exc_info=True)
    finally:
        await db.disconnect()

async def main():
    """Главная функция"""
    logging.info("🗑️  Скрипт очистки базы данных")
    logging.info("=" * 50)
    
    # Запрашиваем подтверждение
    confirmation = input("Вы уверены, что хотите удалить ВСЕ данные? Введите 'YES' для подтверждения: ")
    
    if confirmation == "YES":
        await clear_database()
    else:
        logging.info("❌ Операция отменена пользователем")
    
    logging.info("=" * 50)
    logging.info("🏁 Скрипт завершен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Скрипт прерван пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}", exc_info=True)
