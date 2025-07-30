#!/usr/bin/env python3
"""
Форум на базе FastAPI с Redis 8 и продвинутой анти-спам системой
Включает в себя:
- Bayesian spam filtering
- Rate limiting
- IP reputation tracking
- Content analysis
- User behavior analysis
"""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import uuid4

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn
from textblob import TextBlob
import logging

import logging
from logging.handlers import RotatingFileHandler

# Настройка логирования
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Настройка обработчика для файла
log_file = 'logs/forum.log'
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5) # 10 MB per file, 5 backups
file_handler.setFormatter(log_formatter)

# Настройка обработчика для консоли
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Получаем логгер и добавляем обработчики
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# Модели данных
class User(BaseModel):
    user_id: str
    username: str
    email: str
    created_at: datetime
    reputation_score: float = 100.0
    is_banned: bool = False


class Post(BaseModel):
    post_id: str
    user_id: str
    username: str
    title: str
    content: str
    created_at: datetime
    spam_score: float = 0.0
    is_spam: bool = False
    forum_id: str


class Forum(BaseModel):
    forum_id: str
    name: str
    description: str
    created_at: datetime


class CreatePostRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    content: str = Field(..., min_length=10, max_length=10000)
    forum_id: str


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str


class SpamGuard:
    """Продвинутая система защиты от спама с использованием Redis 8"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.spam_words = {
            'ru': ['казино', 'заработок', 'халява', 'кредит', 'займ', 'лохотрон', 'пирамида'],
            'en': ['casino', 'lottery', 'winner', 'prize', 'free money', 'click here', 'urgent']
        }

    async def init_spam_model(self):
        """Инициализация Bayesian модели для обнаружения спама"""
        # Создаем ключи для Bayesian классификатора
        await self.redis.set("spam:total_spam", 0)
        await self.redis.set("spam:total_ham", 0)
        logger.info("Spam detection model initialized")

    async def train_spam_filter(self, text: str, is_spam: bool):
        """Обучение Bayesian фильтра"""
        words = self._tokenize(text)
        category = "spam" if is_spam else "ham"

        # Увеличиваем счетчик категории
        await self.redis.incr(f"spam:total_{category}")

        # Обучаем на словах
        for word in set(words):
            await self.redis.hincrby(f"spam:words:{category}", word, 1)

    async def calculate_spam_probability(self, text: str) -> float:
        """Вычисление вероятности спама с использованием Naive Bayes"""
        words = self._tokenize(text)

        # Получаем общие счетчики
        total_spam = int(await self.redis.get("spam:total_spam") or 0)
        total_ham = int(await self.redis.get("spam:total_ham") or 0)

        if total_spam == 0 and total_ham == 0:
            return 0.0

        spam_prob = 0.0
        ham_prob = 0.0

        for word in set(words):
            # Получаем количество раз, когда слово встречалось в спаме и не-спаме
            spam_count = int(await self.redis.hget(f"spam:words:spam", word) or 0)
            ham_count = int(await self.redis.hget(f"spam:words:ham", word) or 0)

            # Применяем сглаживание Лапласа
            word_spam_prob = (spam_count + 1) / (total_spam + 2)
            word_ham_prob = (ham_count + 1) / (total_ham + 2)

            spam_prob += word_spam_prob
            ham_prob += word_ham_prob

        # Нормализуем и возвращаем вероятность спама
        total_prob = spam_prob + ham_prob
        return spam_prob / total_prob if total_prob > 0 else 0.0

    async def check_rate_limit(self, user_id: str, ip_address: str) -> bool:
        """Проверка ограничений по частоте публикаций"""
        current_time = int(time.time())
        window = 300  # 5 минут

        # Проверяем ограничения по пользователю
        user_key = f"rate_limit:user:{user_id}"
        user_posts = await self.redis.zcount(user_key, current_time - window, current_time)

        if user_posts >= 5:  # Максимум 5 постов за 5 минут
            return False

        # Проверяем ограничения по IP
        ip_key = f"rate_limit:ip:{ip_address}"
        ip_posts = await self.redis.zcount(ip_key, current_time - window, current_time)

        if ip_posts >= 10:  # Максимум 10 постов с одного IP за 5 минут
            return False

        # Записываем текущий запрос
        await self.redis.zadd(user_key, {str(uuid4()): current_time})
        await self.redis.zadd(ip_key, {str(uuid4()): current_time})

        # Устанавливаем TTL для автоочистки
        await self.redis.expire(user_key, window)
        await self.redis.expire(ip_key, window)

        return True

    async def update_ip_reputation(self, ip_address: str, is_spam: bool):
        """Обновление репутации IP адреса"""
        key = f"ip_reputation:{ip_address}"
        current_score = float(await self.redis.get(key) or 50.0)

        if is_spam:
            new_score = max(0, current_score - 10)
        else:
            new_score = min(100, current_score + 1)

        await self.redis.setex(key, 86400 * 7, new_score)  # Храним 7 дней

    async def get_ip_reputation(self, ip_address: str) -> float:
        """Получение репутации IP адреса"""
        key = f"ip_reputation:{ip_address}"
        return float(await self.redis.get(key) or 50.0)

    async def analyze_content(self, text: str) -> Dict:
        """Анализ контента на предмет спама"""
        analysis = {
            'spam_words_count': 0,
            'suspicious_patterns': [],
            'sentiment_score': 0.0,
            'contains_urls': False,
            'excessive_caps': False
        }

        text_lower = text.lower()

        # Проверяем спам-слова
        for lang, words in self.spam_words.items():
            for word in words:
                if word in text_lower:
                    analysis['spam_words_count'] += 1

        # Проверяем подозрительные паттерны
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        if re.search(url_pattern, text):
            analysis['contains_urls'] = True

        # Проверяем чрезмерное использование заглавных букв
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text) if text else 0
        if caps_ratio > 0.3:
            analysis['excessive_caps'] = True

        # Анализ тональности
        try:
            blob = TextBlob(text)
            analysis['sentiment_score'] = blob.sentiment.polarity
        except:
            pass

        return analysis

    async def comprehensive_spam_check(self, text: str, user_id: str, ip_address: str) -> Dict:
        """Комплексная проверка на спам"""
        # Проверяем rate limiting
        if not await self.check_rate_limit(user_id, ip_address):
            return {'is_spam': True, 'reason': 'rate_limit_exceeded', 'score': 1.0}

        # Получаем репутацию IP
        ip_reputation = await self.get_ip_reputation(ip_address)

        # Вычисляем вероятность спама через Bayesian
        bayesian_score = await self.calculate_spam_probability(text)

        # Анализируем содержимое
        content_analysis = await self.analyze_content(text)

        # Вычисляем итоговый счет спама
        spam_score = (
                bayesian_score * 0.4 +
                (1 - ip_reputation / 100) * 0.3 +
                (content_analysis['spam_words_count'] / 10) * 0.2 +
                (1 if content_analysis['excessive_caps'] else 0) * 0.1
        )

        is_spam = spam_score > 0.7

        return {
            'is_spam': is_spam,
            'score': spam_score,
            'bayesian_score': bayesian_score,
            'ip_reputation': ip_reputation,
            'content_analysis': content_analysis,
            'reason': 'content_analysis'
        }

    def _tokenize(self, text: str) -> List[str]:
        """Токенизация текста"""
        # Простая токенизация - можно улучшить
        words = re.findall(r'\b\w+\b', text.lower())
        return [word for word in words if len(word) > 2]


class ForumService:
    """Сервис для работы с форумом"""

    def __init__(self, redis_client, spam_guard):
        self.redis = redis_client
        self.spam_guard = spam_guard

    async def create_user(self, user_data: CreateUserRequest) -> User:
        """Создание нового пользователя"""
        user_id = str(uuid4())
        user = User(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            created_at=datetime.utcnow()
        )

        # Сохраняем пользователя
        await self.redis.hset(
            f"user:{user_id}",
            mapping={
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
                "reputation_score": user.reputation_score,
                "is_banned": str(user.is_banned)
            }
        )

        # Индексируем по username
        await self.redis.set(f"username:{user.username}", user_id)

        return user

    async def get_user(self, user_id: str) -> Optional[User]:
        """Получение пользователя по ID"""
        user_data = await self.redis.hgetall(f"user:{user_id}")
        if not user_data:
            return None

        return User(
            user_id=user_id,
            username=user_data[b'username'].decode(),
            email=user_data[b'email'].decode(),
            created_at=datetime.fromisoformat(user_data[b'created_at'].decode()),
            reputation_score=float(user_data[b'reputation_score']),
            is_banned=user_data[b'is_banned'].decode() == 'True'
        )

    async def create_post(self, post_data: CreatePostRequest, user_id: str, ip_address: str) -> Post:
        """Создание нового поста с проверкой на спам"""
        user = await self.get_user(user_id)
        if not user or user.is_banned:
            raise HTTPException(status_code=403, detail="User is banned or not found")

        # Проверяем на спам
        spam_result = await self.spam_guard.comprehensive_spam_check(
            f"{post_data.title} {post_data.content}",
            user_id,
            ip_address
        )

        post_id = str(uuid4())
        post = Post(
            post_id=post_id,
            user_id=user_id,
            username=user.username,
            title=post_data.title,
            content=post_data.content,
            forum_id=post_data.forum_id,
            created_at=datetime.utcnow(),
            spam_score=spam_result['score'],
            is_spam=spam_result['is_spam']
        )

        # Сохраняем пост
        await self.redis.hset(
            f"post:{post_id}",
            mapping={
                "user_id": post.user_id,
                "username": post.username,
                "title": post.title,
                "content": post.content,
                "forum_id": post.forum_id,
                "created_at": post.created_at.isoformat(),
                "spam_score": post.spam_score,
                "is_spam": str(post.is_spam)
            }
        )

        # Если не спам, добавляем в публичные списки
        if not post.is_spam:
            await self.redis.zadd(f"forum:{post.forum_id}:posts", {post_id: time.time()})
            await self.redis.zadd("recent_posts", {post_id: time.time()})
        else:
            # Если спам, добавляем в карантин
            await self.redis.zadd("spam_posts", {post_id: time.time()})
            logger.warning(f"Spam detected: {post_id}, score: {spam_result['score']}")

        # Обучаем спам-фильтр
        await self.spam_guard.train_spam_filter(
            f"{post_data.title} {post_data.content}",
            post.is_spam
        )

        # Обновляем репутацию IP
        await self.spam_guard.update_ip_reputation(ip_address, post.is_spam)

        return post

    async def get_posts(self, forum_id: str, limit: int = 50) -> List[Post]:
        """Получение постов форума"""
        post_ids = await self.redis.zrevrange(f"forum:{forum_id}:posts", 0, limit - 1)
        posts = []

        for post_id in post_ids:
            post_data = await self.redis.hgetall(f"post:{post_id.decode()}")
            if post_data:
                posts.append(Post(
                    post_id=post_id.decode(),
                    user_id=post_data[b'user_id'].decode(),
                    username=post_data[b'username'].decode(),
                    title=post_data[b'title'].decode(),
                    content=post_data[b'content'].decode(),
                    forum_id=post_data[b'forum_id'].decode(),
                    created_at=datetime.fromisoformat(post_data[b'created_at'].decode()),
                    spam_score=float(post_data[b'spam_score']),
                    is_spam=post_data[b'is_spam'].decode() == 'True'
                ))

        return posts


# Инициализация приложения
app = FastAPI(title="Forum with Spam Guard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к Redis
redis_client = None
spam_guard = None
forum_service = None


@app.on_event("startup")
async def startup_event():
    global redis_client, spam_guard, forum_service

    # Подключаемся к Redis 8
    redis_client = redis.Redis(
        host='localhost',
        port=6379,
        decode_responses=False,
        health_check_interval=30
    )

    # Инициализируем компоненты
    spam_guard = SpamGuard(redis_client)
    forum_service = ForumService(redis_client, spam_guard)

    # Инициализируем спам-модель
    await spam_guard.init_spam_model()

    # Создаем тестовые форумы
    test_forums = [
        {"forum_id": "general", "name": "Общие вопросы", "description": "Общие обсуждения"},
        {"forum_id": "tech", "name": "Технологии", "description": "Обсуждение технологий"},
        {"forum_id": "news", "name": "Новости", "description": "Новости и события"}
    ]

    for forum_data in test_forums:
        await redis_client.hset(
            f"forum:{forum_data['forum_id']}",
            mapping={
                "name": forum_data["name"],
                "description": forum_data["description"],
                "created_at": datetime.utcnow().isoformat()
            }
        )

    logger.info("Forum application started successfully")


def get_client_ip(request: Request) -> str:
    """Получение IP адреса клиента"""
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.client.host


# API эндпоинты
@app.post("/api/users", response_model=User)
async def create_user(user_data: CreateUserRequest):
    """Создание нового пользователя"""
    return await forum_service.create_user(user_data)


@app.get("/api/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Получение информации о пользователе"""
    user = await forum_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/posts", response_model=Post)
