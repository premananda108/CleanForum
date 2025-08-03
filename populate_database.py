#!/usr/bin/env python3
"""
Скрипт для начального заполнения базы данных из spam_dataset.json
Создает тестовых пользователей, категории и посты БЕЗ проверки на спам
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

from models.database import db
from models.post import Post, PostCreate, PostStatus
from models.user import User, UserCreate, UserRole
from models.category import Category, CategoryCreate
from services.vector_classifier import vector_classifier
from services.redis_manager import vector_manager
from config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Тестовые пользователи для создания
TEST_USERS = [
    {
        "username": "alice_blogger",
        "email": "alice@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "bob_writer", 
        "email": "bob@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "charlie_spam",
        "email": "charlie@example.com", 
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "diana_expert",
        "email": "diana@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "moderator_1",
        "email": "mod1@example.com",
        "password": "password123", 
        "role": UserRole.MODERATOR
    }
]

# Категории для создания
TEST_CATEGORIES = [
    {
        "name": "Общие",
        "description": "Разговоры на любые темы"
    },
    {
        "name": "Технологии", 
        "description": "Все о высоких технологиях"
    },
    {
        "name": "Финансы",
        "description": "Обсуждение финансовых вопросов"
    },
    {
        "name": "Здоровье",
        "description": "Вопросы здоровья и медицины"
    },
    {
        "name": "Флуд",
        "description": "Для несерьезных обсуждений"
    }
]

# Дополнительные легитимные посты
LEGITIMATE_POSTS = [
    {
        "title": "Обзор новых технологий в области машинного обучения",
        "content": "Современное машинное обучение развивается очень быстро. В этом году мы увидели множество интересных разработок в области нейронных сетей, особенно в сфере обработки естественного языка. Большие языковые модели становятся все более мощными и находят применение в различных областях - от автоматизации задач до творческой деятельности.",
        "tags": ["машинное_обучение", "технологии", "ИИ"],
        "label": "legitimate"
    },
    {
        "title": "Рецепт домашней пиццы",
        "content": "Сегодня хочу поделиться проверенным рецептом пиццы, которую легко приготовить дома. Для теста понадобится: мука, вода, дрожжи, соль и немного оливкового масла. Замешиваем тесто, даем подойти 2 часа. Для соуса используем томаты, базилик, чеснок. Выпекаем при высокой температуре 220-250 градусов.",
        "tags": ["рецепт", "кулинария", "пицца"],
        "label": "legitimate"
    },
    {
        "title": "Как выбрать хороший фотоаппарат для начинающих",
        "content": "При выборе первого фотоаппарата важно учесть несколько факторов: бюджет, цели съемки, размер и вес камеры. Для начинающих рекомендую обратить внимание на беззеркальные камеры - они компактнее зеркальных, но при этом дают отличное качество изображения. Важные параметры: размер матрицы, количество мегапикселей, стабилизация изображения.",
        "tags": ["фотография", "камера", "советы"],
        "label": "legitimate"
    },
    {
        "title": "Основы здорового питания",
        "content": "Здоровое питание - это основа хорошего самочувствия. Важно включать в рацион разнообразные продукты: овощи, фрукты, цельные злаки, белковые продукты. Рекомендуется есть 5-6 раз в день небольшими порциями, пить достаточно воды, ограничить потребление сахара и обработанных продуктов.",
        "tags": ["здоровье", "питание", "диета"],
        "label": "legitimate"
    },
    {
        "title": "Лучшие книги по программированию",
        "content": "Для изучения программирования рекомендую несколько классических книг: 'Чистый код' Роберта Мартина, 'Совершенный код' Стива Макконнелла, 'Алгоритмы: построение и анализ' Кормена. Эти книги помогут не только изучить синтаксис языка, но и понять принципы написания качественного кода.",
        "tags": ["программирование", "книги", "обучение"],
        "label": "legitimate"
    }
]

class DatabasePopulator:
    """Класс для заполнения базы данных тестовыми данными"""
    
    def __init__(self):
        self.created_users = []
        self.created_categories = []
        
    async def populate_all(self):
        """Основной метод для заполнения всей базы"""
        logging.info("🚀 Начинаем заполнение базы данных...")
        
        # Подключаемся к БД
        await db.connect()
        await vector_classifier.initialize()
        
        try:
            # Создаем пользователей
            await self.create_users()
            
            # Создаем категории
            await self.create_categories()
            
            # Создаем посты из датасета
            await self.create_posts_from_dataset()
            
            # Создаем дополнительные легитимные посты
            await self.create_legitimate_posts()
            
            # Выводим статистику
            await self.print_statistics()
            
            logging.info("✅ Заполнение базы данных завершено успешно!")
            
        except Exception as e:
            logging.error(f"❌ Ошибка при заполнении базы: {e}", exc_info=True)
        finally:
            await db.disconnect()
    
    async def create_users(self):
        """Создание тестовых пользователей"""
        logging.info("👥 Создаем тестовых пользователей...")
        
        for user_data in TEST_USERS:
            try:
                # Проверяем, существует ли пользователь
                existing_user = await User.get_by_username(user_data["username"])
                if existing_user:
                    logging.info(f"Пользователь {user_data['username']} уже существует, пропускаем")
                    self.created_users.append(existing_user.id)
                    continue
                
                user_create = UserCreate(
                    username=user_data["username"],
                    email=user_data["email"], 
                    password=user_data["password"]
                )
                
                user_id = await User.create(user_create, user_data["role"])
                self.created_users.append(user_id)
                
                # Устанавливаем случайную дату создания (от 30 до 365 дней назад)
                days_ago = random.randint(30, 365)
                creation_date = datetime.now() - timedelta(days=days_ago)
                await db.hset(f"user:{user_id}", "created_at", creation_date.isoformat())
                
                logging.info(f"✓ Создан пользователь: {user_data['username']} (ID: {user_id})")
                
            except Exception as e:
                logging.error(f"Ошибка создания пользователя {user_data['username']}: {e}")
    
    async def create_categories(self):
        """Создание тестовых категорий"""
        logging.info("📁 Создаем категории...")
        
        for cat_data in TEST_CATEGORIES:
            try:
                # Проверяем, существует ли категория
                existing_categories = await Category.get_all()
                existing_names = [cat.name for cat in existing_categories]
                
                if cat_data["name"] in existing_names:
                    logging.info(f"Категория '{cat_data['name']}' уже существует, пропускаем")
                    # Находим ID существующей категории
                    for cat in existing_categories:
                        if cat.name == cat_data["name"]:
                            self.created_categories.append(cat.id)
                            break
                    continue
                
                category_create = CategoryCreate(
                    name=cat_data["name"],
                    description=cat_data["description"]
                )
                
                category_id = await Category.create(category_create)
                self.created_categories.append(category_id)
                
                logging.info(f"✓ Создана категория: {cat_data['name']} (ID: {category_id})")
                
            except Exception as e:
                logging.error(f"Ошибка создания категории {cat_data['name']}: {e}")
    
    async def create_posts_from_dataset(self):
        """Создание постов из spam_dataset.json"""
        logging.info("📝 Создаем посты из датасета...")
        
        # Загружаем данные из файла
        try:
            with open("spam_dataset.json", "r", encoding="utf-8") as f:
                dataset = json.load(f)
        except FileNotFoundError:
            logging.error("Файл spam_dataset.json не найден!")
            return
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка чтения JSON файла: {e}")
            return
        
        spam_posts_created = 0
        
        for post_data in dataset:
            try:
                # Выбираем случайного автора
                author_id = random.choice(self.created_users)
                
                # Выбираем случайную категорию
                category_id = random.choice(self.created_categories)
                
                # Создаем PostCreate объект
                post_create = PostCreate(
                    title=post_data["title"],
                    content=post_data["content"],
                    category_id=category_id,
                    tags=post_data.get("tags", [])
                )
                
                # Создаем пост БЕЗ проверки на спам
                post_id = await self.create_post_without_spam_check(
                    post_create, 
                    author_id,
                    is_spam=(post_data["label"] == "spam")
                )
                
                if post_id:
                    if post_data["label"] == "spam":
                        spam_posts_created += 1
                    logging.info(f"✓ Создан пост: {post_data['title'][:50]}... (ID: {post_id}, спам: {post_data['label'] == 'spam'})")
                
            except Exception as e:
                logging.error(f"Ошибка создания поста '{post_data.get('title', 'Без названия')}': {e}")
        
        logging.info(f"📊 Создано {spam_posts_created} спам-постов из датасета")
    
    async def create_legitimate_posts(self):
        """Создание дополнительных легитимных постов"""
        logging.info("📝 Создаем дополнительные легитимные посты...")
        
        legitimate_posts_created = 0
        
        for post_data in LEGITIMATE_POSTS:
            try:
                # Выбираем случайного автора (исключая спаммеров для легитимных постов)
                legitimate_authors = [uid for uid in self.created_users[:4]]  # Первые 4 - не спаммеры
                author_id = random.choice(legitimate_authors)
                
                # Выбираем подходящую категорию на основе тегов
                category_id = self.choose_category_by_tags(post_data["tags"])
                
                post_create = PostCreate(
                    title=post_data["title"],
                    content=post_data["content"], 
                    category_id=category_id,
                    tags=post_data["tags"]
                )
                
                post_id = await self.create_post_without_spam_check(
                    post_create,
                    author_id, 
                    is_spam=False
                )
                
                if post_id:
                    legitimate_posts_created += 1
                    logging.info(f"✓ Создан легитимный пост: {post_data['title'][:50]}... (ID: {post_id})")
                
            except Exception as e:
                logging.error(f"Ошибка создания легитимного поста '{post_data.get('title', 'Без названия')}': {e}")
        
        logging.info(f"📊 Создано {legitimate_posts_created} дополнительных легитимных постов")
    
    def choose_category_by_tags(self, tags: List[str]) -> str:
        """Выбор категории на основе тегов поста"""
        if not self.created_categories:
            return random.choice(self.created_categories) if self.created_categories else "general"
        
        # Простая логика выбора категории на основе тегов
        tech_tags = ["технологии", "ИИ", "программирование", "машинное_обучение", "камера", "фотография"]
        health_tags = ["здоровье", "питание", "диета"]
        general_tags = ["рецепт", "кулинария", "советы", "книги", "обучение"]
        
        for tag in tags:
            if any(tech_tag in tag.lower() for tech_tag in tech_tags):
                # Ищем категорию "Технологии"
                return self.created_categories[1] if len(self.created_categories) > 1 else self.created_categories[0]
            elif any(health_tag in tag.lower() for health_tag in health_tags):
                # Ищем категорию "Здоровье"  
                return self.created_categories[3] if len(self.created_categories) > 3 else self.created_categories[0]
        
        # По умолчанию - общая категория
        return self.created_categories[0] if self.created_categories else "general"
    
    async def create_post_without_spam_check(self, post_data: PostCreate, author_id: str, is_spam: bool = False) -> str:
        """
        Создание поста БЕЗ проверки на спам (для заполнения тестовыми данными)
        Копирует логику Post.create(), но пропускает анализ спама
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Извлекаем чистый текст
        text_content = Post._extract_text_from_editorjs(post_data.content)
        
        # Устанавливаем статус на основе параметра is_spam
        status = PostStatus.SPAM if is_spam else PostStatus.PUBLISHED
        
        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": text_content,
            "content_json": post_data.content,
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": 0,
            "comment_count": 0,
            "vote_score": 0,
            "is_spam": str(is_spam),
            "spam_score": 0.9 if is_spam else 0.1,  # Фиксированные значения для тестов
            "reading_time": Post.calculate_reading_time(text_content)
        }
        
        # Случайная дата создания (от 1 до 30 дней назад)
        days_ago = random.randint(1, 30)
        random_date = datetime.now() - timedelta(days=days_ago)
        post_info["created_at"] = random_date.isoformat()
        post_info["updated_at"] = random_date.isoformat()
        
        # Сохраняем пост в Redis
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = random_date.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
            
            # Если спам - добавляем в множество спама
            if is_spam:
                pipe.sadd("posts:spam", post_id)
                
            await pipe.execute()
        
        # Создаем вектор и добавляем в поисковый индекс
        try:
            if not vector_classifier.is_initialized:
                await vector_classifier.initialize()
            
            post_vector = vector_classifier.create_vector(post_data.title, text_content, post_data.tags)
            
            await vector_manager.add_vector(
                doc_id=f"post:{post_id}",
                vector=post_vector,
                label=status.value,
                title=post_data.title,
                content=text_content
            )
            
        except Exception as e:
            logging.warning(f"Не удалось добавить пост {post_id} в поисковый индекс: {e}")
        
        # Обновляем счетчик постов у автора
        await User.update_stats(author_id, post_count_delta=1)
        
        # Обновляем счетчик в категории
        await Category.update_post_count(post_data.category_id, 1)
        
        return post_id
    
    async def print_statistics(self):
        """Вывод статистики созданных данных"""
        logging.info("📊 Статистика созданных данных:")
        
        # Статистика пользователей
        total_users = len(self.created_users)
        logging.info(f"👥 Пользователей: {total_users}")
        
        # Статистика категорий  
        total_categories = len(self.created_categories)
        logging.info(f"📁 Категорий: {total_categories}")
        
        # Статистика постов
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        legitimate_posts = total_posts - spam_posts
        
        logging.info(f"📝 Всего постов: {total_posts}")
        logging.info(f"🚫 Спам-постов: {spam_posts}")
        logging.info(f"✅ Легитимных постов: {legitimate_posts}")
        
        # Статистика векторного индекса
        try:
            index_info = await vector_manager.get_index_info()
            vector_count = index_info.get("num_docs", 0)
            logging.info(f"🔍 Векторов в поисковом индексе: {vector_count}")
        except Exception as e:
            logging.warning(f"Не удалось получить статистику векторного индекса: {e}")


async def main():
    """Главная функция скрипта"""
    logging.info("🎯 Скрипт заполнения базы данных")
    logging.info("=" * 50)
    
    populator = DatabasePopulator()
    await populator.populate_all()
    
    logging.info("=" * 50)
    logging.info("🏁 Скрипт завершен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Скрипт прерван пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}", exc_info=True)
