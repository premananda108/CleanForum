#!/usr/bin/env python3
"""
Скрипт настройки и запуска форума с анти-спам системой
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import redis.asyncio as redis
import requests


class ForumSetup:
    """Класс для настройки и инициализации форума"""

    def __init__(self):
        self.redis_client = None
        self.base_dir = Path(__file__).parent

    async def check_redis_connection(self, host='localhost', port=6379, max_retries=30):
        """Проверка подключения к Redis"""
        print(f"🔍 Проверка подключения к Redis {host}:{port}...")

        for attempt in range(max_retries):
            try:
                client = redis.Redis(host=host, port=port, decode_responses=False)
                await client.ping()
                print("✅ Redis подключен успешно!")
                self.redis_client = client
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⏳ Попытка {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(2)
                else:
                    print(f"❌ Не удалось подключиться к Redis: {e}")
                    return False

        return False

    async def initialize_test_data(self):
        """Инициализация тестовых данных"""
        print("📊 Инициализация тестовых данных...")

        if not self.redis_client:
            print("❌ Redis не подключен!")
            return False

        try:
            # Создаем тестовые форумы
            forums = [
                {
                    "forum_id": "general",
                    "name": "Общие вопросы",
                    "description": "Общие обсуждения и вопросы"
                },
                {
                    "forum_id": "tech",
                    "name": "Технологии",
                    "description": "Обсуждение технологий и программирования"
                },
                {
                    "forum_id": "news",
                    "name": "Новости",
                    "description": "Новости и актуальные события"
                },
                {
                    "forum_id": "offtopic",
                    "name": "Оффтопик",
                    "description": "Свободное общение"
                }
            ]

            for forum in forums:
                await self.redis_client.hset(
                    f"forum:{forum['forum_id']}",
                    mapping={
                        "name": forum["name"],
                        "description": forum["description"],
                        "created_at": "2024-01-01T00:00:00"
                    }
                )

            # Создаем тестовых пользователей
            test_users = [
                {
                    "user_id": "demo_user",
                    "username": "DemoUser",
                    "email": "demo@example.com",
                    "reputation_score": 85.0
                },
                {
                    "user_id": "admin_user",
                    "username": "Administrator",
                    "email": "admin@example.com",
                    "reputation_score": 100.0
                },
                {
                    "user_id": "test_user",
                    "username": "TestUser",
                    "email": "test@example.com",
                    "reputation_score": 70.0
                }
            ]

            for user in test_users:
                await self.redis_client.hset(
                    f"user:{user['user_id']}",
                    mapping={
                        "username": user["username"],
                        "email": user["email"],
                        "created_at": "2024-01-01T00:00:00",
                        "reputation_score": user["reputation_score"],
                        "is_banned": "False"
                    }
                )

                # Индексируем по username
                await self.redis_client.set(f"username:{user['username']}", user['user_id'])

            # Инициализируем спам-модель базовыми данными
            spam_examples = [
                "СРОЧНО! Казино онлайн! Бонус 1000 рублей!",
                "Заработок без вложений! Переходи по ссылке!",
                "ХАЛЯВА! Бесплатные деньги каждый день!",
                "Займ без проверок! Одобрение 100%!",
                "ВНИМАНИЕ! Акция только сегодня!"
            ]

            ham_examples = [
                "Интересная статья о программировании",
                "Обсуждаем новые технологии",
                "Рецепты здоровой еды",
                "Планы на выходные",
                "Книжные рекомендации"
            ]

            # Базовое обучение спам-фильтра
            await self.redis_client.set("spam:total_spam", len(spam_examples))
            await self.redis_client.set("spam:total_ham", len(ham_examples))

            # Сохраняем примеры для обучения
            for i, text in enumerate(spam_examples):
                words = text.lower().split()
                for word in set(words):
                    if len(word) > 2:
                        await self.redis_client.hincrby("spam:words:spam", word, 1)

            for i, text in enumerate(ham_examples):
                words = text.lower().split()
                for word in set(words):
                    if len(word) > 2:
                        await self.redis_client.hincrby("spam:words:ham", word, 1)

            print("✅ Тестовые данные инициализированы!")
            return True

        except Exception as e:
            print(f"❌ Ошибка при инициализации данных: {e}")
            return False

    def check_dependencies(self):
        """Проверка установленных зависимостей"""
        print("📦 Проверка зависимостей...")

        required_packages = [
            'fastapi',
            'uvicorn',
            'redis',
            'pydantic',
            'textblob'
        ]

        missing_packages = []

        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package}")
            except ImportError:
                print(f"❌ {package}")
                missing_packages.append(package)

        if missing_packages:
            print(f"\n⚠️ Отсутствующие пакеты: {', '.join(missing_packages)}")
            print("Установите их командой: pip install -r requirements.txt")
            return False

        print("✅ Все зависимости установлены!")
        return True

    def create_config_files(self):
        """Создание конфигурационных файлов"""
        print("⚙️ Создание конфигурационных файлов...")

        # Создаем .env файл
        env_content = """# Конфигурация форума
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True

