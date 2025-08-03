#!/usr/bin/env python3
"""
Скрипт для начального заполнения базы данных из JSON файлов.
Создает тестовых пользователей, категории и посты БЕЗ проверки на спам.
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
import os

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

            # Создаем посты из JSON файлов
            await self.create_posts_from_json_files()

            # Выводим статистику
            await self.print_statistics()

            # Запускаем анализ созданных постов
            await self._analyze_created_posts()

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

    async def create_posts_from_json_files(self):
        """Создание постов из файлов default_spam_dataset.json и default_dataset.json"""
        logging.info("📝 Создаем посты из JSON файлов...")

        datasets = ["default_spam_dataset.json", "default_dataset.json"]
        posts_created = 0
        spam_posts_created = 0
        legit_posts_created = 0

        for filename in datasets:
            if not os.path.exists(filename):
                logging.warning(f"Файл данных {filename} не найден, пропускаем.")
                continue

            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not content:
                        logging.warning(f"Файл {filename} пуст, пропускаем.")
                        continue
                    dataset = json.loads(content)
            except json.JSONDecodeError as e:
                logging.error(f"Ошибка чтения JSON файла {filename}: {e}")
                continue

            if not dataset:
                logging.info(f"Файл {filename} не содержит постов.")
                continue

            logging.info(f"Загружаем посты из {filename}...")
            for post_data in dataset:
                try:
                    if not self.created_users:
                        logging.error("Нет созданных пользователей для назначения авторами.")
                        return
                    author_id = random.choice(self.created_users)

                    # Определяем категорию
                    category_name = post_data.get("category")
                    category_id = self.get_category_id_by_name(category_name)

                    if not category_id:
                        category_id = self.choose_category_by_tags(post_data.get("tags", []))

                    post_create = PostCreate(
                        title=post_data["title"],
                        content=post_data["content"],
                        category_id=category_id,
                        tags=post_data.get("tags", [])
                    )

                    is_spam = post_data.get("label") == "spam"

                    post_id = await self.create_post_without_spam_check(
                        post_create,
                        author_id,
                        is_spam=is_spam
                    )

                    if post_id:
                        posts_created += 1
                        if is_spam:
                            spam_posts_created += 1
                        else:
                            legit_posts_created += 1
                        logging.info(f"✓ Создан пост: {post_data['title'][:50]}... (ID: {post_id}, спам: {is_spam})")

                except Exception as e:
                    logging.error(
                        f"Ошибка создания поста '{post_data.get('title', 'Без названия')}' из файла {filename}: {e}",
                        exc_info=True)

        logging.info(f"📊 Всего создано постов из файлов: {posts_created}")
        logging.info(f"    -> Легитимных: {legit_posts_created}")
        logging.info(f"    -> Спам: {spam_posts_created}")

    def get_category_id_by_name(self, name: str) -> str:
        """Возвращает ID категории по её имени"""
        if not name:
            return ""
        # Предполагается, что TEST_CATEGORIES и self.created_categories имеют одинаковый порядок
        try:
            index = [cat['name'] for cat in TEST_CATEGORIES].index(name)
            if index < len(self.created_categories):
                return self.created_categories[index]
        except ValueError:
            return ""
        return ""

    def choose_category_by_tags(self, tags: List[str]) -> str:
        """Выбор категории на основе тегов поста"""
        if not self.created_categories:
            return ""

        tech_tags = ["технологии", "ии", "программирование", "машинное_обучение", "камера", "фотография"]
        health_tags = ["здоровье", "питание", "диета", "похудение", "таблетки"]
        finance_tags = ["финансы", "деньги", "заработок", "bitcoin", "криптовалюта", "forex", "кредит", "трейдинг"]

        lower_tags = [tag.lower() for tag in tags]

        if any(tag in lower_tags for tag in tech_tags):
            return self.created_categories[1] if len(self.created_categories) > 1 else self.created_categories[0]
        elif any(tag in lower_tags for tag in finance_tags):
            return self.created_categories[2] if len(self.created_categories) > 2 else self.created_categories[0]
        elif any(tag in lower_tags for tag in health_tags):
            return self.created_categories[3] if len(self.created_categories) > 3 else self.created_categories[0]

        return random.choice([self.created_categories[0], self.created_categories[4]]) if len(
            self.created_categories) > 4 else self.created_categories[0]

    async def create_post_without_spam_check(self, post_data: PostCreate, author_id: str, is_spam: bool = False) -> str:
        """
        Создание поста БЕЗ проверки на спам (для заполнения тестовыми данными).
        Версия, обновленная для работы с Markdown.
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()

        # Контент уже является Markdown текстом
        text_content = post_data.content
        status = PostStatus.SPAM if is_spam else PostStatus.PUBLISHED

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": text_content,  # Сохраняем Markdown напрямую
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": random.randint(10, 1000),
            "comment_count": random.randint(0, 50),
            "vote_score": random.randint(-5, 20),
            "is_spam": str(is_spam),
            "spam_score": 0.95 if is_spam else random.uniform(0.01, 0.2),
            "reading_time": Post.calculate_reading_time(text_content)
        }

        # Устанавливаем случайную дату создания для реалистичности
        days_ago = random.randint(1, 30)
        random_date = datetime.now() - timedelta(days=days_ago)
        post_info["created_at"] = random_date.isoformat()
        post_info["updated_at"] = random_date.isoformat()

        # Сохраняем в Redis
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = random_date.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
            if is_spam:
                pipe.sadd("posts:spam", post_id)
            await pipe.execute()

        # Добавляем вектор в поисковый индекс
        try:
            if not vector_classifier.is_initialized:
                await vector_classifier.initialize()

            post_vector = vector_classifier.create_vector(post_data.title, text_content, post_data.tags)

            await vector_manager.add_vector(
                doc_id=f"post:{post_id}",
                vector=post_vector,
                title=post_data.title,
                content=text_content
            )
        except Exception as e:
            logging.warning(f"Не удалось добавить пост {post_id} в поисковый индекс: {e}")

        # Обновляем счетчики
        await User.update_stats(author_id, post_count_delta=1)
        await Category.update_post_count(post_data.category_id, 1)

        return post_id

    async def print_statistics(self):
        """Вывод статистики созданных данных"""
        logging.info("📊 Статистика созданных данных:")
        total_users = len(self.created_users)
        logging.info(f"👥 Пользователей: {total_users}")
        total_categories = len(self.created_categories)
        logging.info(f"📁 Категорий: {total_categories}")
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        legitimate_posts = total_posts - spam_posts
        logging.info(f"📝 Всего постов: {total_posts}")
        logging.info(f"🚫 Спам-постов: {spam_posts}")
        logging.info(f"✅ Легитимных постов: {legitimate_posts}")
        try:
            index_info = await vector_manager.get_index_info()
            vector_count = index_info.get("num_docs", 0)
            logging.info(f"🔍 Векторов в поисковом индексе: {vector_count}")
        except Exception as e:
            logging.warning(f"Не удалось получить статистику векторного индекса: {e}")

    async def _analyze_created_posts(self):
        """Запускает анализ всех постов, у которых нет анализа."""
        logging.info("🔬 Запускаем анализ спама для всех созданных постов...")

        # Получаем все посты, которые были созданы в рамках этого скрипта или уже существовали.
        # Поскольку мы не знаем точно, какие из них новые, просто перебираем все.
        # В реальной системе это был бы более сложный фоновый процесс.
        all_post_ids = await db.zrevrange("posts:all", 0, -1)

        analyzed_count = 0
        skipped_count = 0

        for post_id in all_post_ids:
            try:
                # Проверяем, существует ли уже анализ
                analysis_exists = await db.exists(f"vector_analysis:post:{post_id}")
                if not analysis_exists:
                    post = await Post.get_by_id(post_id)
                    if post:
                        await vector_classifier.analyze_with_vectors(
                            post.id, post.title, post.content, post.tags, post.author_id
                        )
                        analyzed_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logging.error(f"Ошибка при анализе поста {post_id}: {e}")

        logging.info(f"🔬 Анализ завершен. Проанализировано: {analyzed_count}, пропущено (уже были): {skipped_count}")


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