import asyncio
import json
import uuid
import logging

from models.database import db
from services.vector_classifier import vector_classifier, vector_manager
from models.post import Post, PostCreate
from models.category import Category, CategoryCreate

# Настраиваем базовое логирование для скрипта
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def seed_database():
    """Заполняет базу данных начальными данными из spam_dataset.json"""
    logging.info("Начало заполнения базы данных...")

    try:
        # 1. Подключаемся к зависимостям
        await db.connect()
        await vector_classifier.initialize()

        if not vector_classifier.is_initialized:
            logging.error("Векторный классификатор не инициализирован. Прерывание.")
            return

        # 2. Загружаем датасет
        logging.info(f"Чтение файла spam_dataset.json...")
        with open('spam_dataset.json', 'r', encoding='utf-8') as f:
            dataset = json.load(f)

        logging.info(f"Найдено {len(dataset)} постов для загрузки.")

        # 3. Создаем категории
        created_categories = {}
        for item in dataset:
            cat_name = item.get("category", "Общие")
            if cat_name not in created_categories:
                try:
                    existing_category = await Category.get_by_name(cat_name)
                    if existing_category:
                        cat_id = existing_category.id
                        logging.info(f"Категория '{cat_name}' уже существует.")
                    else:
                        cat_data = CategoryCreate(name=cat_name, description=f"Описание для {cat_name}")
                        cat_id = await Category.create(cat_data)
                        logging.info(f"Создана категория: '{cat_name}'")
                    created_categories[cat_name] = cat_id
                except Exception as e:
                    logging.error(f"Ошибка при создании категории '{cat_name}': {e}")
                    created_categories[cat_name] = None

        # 4. Создаем посты и их векторы
        for i, item in enumerate(dataset):
            try:
                cat_name = item.get("category", "Общие")
                category_id = created_categories.get(cat_name)

                if not category_id:
                    logging.warning(f"Пропуск поста '{item['title']}' из-за отсутствия категории.")
                    continue

                post_data = PostCreate(
                    title=item['title'],
                    content=item['content'],
                    category_id=category_id,
                    tags=item.get('tags', [])
                )
                author_id = f"user_seed_{uuid.uuid4().hex[:8]}"

                # Создаем основной пост
                post_id = await Post.create(post_data, author_id)

                # Создаем и сохраняем вектор
                vector = vector_classifier.create_vector(post_data.title, post_data.content, post_data.tags)
                label = "spam" if item['is_spam'] else "legitimate"
                
                await vector_manager.add_vector(
                    post_id, vector, label, post_data.title, post_data.content[:200]
                )
                logging.info(f"({i+1}/{len(dataset)}) Пост '{item['title']}' ({label}) успешно загружен.")

            except Exception as e:
                logging.error(f"Ошибка при обработке поста '{item['title']}': {e}", exc_info=False)

    finally:
        # 5. Отключаемся от Redis
        await db.disconnect()
        logging.info("Заполнение базы данных завершено.")

if __name__ == "__main__":
    # Проверяем, что Redis запущен, перед стартом
    try:
        import redis
        r = redis.Redis(host= 'localhost', port=6379)
        r.ping()
    except redis.exceptions.ConnectionError:
        logging.error("Не удалось подключиться к Redis. Убедитесь, что Docker-контейнер запущен.")
    else:
        asyncio.run(seed_database())