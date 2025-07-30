#!/usr/bin/env python3
"""
Тесты для форума с анти-спам системой
"""

import asyncio
import json
import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from main import app, SpamGuard, ForumService

# Тестовый клиент FastAPI
client = TestClient(app)


class TestSpamGuard:
    """Тесты для системы защиты от спама"""

    @pytest.fixture
    async def redis_client(self):
        """Фикстура для Redis клиента"""
        client = redis.Redis(host='localhost', port=6379, decode_responses=False, db=1)  # Используем тестовую БД
        yield client
        await client.flushdb()  # Очищаем после теста
        await client.close()

    @pytest.fixture
    async def spam_guard(self, redis_client):
        """Фикстура для SpamGuard"""
        guard = SpamGuard(redis_client)
        await guard.init_spam_model()
        return guard

    @pytest.mark.asyncio
    async def test_spam_words_detection(self, spam_guard):
        """Тест детекции спам-слов"""
        spam_text = "Казино онлайн! Бесплатные деньги! Заработок без вложений!"
        ham_text = "Обсуждаем новые технологии в программировании"

        spam_analysis = await spam_guard.analyze_content(spam_text)
        ham_analysis = await spam_guard.analyze_content(ham_text)

        assert spam_analysis['spam_words_count'] > 0
        assert ham_analysis['spam_words_count'] == 0

    @pytest.mark.asyncio
    async def test_rate_limiting(self, spam_guard):
        """Тест ограничения частоты постов"""
        user_id = "test_user"
        ip_address = "192.168.1.100"

        # Первые 5 постов должны пройти
        for i in range(5):
            result = await spam_guard.check_rate_limit(user_id, ip_address)
            assert result == True

        # 6-й пост должен быть заблокирован
        result = await spam_guard.check_rate_limit(user_id, ip_address)
        assert result == False

    @pytest.mark.asyncio
    async def test_bayesian_training(self, spam_guard):
        """Тест обучения Bayesian фильтра"""
        # Обучаем на спаме
        await spam_guard.train_spam_filter("казино бонус халява", True)
        await spam_guard.train_spam_filter("лотерея выигрыш деньги", True)

        # Обучаем на не-спаме
        await spam_guard.train_spam_filter("интересная статья о программировании", False)
        await spam_guard.train_spam_filter("обсуждение книг и фильмов", False)

        # Проверяем предсказания
        spam_prob = await spam_guard.calculate_spam_probability("казино халява")
        ham_prob = await spam_guard.calculate_spam_probability("программирование статья")

        assert spam_prob > ham_prob

    @pytest.mark.asyncio
    async def test_ip_reputation(self, spam_guard):
        """Тест системы репутации IP"""
        ip_address = "192.168.1.200"

        # Начальная репутация
        initial_rep = await spam_guard.get_ip_reputation(ip_address)
        assert initial_rep == 50.0

        # Понижаем репутацию за спам
        await spam_guard.update_ip_reputation(ip_address, True)
        spam_rep = await spam_guard.get_ip_reputation(ip_address)
        assert spam_rep < initial_rep

        # Повышаем репутацию за хороший контент
        await spam_guard.update_ip_reputation(ip_address, False)
        good_rep = await spam_guard.get_ip_reputation(ip_address)
        assert good_rep > spam_rep


