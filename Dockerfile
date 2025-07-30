# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файл с зависимостями в рабочую директорию
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта в рабочую директорию
COPY . .

# Указываем команду для запуска приложения
# FastAPI приложение будет доступно на порту 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
