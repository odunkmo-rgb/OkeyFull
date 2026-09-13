FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY discord-bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY discord-bot /app/discord-bot

# Railway can mount a persistent volume at /data.
RUN mkdir -p /data

CMD ["python", "discord-bot/main.py"]