class TestForumAPI:
    """Тесты для API форума"""

    def test_create_user(self):
        """Тест создания пользователя"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com"
        }

        response = client.post("/api/users", json=user_data)
        assert response.status_code == 200

        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "user_id" in data

    def test_create_post_normal(self):
        """Тест создания обычного поста"""
        post_data = {
            "title": "Обсуждение новых технологий",
            "content": "Давайте обсудим последние тренды в разработке программного обеспечения",
            "forum_id": "tech"
        }

        response = client.post("/api/posts?user_id=test_user", json=post_data)
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == post_data["title"]
        assert data["is_spam"] == False
        assert data["spam_score"] < 0.5

    def test_create_post_spam(self):
        """Тест создания спам-поста"""
        post_data = {
            "title": "СРОЧНО! КАЗИНО ОНЛАЙН!",
            "content": "ЗАРАБОТОК БЕЗ ВЛОЖЕНИЙ! БЕСПЛАТНЫЕ ДЕНЬГИ! ПЕРЕХОДИ ПО ССЫЛКЕ! ХАЛЯВА!",
            "forum_id": "general"
        }

        response = client.post("/api/posts?user_id=spam_user", json=post_data)
        assert response.status_code == 200

        data = response.json()
        assert data["is_spam"] == True
        assert data["spam_score"] > 0.7

    def test_get_forum_posts(self):
        """Тест получения постов форума"""
        # Сначала создаем пост
        post_data = {
            "title": "Тестовый пост",
            "content": "Это тестовый контент для проверки",
            "forum_id": "general"
        }
        client.post("/api/posts?user_id=test_user", json=post_data)

        # Получаем посты
        response = client.get("/api/forums/general/posts")
        assert response.status_code == 200

        posts = response.json()
        assert isinstance(posts, list)

    def test_spam_stats(self):
        """Тест получения статистики спама"""
        response = client.get("/api/spam/stats")
        assert response.status_code == 200

        stats = response.json()
        assert "total_spam_trained" in stats
        assert "total_ham_trained" in stats
        assert "quarantined_posts" in stats


class TestAdvancedFeatures:
    """Тесты для расширенных возможностей"""

    @pytest.mark.asyncio
    async def test_content_features_extraction(self):
        """Тест извлечения признаков контента"""
        from advanced_spam_features import AdvancedSpamDetector

        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False, db=1)
        detector = AdvancedSpamDetector(redis_client)

        text = "СРОЧНО!!! Заработок без вложений!!! http://spam-site.com Звоните: 1234567890"
        features = detector.extract_content_features(text)

        assert features.exclamation_count > 0
        assert features.caps_ratio > 0.3
        assert features.url_count > 0
        assert features.phone_count > 0

        await redis_client.close()

    @pytest.mark.asyncio
    async def test_user_behavior_analysis(self):
        """Тест анализа поведения пользователя"""
        from advanced_spam_features import AdvancedSpamDetector

        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False, db=1)
        detector = AdvancedSpamDetector(redis_client)

        user_id = "behavior_test_user"

        # Обновляем поведение несколько раз
        for i in range(3):
            await detector.update_user_behavior(
                user_id,
                f"Тестовый пост номер {i}",
                "192.168.1.50"
            )

        behavior = await detector.analyze_user_behavior(user_id)
        assert behavior.user_id == user_id
        assert behavior.avg_post_length > 0

        await redis_client.close()

    @pytest.mark.asyncio
    async def test_bot_detection(self):
        """Тест детекции ботов"""
        from advanced_spam_features import AdvancedSpamDetector

        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False, db=1)
        detector = AdvancedSpamDetector(redis_client)

        # Тест подозрительного имени пользователя
        bot_score = await detector.detect_bot_behavior("bot123", "user12345bot", "")
        assert bot_score > 0.3

        # Тест нормального пользователя
        human_score = await detector.detect_bot_behavior("human123", "john_doe", "")
        assert human_score < 0.3

        await redis_client.close()


class TestIntegration:
    """Интеграционные тесты"""

    def test_full_spam_detection_workflow(self):
        """Полный тест процесса детекции спама"""
        # Создаем пользователя
        user_data = {
            "username": "spammer123",
            "email": "spammer@spam.com"
        }
        user_response = client.post("/api/users", json=user_data)
        user_id = user_response.json()["user_id"]

        # Создаем серию спам-постов
        spam_posts = [
            {
                "title": "КАЗИНО ОНЛАЙН БОНУС",
                "content": "СРОЧНО! БЕСПЛАТНЫЕ ДЕНЬГИ! ПЕРЕХОДИ ПО ССЫЛКЕ!",
                "forum_id": "general"
            },
            {
                "title": "ЗАРАБОТОК БЕЗ ВЛОЖЕНИЙ",
                "content": "ХАЛЯВА! ЛОХОТРОН НЕ ПРЕДЛАГАТЬ! ТОЛЬКО ПРОВЕРЕННЫЕ СХЕМЫ!",
                "forum_id": "general"
            }
        ]

        spam_detected = 0
        for post_data in spam_posts:
            response = client.post(f"/api/posts?user_id={user_id}", json=post_data)
            if response.json()["is_spam"]:
                spam_detected += 1

        # Проверяем, что большинство спам-постов было обнаружено
        assert spam_detected >= len(spam_posts) * 0.8  # Минимум 80% точность

    def test_rate_limiting_integration(self):
        """Интеграционный тест ограничения частоты"""
        user_data = {
            "username": "rapidposter",
            "email": "rapid@example.com"
        }
        user_response = client.post("/api/users", json=user_data)
        user_id = user_response.json()["user_id"]

        # Пытаемся создать много постов быстро
        successful_posts = 0
        for i in range(10):
            post_data = {
                "title": f"Пост номер {i}",
                "content": f"Содержимое поста номер {i}",
                "forum_id": "general"
            }

            response = client.post(f"/api/posts?user_id={user_id}", json=post_data)
            if response.status_code == 200:
                successful_posts += 1
            else:
                break

        # Должно быть ограничение на количество постов
        assert successful_posts <= 5  # Максимум 5 постов за период


# Тестовые данные для различных сценариев
TEST_SPAM_TEXTS = [
    "СРОЧНО! Казино онлайн! Бонус 1000 рублей!",
    "Заработок без вложений! Кликай здесь!",
    "ХАЛЯВА! Бесплатные деньги каждый день!",
    "Займ без проверок! Одобрение 100%!",
    "ВНИМАНИЕ! Акция только сегодня! Переходи по ссылке!",
    "Make money fast! Click here now!",
    "Free casino bonus! Win big today!",
    "Urgent offer! Limited time only!"
]

TEST_HAM_TEXTS = [
    "Интересная статья о машинном обучении",
    "Обсуждаем новые фильмы в кинотеатрах",
    "Рецепт вкусного борща от моей бабушки",
    "Планируем встречу на следующей неделе",
    "Как настроить Redis для высокой производительности",
    "Great discussion about programming languages",
    "Book recommendations for software developers",
    "Weather forecast looks good for the weekend"
]


class TestDataQuality:
    """Тесты качества данных и производительности"""

    @pytest.mark.asyncio
    async def test_spam_detection_accuracy(self):
        """Тест точности детекции спама на тестовых данных"""
        from advanced_spam_features import AdvancedSpamDetector

        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False, db=1)
        detector = AdvancedSpamDetector(redis_client)
        await detector.initialize_ml_model()

        # Обучаем на тестовых данных
        for text in TEST_SPAM_TEXTS:
            await detector._train_initial_model()

        correct_predictions = 0
        total_predictions = 0

        # Тестируем на спаме
        for text in TEST_SPAM_TEXTS:
            result = await detector.comprehensive_spam_analysis(
                text, "test_user", "192.168.1.1", "testuser"
            )
            if result['is_spam']:
                correct_predictions += 1
            total_predictions += 1

        # Тестируем на не-спаме
        for text in TEST_HAM_TEXTS:
            result = await detector.comprehensive_spam_analysis(
                text, "test_user", "192.168.1.1", "testuser"
            )
            if not result['is_spam']:
                correct_predictions += 1
            total_predictions += 1

        accuracy = correct_predictions / total_predictions
        assert accuracy > 0.8  # Минимум 80% точность

        await redis_client.close()

    def test_performance_load(self):
        """Тест производительности под нагрузкой"""
        import time

        start_time = time.time()

        # Создаем 100 постов
        for i in range(100):
            post_data = {
                "title": f"Тестовый пост {i}",
                "content": f"Содержимое тестового поста номер {i}",
                "forum_id": "general"
            }

            response = client.post(f"/api/posts?user_id=load_test_user_{i % 10}", json=post_data)
            assert response.status_code in [200, 403]  # 403 может быть из-за rate limiting

        end_time = time.time()
        execution_time = end_time - start_time

        # Должно выполняться за разумное время (менее 30 секунд для 100 постов)
        assert execution_time < 30.0


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])


# Скрипт для ручного тестирования
async def manual_test():
    """Ручное тестирование функциональности"""
    print("🧪 Запуск ручных тестов...")

    # Тест создания пользователя
    print("\n1. Тестирование создания пользователя...")
    user_response = client.post("/api/users", json={
        "username": "manual_test_user",
        "email": "manual@test.com"
    })
    print(f"Статус: {user_response.status_code}")
    if user_response.status_code == 200:
        print(f"Пользователь создан: {user_response.json()['username']}")

    # Тест создания обычного поста
    print("\n2. Тестирование создания обычного поста...")
    normal_post = client.post("/api/posts?user_id=manual_test", json={
        "title": "Обсуждение технологий",
        "content": "Интересная статья о современных подходах к разработке",
        "forum_id": "tech"
    })
    print(f"Статус: {normal_post.status_code}")
    if normal_post.status_code == 200:
        post_data = normal_post.json()
        print(f"Пост создан. Спам-скор: {post_data['spam_score']:.3f}, Спам: {post_data['is_spam']}")

    # Тест создания спам-поста
    print("\n3. Тестирование детекции спама...")
    spam_post = client.post("/api/posts?user_id=manual_test", json={
        "title": "СРОЧНО! КАЗИНО БОНУС!",
        "content": "ЗАРАБОТОК БЕЗ ВЛОЖЕНИЙ! БЕСПЛАТНЫЕ ДЕНЬГИ! ХАЛЯВА!",
        "forum_id": "general"
    })
    print(f"Статус: {spam_post.status_code}")
    if spam_post.status_code == 200:
        post_data = spam_post.json()
        print(f"Пост создан. Спам-скор: {post_data['spam_score']:.3f}, Спам: {post_data['is_spam']}")

    # Тест статистики
    print("\n4. Получение статистики...")
    stats_response = client.get("/api/spam/stats")
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"Статистика: {json.dumps(stats, indent=2)}")

    print("\n✅ Ручные тесты завершены!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        asyncio.run(manual_test())
    else:
        pytest.main([__file__, "-v"])