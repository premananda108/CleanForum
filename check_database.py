#!/usr/bin/env python3
"""
Скрипт для быстрой проверки созданных данных в базе
"""
import asyncio
import logging
from models.database import db
from models.post import Post
from models.user import User
from models.category import Category
from services.redis_manager import vector_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def check_database():
    """Проверка содержимого базы данных"""
    logging.info("🔍 Проверка содержимого базы данных")
    logging.info("=" * 50)
    
    await db.connect()
    
    try:
        # Проверяем общие статистики
        logging.info("📊 ОБЩАЯ СТАТИСТИКА:")
        
        # Количество ключей в Redis
        keys_count = await db.redis_client.dbsize()
        logging.info(f"🗄️  Всего ключей в Redis: {keys_count}")
        
        # Статистика постов
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        published_posts = await Post.count_published()
        
        logging.info(f"📝 Всего постов: {total_posts}")
        logging.info(f"✅ Опубликованных: {published_posts}")
        logging.info(f"🚫 Спам-постов: {spam_posts}")
        
        # Проверяем пользователей
        logging.info("\n👥 ПОЛЬЗОВАТЕЛИ:")
        test_usernames = ["alice_blogger", "bob_writer", "charlie_spam", "diana_expert", "moderator_1"]
        
        for username in test_usernames:
            user = await User.get_by_username(username)
            if user:
                logging.info(f"✓ {username} (ID: {user.id}, роль: {user.role.value}, постов: {user.post_count})")
            else:
                logging.warning(f"❌ {username} не найден")
        
        # Проверяем категории
        logging.info("\n📁 КАТЕГОРИИ:")
        categories = await Category.get_all()
        for category in categories:
            posts_in_category = len(await Post.get_by_category(category.id, limit=100))
            logging.info(f"✓ {category.name} (ID: {category.id}, постов: {posts_in_category})")
        
        # Проверяем последние посты
        logging.info("\n📝 ПОСЛЕДНИЕ ПОСТЫ:")
        recent_posts = await Post.get_all(limit=5)
        for i, post in enumerate(recent_posts, 1):
            status_emoji = "🚫" if post.status.value == "spam" else "✅"
            logging.info(f"{i}. {status_emoji} '{post.title[:50]}...' (автор: {post.author_username}, статус: {post.status.value})")
        
        # Проверяем векторный индекс
        logging.info("\n🔍 ВЕКТОРНЫЙ ПОИСКОВЫЙ ИНДЕКС:")
        try:
            await vector_manager.connect()
            index_info = await vector_manager.get_index_info()
            
            if index_info:
                logging.info(f"✓ Индекс существует: {vector_manager.index_name}")
                logging.info(f"📊 Векторов в индексе: {index_info.get('num_docs', 'N/A')}")
                logging.info(f"💾 Размер индекса: {index_info.get('inverted_sz_mb', 'N/A')} MB")
            else:
                logging.warning("❌ Векторный индекс не найден")
                
        except Exception as e:
            logging.error(f"❌ Ошибка проверки векторного индекса: {e}")
        
        # Тестируем поиск
        logging.info("\n🔎 ТЕСТИРОВАНИЕ ПОИСКА:")
        try:
            search_results = await Post.search_by_text("заработок", limit=3)
            logging.info(f"Поиск по слову 'заработок': найдено {len(search_results)} результатов")
            for result in search_results:
                logging.info(f"  - '{result.title[:40]}...'")
        except Exception as e:
            logging.error(f"❌ Ошибка тестирования поиска: {e}")
        
        logging.info("\n" + "=" * 50)
        logging.info("✅ Проверка базы данных завершена")
        
    except Exception as e:
        logging.error(f"❌ Ошибка при проверке базы: {e}", exc_info=True)
    finally:
        await db.disconnect()

async def main():
    """Главная функция"""
    await check_database()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Проверка прервана пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}", exc_info=True)
