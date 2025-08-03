# 🧪 Примеры API запросов для тестирования

После заполнения базы данных с помощью `populate_database.py`, вы можете протестировать API с помощью этих запросов.

## 📋 Предварительные условия

1. Запустите сервер:
   ```bash
   python main.py
   ```

2. Сервер будет доступен по адресу: `http://localhost:8000`

## 🔍 Основные API запросы

### 1. Получить список всех постов
```bash
curl -X GET "http://localhost:8000/api/posts?limit=10&offset=0"
```

### 2. Получить посты определенной категории
```bash
# Сначала получите ID категории из списка категорий
curl -X GET "http://localhost:8000/api/categories"

# Затем запросите посты категории (замените CATEGORY_ID)
curl -X GET "http://localhost:8000/api/posts?category_id=CATEGORY_ID&limit=5"
```

### 3. Получить конкретный пост
```bash
# Замените POST_ID на реальный ID поста из списка
curl -X GET "http://localhost:8000/api/posts/POST_ID"
```

### 4. Поиск постов
```bash
# Поиск по ключевому слову
curl -X GET "http://localhost:8000/api/search?q=заработок&limit=5"

# Векторный поиск похожих постов
curl -X POST "http://localhost:8000/api/search/similar" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Как заработать деньги",
    "content": "Хочу найти способы заработка в интернете",
    "tags": ["деньги", "заработок"]
  }'
```

### 5. Получить категории
```bash
curl -X GET "http://localhost:8000/api/categories"
```

### 6. Создать новый пост
```bash
curl -X POST "http://localhost:8000/api/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Тестовый пост",
    "content": "Это содержимое тестового поста для проверки API",
    "category_id": "CATEGORY_ID",
    "tags": ["тест", "api"]
  }'
```

### 7. Панель модератора
```bash
# Получить все посты для модерации (включая спам)
curl -X GET "http://localhost:8000/api/moderator/posts?limit=20"

# Получить статистику спама
curl -X GET "http://localhost:8000/api/moderator/spam-stats"

# Получить информацию о векторном классификаторе
curl -X GET "http://localhost:8000/api/moderator/classifier-stats"
```

### 8. Анализ спама для поста
```bash
# Получить результаты анализа спама (замените POST_ID)
curl -X GET "http://localhost:8000/api/posts/POST_ID/spam-analysis"
```

## 🌐 Веб-интерфейс

Также доступны HTML страницы:

- **Главная страница:** http://localhost:8000/
- **Создание поста:** http://localhost:8000/create
- **Панель модератора:** http://localhost:8000/moderator
- **Поиск:** http://localhost:8000/search
- **Категория:** http://localhost:8000/category/CATEGORY_ID
- **Страница поста:** http://localhost:8000/posts/POST_ID

## 📊 Полезные запросы для отладки

### Проверка здоровья приложения
```bash
curl -X GET "http://localhost:8000/health"
```

### Получение логов приложения
```bash
curl -X GET "http://localhost:8000/api/logs"
```

### API документация (Swagger)
Откройте в браузере: http://localhost:8000/docs

## 🧪 Сценарии тестирования

### Сценарий 1: Проверка фильтрации спама
1. Получите список всех постов
2. Обратите внимание на посты со статусом "spam"
3. Попробуйте создать новый пост с подозрительным содержанием
4. Проверьте, как система определяет спам

### Сценарий 2: Тестирование поиска
1. Выполните текстовый поиск по слову "заработок"
2. Попробуйте векторный поиск с похожим содержанием
3. Сравните результаты обычного и векторного поиска

### Сценарий 3: Работа модератора
1. Откройте панель модератора
2. Просмотрите все посты, включая спам
3. Проверьте статистику классификации

## 🔧 Примеры ответов API

### Успешный ответ получения постов:
```json
[
  {
    "id": "uuid-string",
    "title": "Название поста",
    "content": "Содержание поста...",
    "category_id": "category-uuid",
    "category_name": "Технологии",
    "author_id": "user-uuid",
    "author_username": "alice_blogger",
    "tags": ["тег1", "тег2"],
    "status": "published",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
    "view_count": 5,
    "comment_count": 0,
    "vote_score": 0,
    "is_spam": false,
    "spam_score": 0.1,
    "reading_time": 2
  }
]
```

### Ответ при создании спам-поста:
```json
{
  "detail": "Ваш пост был определен как спам и не может быть опубликован."
}
```

## 🚨 Обработка ошибок

### 404 - Пост не найден
```json
{
  "detail": "Пост не найден"
}
```

### 422 - Спам обнаружен
```json
{
  "detail": "Ваш пост был определен как спам и не может быть опубликован."
}
```

### 500 - Внутренняя ошибка сервера
```json
{
  "detail": "Внутренняя ошибка при создании поста"
}
```

## 📝 Дополнительные инструменты

### HTTPie (альтернатива curl)
```bash
# Установка
pip install httpie

# Примеры использования
http GET localhost:8000/api/posts
http POST localhost:8000/api/posts title="Тест" content="Содержание" category_id="CATEGORY_ID" tags:='["тест"]'
```

### Postman Collection
Импортируйте URL `http://localhost:8000/docs` в Postman для автоматического создания коллекции запросов.
