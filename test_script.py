
import requests
import json

BASE_URL = "http://localhost:8000/api"

# 1. Создаем пользователя
create_user_payload = {
    "username": "test_user",
    "email": "test@example.com"
}
try:
    response = requests.post(f"{BASE_URL}/users", json=create_user_payload)
    response.raise_for_status()  # Проверяем на HTTP ошибки
    user = response.json()
    user_id = user['user_id']
    print(f"Пользователь создан успешно. User ID: {user_id}")

    # 2. Создаем пост от имени этого пользователя
    create_post_payload = {
        "title": "Мой первый пост",
        "content": "Это содержимое моего первого поста. Надеюсь, он не будет помечен как спам.",
        "forum_id": "general"
    }
    
    # Обратите внимание, что мы передаем user_id как параметр запроса
    response = requests.post(f"{BASE_URL}/posts?user_id={user_id}", json=create_post_payload)
    response.raise_for_status()
    post = response.json()
    print("Пост создан успешно:")
    print(json.dumps(post, indent=2, ensure_ascii=False))

except requests.exceptions.RequestException as e:
    print(f"Произошла ошибка: {e}")
    if e.response:
        print(f"Ответ сервера: {e.response.text}")

