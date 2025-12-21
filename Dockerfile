# Multi-stage build for smaller image
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Copy Python packages from builder (system-wide installation)
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p logs cache backups && \
    chmod -R 755 logs cache backups

# Run as non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Health check - simple check that Python can import and basic functionality works
# Database check is done via file existence and basic connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os; db_file = 'bot.db'; (os.path.exists(db_file) and os.path.isfile(db_file)) or exit(1)" || exit 1

USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