async def create_post(
        post_data: CreatePostRequest,
        request: Request,
        user_id: str = "default_user"  # В реальном приложении получать из JWT
):
    """Создание нового поста"""
    ip_address = get_client_ip(request)
    return await forum_service.create_post(post_data, user_id, ip_address)


@app.get("/api/forums/{forum_id}/posts", response_model=List[Post])
async def get_forum_posts(forum_id: str, limit: int = 50):
    """Получение постов форума"""
    return await forum_service.get_posts(forum_id, limit)


@app.get("/api/spam/stats")
async def get_spam_stats():
    """Получение статистики по спаму"""
    total_spam = int(await redis_client.get("spam:total_spam") or 0)
    total_ham = int(await redis_client.get("spam:total_ham") or 0)
    spam_posts_count = await redis_client.zcard("spam_posts")

    return {
        "total_spam_trained": total_spam,
        "total_ham_trained": total_ham,
        "quarantined_posts": spam_posts_count,
        "detection_accuracy": round(total_spam / (total_spam + total_ham) * 100, 2) if (
                                                                                                   total_spam + total_ham) > 0 else 0
    }


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Главная страница с интерфейсом форума"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Forum with Spam Guard</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; color: #333; margin-bottom: 30px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .posts { margin-top: 30px; }
            .post { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid #007bff; }
            .post.spam { border-left-color: #dc3545; background: #fff5f5; }
            .post-meta { font-size: 12px; color: #666; margin-bottom: 10px; }
            .spam-indicator { color: #dc3545; font-weight: bold; }
            .stats { background: #e9ecef; padding: 15px; border-radius: 6px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="header">🛡️ Forum with Advanced Spam Guard</h1>
            <p class="header">Powered by FastAPI, Redis 8, and AI-based spam detection</p>

            <div class="stats" id="stats">
                <h3>📊 Spam Detection Statistics</h3>
                <div id="stats-content">Loading...</div>
            </div>

            <h2>✍️ Create New Post</h2>
            <form id="postForm">
                <div class="form-group">
                    <label>Forum:</label>
                    <select id="forumId" required>
                        <option value="general">Общие вопросы</option>
                        <option value="tech">Технологии</option>
                        <option value="news">Новости</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Title:</label>
                    <input type="text" id="title" required minlength="3" maxlength="200">
                </div>
                <div class="form-group">
                    <label>Content:</label>
                    <textarea id="content" required minlength="10" maxlength="10000" rows="5"></textarea>
                </div>
                <button type="submit">🚀 Create Post</button>
            </form>

            <div class="posts">
                <h2>📝 Recent Posts</h2>
                <div id="posts-container">Loading posts...</div>
            </div>
        </div>

        <script>
            // Загрузка статистики
            async function loadStats() {
                try {
                    const response = await fetch('/api/spam/stats');
                    const stats = await response.json();
                    document.getElementById('stats-content').innerHTML = \`
                        <strong>Spam Trained:</strong> \${stats.total_spam_trained} | 
                        <strong>Ham Trained:</strong> \${stats.total_ham_trained} | 
                        <strong>Quarantined Posts:</strong> \${stats.quarantined_posts} | 
                        <strong>Detection Accuracy:</strong> \${stats.detection_accuracy}%
                    \`;
                } catch (error) {
                    document.getElementById('stats-content').innerHTML = 'Error loading stats';
                }
            }

            // Загрузка постов
            async function loadPosts(forumId = 'general') {
                try {
                    const response = await fetch(\`/api/forums/\${forumId}/posts\`);
                    const posts = await response.json();
                    const container = document.getElementById('posts-container');

                    if (posts.length === 0) {
                        container.innerHTML = '<p>No posts yet. Create the first one!</p>';
                        return;
                    }

                    container.innerHTML = posts.map(post => \`
                        <div class="post \${post.is_spam ? 'spam' : ''}">
                            <div class="post-meta">
                                👤 \${post.username} | 📅 \${new Date(post.created_at).toLocaleString()} | 
                                🎯 Spam Score: \${(post.spam_score * 100).toFixed(1)}%
                                \${post.is_spam ? '<span class="spam-indicator">⚠️ SPAM DETECTED</span>' : ''}
                            </div>
                            <h3>\${post.title}</h3>
                            <p>\${post.content}</p>
                        </div>
                    \`).join('');
                } catch (error) {
                    document.getElementById('posts-container').innerHTML = 'Error loading posts';
                }
            }

            // Отправка формы
            document.getElementById('postForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = {
                    title: document.getElementById('title').value,
                    content: document.getElementById('content').value,
                    forum_id: document.getElementById('forumId').value
                };

                try {
                    const response = await fetch('/api/posts?user_id=demo_user', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });

                    if (response.ok) {
                        const post = await response.json();
                        alert(post.is_spam ? 
                            \`⚠️ Post created but marked as SPAM (score: \${(post.spam_score * 100).toFixed(1)}%)\` : 
                            \`✅ Post created successfully! (spam score: \${(post.spam_score * 100).toFixed(1)}%)\`
                        );
                        document.getElementById('postForm').reset();
                        loadPosts(formData.forum_id);
                        loadStats();
                    } else {
                        const error = await response.json();
                        alert('Error: ' + error.detail);
                    }
                } catch (error) {
                    alert('Network error: ' + error.message);
                }
            });

            // Обновление постов при смене форума
            document.getElementById('forumId').addEventListener('change', (e) => {
                loadPosts(e.target.value);
            });

            // Инициализация
            loadStats();
            loadPosts();

            // Автообновление каждые 30 секунд
            setInterval(() => {
                loadStats();
                loadPosts(document.getElementById('forumId').value);
            }, 30000);
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)