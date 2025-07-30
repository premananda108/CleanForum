#!/usr/bin/env python3
"""
Расширенные возможности анти-спам системы для форума
Включает:
- ML-модели для детекции спама
- Анализ поведения пользователей
- Детекция ботов
- Система репутации
- Автоматическое обучение
"""

import asyncio
import hashlib
import json
import numpy as np
import re
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pickle
import base64

import redis.asyncio as redis
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

# Загрузка NLTK данных
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass


@dataclass
class UserBehavior:
    """Модель поведения пользователя"""
    user_id: str
    post_frequency: float  # постов в час
    avg_post_length: float
    vocabulary_diversity: float  # уникальных слов / общих слов
    time_patterns: List[int]  # часы активности
    ip_changes: int
    suspicious_patterns: List[str]
    reputation_score: float
    registration_age_days: int


@dataclass
class ContentFeatures:
    """Признаки контента для ML"""
    text_length: int
    word_count: int
    sentence_count: int
    exclamation_count: int
    question_count: int
    caps_ratio: float
    digit_ratio: float
    url_count: int
    email_count: int
    phone_count: int
    repetitive_chars: float
    avg_word_length: float
    unique_words_ratio: float
    punctuation_ratio: float
    special_chars_count: int


class AdvancedSpamDetector:
    """Продвинутый детектор спама с ML и анализом поведения"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english') + stopwords.words('russian'))

        # ML модель
        self.ml_model = None
        self.vectorizer = None

        # Паттерны для детекции
        self.spam_patterns = [
            r'\b(казино|casino)\b',
            r'\b(заработок|earn money)\b',
            r'\b(бесплатно|free)\b.*\b(деньги|money)\b',
            r'\b(срочно|urgent)\b.*\b(предложение|offer)\b',
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'\b\d{10,}\b',  # Подозрительно длинные числа
            r'[A-ZА-Я]{5,}',  # Много заглавных букв подряд
        ]

        self.bot_patterns = [
            r'^user\d+$',  # Автогенерированные имена
            r'bot|crawler|spider',
            r'automated|script|program'
        ]

    async def initialize_ml_model(self):
        """Инициализация ML модели"""
        try:
            # Попытка загрузить существующую модель
            model_data = await self.redis.get("spam_ml_model")
            if model_data:
                self.ml_model = pickle.loads(base64.b64decode(model_data))

            vectorizer_data = await self.redis.get("spam_vectorizer")
            if vectorizer_data:
                self.vectorizer = pickle.loads(base64.b64decode(vectorizer_data))

            if not self.ml_model or not self.vectorizer:
                await self._train_initial_model()

        except Exception as e:
            print(f"Error initializing ML model: {e}")
            await self._train_initial_model()

    async def _train_initial_model(self):
        """Обучение начальной модели на базовых данных"""
        # Базовые данные для обучения
        spam_texts = [
            "СРОЧНО! Заработок без вложений! Переходи по ссылке!",
            "Казино онлайн! Бонус 1000 рублей!",
            "Бесплатные деньги! Кликай здесь!",
            "ВНИМАНИЕ! Акция только сегодня!",
            "Займ без проверок! Одобрение 100%!",
            "Make money fast! Click here now!",
            "Free casino bonus! Win big!",
            "Urgent offer! Limited time only!"
        ]

        ham_texts = [
            "Привет! Как дела? Как провел выходные?",
            "Интересная статья о программировании",
            "Обсуждаем новые фильмы в кинотеатрах",
            "Рецепт вкусного борща от бабушки",
            "Планируем встречу на следующей неделе",
            "Hello! How are you doing today?",
            "Great article about technology trends",
            "Discussion about books and reading"
        ]

        # Подготовка данных
        texts = spam_texts + ham_texts
        labels = [1] * len(spam_texts) + [0] * len(ham_texts)

        # Создание пайплайна
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1
        )

        self.ml_model = MultinomialNB(alpha=0.1)

        # Обучение
        X = self.vectorizer.fit_transform(texts)
        self.ml_model.fit(X, labels)

        # Сохранение модели
        await self._save_model()

    async def _save_model(self):
        """Сохранение ML модели в Redis"""
        try:
            model_data = base64.b64encode(pickle.dumps(self.ml_model)).decode()
            await self.redis.set("spam_ml_model", model_data)

            vectorizer_data = base64.b64encode(pickle.dumps(self.vectorizer)).decode()
            await self.redis.set("spam_vectorizer", vectorizer_data)

        except Exception as e:
            print(f"Error saving model: {e}")

    def extract_content_features(self, text: str) -> ContentFeatures:
        """Извлечение признаков из текста"""
        words = word_tokenize(text.lower())
        sentences = text.split('.')

        return ContentFeatures(
            text_length=len(text),
            word_count=len(words),
            sentence_count=len(sentences),
            exclamation_count=text.count('!'),
            question_count=text.count('?'),
            caps_ratio=sum(1 for c in text if c.isupper()) / len(text) if text else 0,
            digit_ratio=sum(1 for c in text if c.isdigit()) / len(text) if text else 0,
            url_count=len(re.findall(r'http[s]?://\S+', text)),
            email_count=len(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
            phone_count=len(re.findall(r'\b\d{10,}\b', text)),
            repetitive_chars=self._calculate_repetitive_chars(text),
            avg_word_length=sum(len(word) for word in words) / len(words) if words else 0,
            unique_words_ratio=len(set(words)) / len(words) if words else 0,
            punctuation_ratio=sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text) if text else 0,
            special_chars_count=sum(1 for c in text if c in '!@#$%^&*()+=[]{}|\\:";\'<>?,./`~')
        )

    def _calculate_repetitive_chars(self, text: str) -> float:
        """Вычисление коэффициента повторяющихся символов"""
        if not text:
            return 0.0

        repetitive_count = 0
        i = 0
        while i < len(text) - 2:
            if text[i] == text[i + 1] == text[i + 2]:
                repetitive_count += 1
                while i < len(text) - 1 and text[i] == text[i + 1]:
                    i += 1
            i += 1

        return repetitive_count / len(text)

    async def analyze_user_behavior(self, user_id: str) -> UserBehavior:
        """Анализ поведения пользователя"""
        user_data = await self.redis.hgetall(f"user_behavior:{user_id}")

        if not user_data:
            # Инициализация данных о поведении пользователя
            behavior = UserBehavior(
                user_id=user_id,
                post_frequency=0.0,
                avg_post_length=0.0,
                vocabulary_diversity=0.0,
                time_patterns=[0] * 24,
                ip_changes=0,
                suspicious_patterns=[],
                reputation_score=50.0,
                registration_age_days=0
            )
        else:
            behavior = UserBehavior(
                user_id=user_id,
                post_frequency=float(user_data.get(b'post_frequency', 0)),
                avg_post_length=float(user_data.get(b'avg_post_length', 0)),
                vocabulary_diversity=float(user_data.get(b'vocabulary_diversity', 0)),
                time_patterns=json.loads(user_data.get(b'time_patterns', '[0]*24')),
                ip_changes=int(user_data.get(b'ip_changes', 0)),
                suspicious_patterns=json.loads(user_data.get(b'suspicious_patterns', '[]')),
                reputation_score=float(user_data.get(b'reputation_score', 50.0)),
                registration_age_days=int(user_data.get(b'registration_age_days', 0))
            )

        return behavior

    async def update_user_behavior(self, user_id: str, post_content: str, ip_address: str):
        """Обновление данных о поведении пользователя"""
        behavior = await self.analyze_user_behavior(user_id)

        # Обновляем статистику постов
        current_hour = datetime.now().hour
        behavior.time_patterns[current_hour] += 1

        # Обновляем среднюю длину постов
        post_length = len(post_content)
        if behavior.avg_post_length == 0:
            behavior.avg_post_length = post_length
        else:
            behavior.avg_post_length = (behavior.avg_post_length + post_length) / 2

        # Анализируем словарное разнообразие
        words = set(word_tokenize(post_content.lower()))
        vocabulary_size = await self.redis.scard(f"user_vocabulary:{user_id}")
        if vocabulary_size > 0:
            new_words = len(words)
            behavior.vocabulary_diversity = new_words / (vocabulary_size + new_words)

        # Сохраняем слова в словарь пользователя
        if words:
            await self.redis.sadd(f"user_vocabulary:{user_id}", *words)
            await self.redis.expire(f"user_vocabulary:{user_id}", 86400 * 30)  # 30 дней

        # Отслеживаем смены IP
        last_ip = await self.redis.get(f"user_last_ip:{user_id}")
        if last_ip and last_ip.decode() != ip_address:
            behavior.ip_changes += 1
        await self.redis.setex(f"user_last_ip:{user_id}", 86400, ip_address)

        # Сохраняем обновленные данные
        await self.redis.hset(f"user_behavior:{user_id}", mapping={
            'post_frequency': behavior.post_frequency,
            'avg_post_length': behavior.avg_post_length,
            'vocabulary_diversity': behavior.vocabulary_diversity,
            'time_patterns': json.dumps(behavior.time_patterns),
            'ip_changes': behavior.ip_changes,
            'suspicious_patterns': json.dumps(behavior.suspicious_patterns),
            'reputation_score': behavior.reputation_score,
            'registration_age_days': behavior.registration_age_days
        })

    async def detect_bot_behavior(self, user_id: str, username: str, user_agent: str = "") -> float:
        """Детекция ботов по поведению"""
        bot_score = 0.0

        # Проверяем имя пользователя на паттерны ботов
        for pattern in self.bot_patterns:
            if re.search(pattern, username.lower()):
                bot_score += 0.3

        # Анализируем поведение
        behavior = await self.analyze_user_behavior(user_id)

        # Подозрительно высокая частота постов
        if behavior.post_frequency > 10:  # Более 10 постов в час
            bot_score += 0.4

        # Низкое разнообразие словаря
        if behavior.vocabulary_diversity < 0.1:
            bot_score += 0.2

        # Подозрительные временные паттерны (активность 24/7)
        active_hours = sum(1 for h in behavior.time_patterns if h > 0)
        if active_hours > 20:  # Активен более 20 часов в сутки
            bot_score += 0.3

        # Частые смены IP
        if behavior.ip_changes > 5:
            bot_score += 0.2

        return min(bot_score, 1.0)

    async def ml_spam_prediction(self, text: str) -> float:
        """Предсказание спама с помощью ML модели"""
        if not self.ml_model or not self.vectorizer:
            return 0.0

        try:
            # Преобразуем текст в вектор
            text_vector = self.vectorizer.transform([text])

            # Получаем вероятность спама
            spam_probability = self.ml_model.predict_proba(text_vector)[0][1]

            return spam_probability

        except Exception as e:
            print(f"Error in ML prediction: {e}")
            return 0.0

    async def comprehensive_spam_analysis(self, text: str, user_id: str, ip_address: str, username: str) -> Dict:
        """Комплексный анализ на спам"""
        # Извлекаем признаки контента
        content_features = self.extract_content_features(text)

        # ML предсказание
        ml_score = await self.ml_spam_prediction(text)

        # Анализ поведения пользователя
        user_behavior = await self.analyze_user_behavior(user_id)

        # Детекция ботов
        bot_score = await self.detect_bot_behavior(user_id, username)

        # Репутация IP
        ip_reputation = await self._get_ip_reputation(ip_address)

        # Паттерн-анализ
        pattern_score = self._analyze_patterns(text)

        # Вычисляем итоговый спам-скор
        spam_score = (
                ml_score * 0.35 +
                pattern_score * 0.25 +
                bot_score * 0.20 +
                (1 - ip_reputation / 100) * 0.15 +
                (1 - user_behavior.reputation_score / 100) * 0.05
        )

        # Дополнительные штрафы
        if content_features.caps_ratio > 0.5:
            spam_score += 0.1

        if content_features.url_count > 2:
            spam_score += 0.15

        if content_features.repetitive_chars > 0.1:
            spam_score += 0.1

        spam_score = min(spam_score, 1.0)

        return {
            'spam_score': spam_score,
            'is_spam': spam_score > 0.7,
            'ml_score': ml_score,
            'pattern_score': pattern_score,
            'bot_score': bot_score,
            'ip_reputation': ip_reputation,
            'user_reputation': user_behavior.reputation_score,
            'content_features': content_features.__dict__,
            'confidence': self._calculate_confidence(spam_score, ml_score, pattern_score)
        }

    async def _get_ip_reputation(self, ip_address: str) -> float:
        """Получение репутации IP"""
        reputation = await self.redis.get(f"ip_reputation:{ip_address}")
        return float(reputation) if reputation else 50.0

    def _analyze_patterns(self, text: str) -> float:
        """Анализ текста на подозрительные паттерны"""
        pattern_score = 0.0

        for pattern in self.spam_patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            pattern_score += matches * 0.2

        return min(pattern_score, 1.0)

    def _calculate_confidence(self, spam_score: float, ml_score: float, pattern_score: float) -> float:
        """Вычисление уверенности в предсказании"""
        # Высокая уверенность если все модели согласны
        scores = [spam_score, ml_score, pattern_score]
        variance = np.var(scores)

        # Чем меньше разброс, тем выше уверенность
        confidence = 1.0 - min(variance * 2, 1.0)
        return confidence

    async def retrain_model(self, feedback_data: List[Tuple[str, bool]]):
        """Переобучение модели на новых данных"""
        if len(feedback_data) < 10:
            return False

        try:
            texts, labels = zip(*feedback_data)

            # Дообучаем существующую модель
            X_new = self.vectorizer.transform(texts)

            # Partial fit для онлайн обучения
            self.ml_model.partial_fit(X_new, labels)

            # Сохраняем обновленную модель
            await self._save_model()

            return True

        except Exception as e:
            print(f"Error retraining model: {e}")
            return False


class SpamReportingSystem:
    """Система отчетности и мониторинга спама"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def generate_spam_report(self) -> Dict:
        """Генерация отчета по спаму"""
        # Получаем статистику за последние 24 часа
        current_time = time.time()
        day_ago = current_time - 86400

        # Спам посты
        spam_posts = await self.redis.zcount("spam_posts", day_ago, current_time)
        total_posts = await self.redis.zcount("all_posts", day_ago, current_time)

        # Заблокированные IP
        blocked_ips = await self.redis.scard("blocked_ips")

        # Пользователи с низкой репутацией
        low_reputation_users = 0
        user_keys = await self.redis.keys("user_behavior:*")
        for key in user_keys:
            reputation = float(await self.redis.hget(key, 'reputation_score') or 50)
            if reputation < 20:
                low_reputation_users += 1

        spam_rate = (spam_posts / total_posts * 100) if total_posts > 0 else 0

        return {
            'timestamp': datetime.now().isoformat(),
            'period': '24h',
            'total_posts': total_posts,
            'spam_posts': spam_posts,
            'spam_rate_percent': round(spam_rate, 2),
            'blocked_ips': blocked_ips,
            'low_reputation_users': low_reputation_users,
            'detection_accuracy': await self._calculate_detection_accuracy()
        }

    async def _calculate_detection_accuracy(self) -> float:
        """Вычисление точности детекции на основе обратной связи"""
        feedback_data = await self.redis.hgetall("spam_feedback")
        if not feedback_data:
            return 95.0  # Базовая точность

        correct_predictions = 0
        total_predictions = 0

        for post_id, feedback in feedback_data.items():
            feedback_data = json.loads(feedback.decode())
            if feedback_data['predicted'] == feedback_data['actual']:
                correct_predictions += 1
            total_predictions += 1

        return (correct_predictions / total_predictions * 100) if total_predictions > 0 else 95.0


# Пример использования расширенной системы
async def main():
    # Подключение к Redis
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)

    # Инициализация детектора
    detector = AdvancedSpamDetector(redis_client)
    await detector.initialize_ml_model()

    # Тестовый анализ
    test_text = "СРОЧНО! Заработок без вложений! Переходи по ссылке казино!"
    result = await detector.comprehensive_spam_analysis(
        test_text,
        "test_user",
        "192.168.1.1",
        "testuser123"
    )

    print("Результат анализа спама:")
    print(json.dumps(result, indent=2, default=str))

    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())