# Настройки спам-фильтра
SPAM_THRESHOLD=0.7
RATE_LIMIT_POSTS_PER_HOUR=10
IP_REPUTATION_THRESHOLD=20

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=logs/forum.log
"""

        with open(self.base_dir / ".env", "w", encoding="utf-8") as f:
            f.write(env_content)

        # Создаем директорию для логов
        logs_dir = self.base_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        print("✅ Конфигурационные файлы созданы!")

    async def test_api_endpoints(self, base_url="http://localhost:8000"):
        """Тестирование API эндпоинтов"""
        print("🧪 Тестирование API...")

        # Ждем запуска сервера
        await asyncio.sleep(3)

        try:
            # Тест создания пользователя
            user_data = {
                "username": "api_test_user",
                "email": "apitest@example.com"
            }

            response = requests.post(f"{base_url}/api/users", json=user_data, timeout=10)
            if response.status_code == 200:
                print("✅ Создание пользователя работает")
                user_id = response.json()["user_id"]
            else:
                print(f"❌ Ошибка создания пользователя: {response.status_code}")
                return False

            # Тест создания поста
            post_data = {
                "title": "API Test Post",
                "content": "This is a test post created via API",
                "forum_id": "general"
            }

            response = requests.post(
                f"{base_url}/api/posts?user_id={user_id}",
                json=post_data,
                timeout=10
            )
            if response.status_code == 200:
                print("✅ Создание поста работает")
                post_result = response.json()
                print(f"   Спам-скор: {post_result['spam_score']:.3f}")
            else:
                print(f"❌ Ошибка создания поста: {response.status_code}")
                return False

            # Тест получения статистики
            response = requests.get(f"{base_url}/api/spam/stats", timeout=10)
            if response.status_code == 200:
                print("✅ Получение статистики работает")
                stats = response.json()
                print(f"   Обучено на спаме: {stats['total_spam_trained']}")
                print(f"   Обучено на не-спаме: {stats['total_ham_trained']}")
            else:
                print(f"❌ Ошибка получения статистики: {response.status_code}")
                return False

            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка соединения с API: {e}")
            return False

    def run_server(self, host="0.0.0.0", port=8000):
        """Запуск сервера"""
        print(f"🚀 Запуск сервера на {host}:{port}...")

        try:
            # Импортируем и запускаем приложение
            import uvicorn
            from main import app

            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=True,
                log_level="info"
            )
        except Exception as e:
            print(f"❌ Ошибка запуска сервера: {e}")


async def main():
    """Главная функция настройки"""
    print("🛡️ Настройка форума с анти-спам системой")
    print("=" * 50)

    setup = ForumSetup()

    # 1. Проверка зависимостей
    if not setup.check_dependencies():
        print("\n❌ Установите недостающие зависимости и запустите скрипт снова")
        return False

    # 2. Создание конфигурационных файлов
    setup.create_config_files()

    # 3. Проверка подключения к Redis
    if not await setup.check_redis_connection():
        print("\n❌ Убедитесь, что Redis запущен и доступен")
        print("Для запуска Redis используйте: docker-compose up redis")
        return False

    # 4. Инициализация тестовых данных
    if not await setup.initialize_test_data():
        return False

    print("\n✅ Настройка завершена успешно!")
    print("\nДля запуска форума используйте:")
    print("  python setup.py --run")
    print("  или")
    print("  python main.py")
    print("\nДля запуска с Docker:")
    print("  docker-compose up")

    if setup.redis_client:
        await setup.redis_client.aclose()

    return True


def run_tests():
    """Запуск тестов"""
    print("🧪 Запуск тестов...")

    try:
        import pytest
        result = pytest.main([
            "test_forum.py",
            "-v",
            "--tb=short",
            "--disable-warnings"
        ])

        if result == 0:
            print("✅ Все тесты прошли успешно!")
        else:
            print("❌ Некоторые тесты не прошли")

        return result == 0

    except ImportError:
        print("❌ pytest не установлен. Установите: pip install pytest")
        return False


def show_usage():
    """Показать справку по использованию"""
    print("""
🛡️ Форум с анти-спам системой
=====================================

Использование:
  python setup.py              - Настройка системы
  python setup.py --run        - Запуск сервера
  python setup.py --test       - Запуск тестов
  python setup.py --docker     - Информация о Docker
  python setup.py --help       - Показать эту справку

Структура проекта:
  main.py                   - Основное приложение FastAPI
  advanced_spam_features.py - Расширенные возможности анти-спам
  test_forum.py            - Тесты
  docker-compose.yml       - Docker конфигурация
  requirements.txt         - Зависимости Python
  redis.conf              - Конфигурация Redis

API Endpoints:
  GET  /                          - Веб-интерфейс форума
  POST /api/users                 - Создание пользователя
  GET  /api/users/{user_id}       - Получение пользователя
  POST /api/posts                 - Создание поста
  GET  /api/forums/{id}/posts     - Получение постов форума
  GET  /api/spam/stats           - Статистика спам-детекции

