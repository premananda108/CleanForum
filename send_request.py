import requests
import json

url = "http://localhost:8000/api/posts"
headers = {"Content-Type": "application/json"}
data = {
    "author": "Tester",
    "title": "Тестовый пост",
    "content": "Это тестовое сообщение, которое точно длиннее десяти символов."
}

try:
    response = requests.post(url, headers=headers, data=json.dumps(data, ensure_ascii=False).encode('utf-8'))
    response.raise_for_status()
    print("Сообщение 'Тестовый пост' успешно отправлено!")
    print(response.json())
except requests.exceptions.RequestException as e:
    print(f"Ошибка при отправке запроса: {e}")
    if e.response:
        print(f"Ответ сервера: {e.response.text}")