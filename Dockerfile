# Multi-stage build for smaller image
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs cache backups

# Health check (basic check - can be improved)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sqlite3; conn = sqlite3.connect('bot.db'); conn.close()" || exit 1

# Run as non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
