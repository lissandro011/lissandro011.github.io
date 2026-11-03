# Imagen Debian (glibc): el binario de neonize no funciona en Alpine (musl).
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY bot.py config.py sticker.py ./

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/data \
    && chown bot:bot /app/data
USER bot

# La sesión de WhatsApp vive acá: montá un volumen para no perderla.
VOLUME ["/app/data"]

CMD ["python", "bot.py"]