Особенности анти-спам системы:
  ✓ Bayesian фильтрация
  ✓ Rate limiting
  ✓ IP репутация
  ✓ ML-модели для детекции
  ✓ Анализ поведения пользователей
  ✓ Детекция ботов
  ✓ Автоматическое обучение

Мониторинг:
  - Redis Commander: http://localhost:8081
  - Форум: http://localhost:8000
  - API документация: http://localhost:8000/docs
""")


def show_docker_info():
    """Показать информацию о Docker"""
    print("""
🐳 Запуск с Docker
==================

1. Запуск всей системы:
   docker-compose up

2. Запуск только Redis:
   docker-compose up redis

3. Перезапуск приложения:
   docker-compose restart forum_app

4. Просмотр логов:
   docker-compose logs -f forum_app

5. Остановка:
   docker-compose down

Компоненты:
  - redis:8.0-alpine      (порт 6379)
  - forum_app            (порт 8000)
  - redis-commander       (порт 8081)

Volumes:
  - redis_data: Данные Redis
  - ./logs: Логи приложения
""")


async def run_server_async():
    """Асинхронный запуск сервера"""
    setup = ForumSetup()

    # Проверяем подключение к Redis
    if not await setup.check_redis_connection():
        print("❌ Redis недоступен. Запустите Redis и попробуйте снова.")
        return

    if setup.redis_client:
        await setup.redis_client.close()

    # Запускаем сервер
    print("🚀 Запуск форума...")
    setup.run_server()


def create_sample_data():
    """Создание примеров данных для демонстрации"""
    print("📝 Создание демонстрационных данных...")

    sample_posts = [
        {
            "title": "Добро пожаловать на форум!",
            "content": "Это первый пост на нашем новом форуме с продвинутой системой защиты от спама.",
            "forum_id": "general",
            "user_id": "admin_user"
        },
        {
            "title": "Обсуждение новых технологий",
            "content": "Давайте обсудим последние тренды в разработке: FastAPI, Redis 8, машинное обучение.",
            "forum_id": "tech",
            "user_id": "demo_user"
        },
        {
            "title": "Как работает анти-спам система",
            "content": "Наша система использует Bayesian фильтрацию, анализ поведения и ML-модели для детекции спама.",
            "forum_id": "tech",
            "user_id": "admin_user"
        }
    ]

    # Создаем демо-посты через API
    try:
        import requests
        base_url = "http://localhost:8000"

        for post in sample_posts:
            response = requests.post(
                f"{base_url}/api/posts?user_id={post['user_id']}",
                json={
                    "title": post["title"],
                    "content": post["content"],
                    "forum_id": post["forum_id"]
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Создан пост: {post['title']} (спам-скор: {result['spam_score']:.3f})")
            else:
                print(f"❌ Ошибка создания поста: {post['title']}")

    except Exception as e:
        print(f"❌ Ошибка создания демо-данных: {e}")
        print("Убедитесь, что сервер запущен на http://localhost:8000")


def benchmark_spam_detection():
    """Бенчмарк производительности спам-детекции"""
    print("⚡ Тестирование производительности...")

    test_texts = [
                     "СРОЧНО! Казино онлайн! Бонус 1000 рублей!",
                     "Интересная статья о программировании",
                     "ХАЛЯВА! Бесплатные деньги каждый день!",
                     "Обсуждаем новые технологии в IT",
                     "Займ без проверок! Одобрение 100%!"
                 ] * 20  # 100 текстов для тестирования

    try:
        import requests
        import time

        base_url = "http://localhost:8000"
        start_time = time.time()

        successful_requests = 0
        for i, text in enumerate(test_texts):
            try:
                response = requests.post(
                    f"{base_url}/api/posts?user_id=benchmark_user_{i % 5}",
                    json={
                        "title": f"Benchmark Test {i}",
                        "content": text,
                        "forum_id": "general"
                    },
                    timeout=5
                )

                if response.status_code in [200, 403]:  # 403 = rate limited
                    successful_requests += 1

            except Exception:
                pass

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Обработано {successful_requests}/{len(test_texts)} запросов")
        print(f"⏱️ Время выполнения: {total_time:.2f} секунд")
        print(f"🚀 Скорость: {successful_requests / total_time:.2f} запросов/сек")

    except Exception as e:
        print(f"❌ Ошибка бенчмарка: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # Базовая настройка
        asyncio.run(main())

    elif "--run" in sys.argv:
        # Запуск сервера
        asyncio.run(run_server_async())

    elif "--test" in sys.argv:
        # Запуск тестов
        run_tests()

    elif "--docker" in sys.argv:
        # Информация о Docker
        show_docker_info()

    elif "--help" in sys.argv or "-h" in sys.argv:
        # Справка
        show_usage()

    elif "--demo" in sys.argv:
        # Создание демо-данных
        create_sample_data()

    elif "--benchmark" in sys.argv:
        # Бенчмарк производительности
        benchmark_spam_detection()

    else:
        print("❌ Неизвестный параметр. Используйте --help для справки")
        sys.exit(1)