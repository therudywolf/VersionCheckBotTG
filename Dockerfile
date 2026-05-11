FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN mkdir -p logs cache data && \
    chmod -R 755 logs cache data

RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, sys; sys.exit(0 if os.path.isfile('data/bot.db') else 1)"

USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
