# AI_RAG_Server/Dockerfile
FROM python:3.12-slim

# Установка системных зависимостей для компиляции и работы
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем зависимости и устанавливаем Python-пакеты
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё содержимое проекта
COPY . .

# Запуск сервера
CMD ["python", "app/main.py"]