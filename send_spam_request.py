import requests
import json

url = "http://localhost:8000/api/posts"
headers = {"Content-Type": "application/json"}
spam_data = {
    "author": "Spammer",
    "title": "Guaranteed Crypto Trading!",
    "content": "Earn money fast with our new crypto trading platform. Buy now for a limited time offer!"
}

print("Отправка спам-сообщения...")

try:
    response = requests.post(url, headers=headers, data=json.dumps(spam_data, ensure_ascii=False).encode('utf-8'))
    print(f"Статус-код ответа: {response.status_code}")
    print("Ответ сервера:")
    # Пытаемся декодировать ответ как JSON, если не получается - выводим как текст
    try:
        print(response.json())
    except json.JSONDecodeError:
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"Ошибка при отправке запроса: {e}")

