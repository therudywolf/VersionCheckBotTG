# VersionCheckBot - Installation Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Setup](#docker-setup)
4. [Database Configuration](#database-configuration)
5. [Configuration](#configuration)
6. [Running the Bot](#running-the-bot)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- **Python**: 3.10 or higher
- **Docker**: 20.10+ (optional, for containerized deployment)
- **PostgreSQL**: 12+ (optional, for production databases)
- **Git**: For cloning the repository

### Required Accounts
- **Telegram Bot Token**: Get from [@BotFather](https://t.me/BotFather)
- **NVD API Key** (optional): Get from [NIST NVD](https://nvd.nist.gov/developers/request-an-api-key)

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/therudywolf/VersionCheckBotTG.git
cd VersionCheckBotTG
```

### 2. Create Virtual Environment

```bash
# Using venv
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your values
# Required: BOT_TOKEN from @BotFather
nano .env  # or use your favorite editor
```

### 5. Initialize Database

```bash
# The database will be created automatically on first run
# For PostgreSQL, run migrations:
alembic upgrade head
```

### 6. Run the Bot

```bash
# Terminal 1: Run the bot
python bot.py

# Terminal 2: Run the web panel (optional)
python -m uvicorn bot.web.app:app --reload --host 0.0.0.0 --port 8000
```

## Docker Setup

### Quick Start

```bash
# Build and run with docker-compose
docker compose up -d

# Check logs
docker compose logs -f bot

# Stop the bot
docker compose down
```

### Production Setup

```bash
# Use production docker-compose with PostgreSQL
docker compose -f docker-compose.prod.yml up -d

# Initialize database
docker compose -f docker-compose.prod.yml exec bot alembic upgrade head

# Check status
docker compose -f docker-compose.prod.yml ps
```

### Build Custom Image

```bash
# Build bot image
docker build -t versioncheckbot:latest .

# Build web panel image
docker build -f Dockerfile.web -t versioncheckbot-web:latest .

# Run with docker run
docker run -d \
  --name versioncheckbot \
  --env-file .env \
  -v versioncheckbot-data:/app/data \
  versioncheckbot:latest
```

## Database Configuration

### SQLite (Default)

The simplest option for development and small deployments:

```env
DATABASE_URL=sqlite:///./data/bot.db
```

No additional setup required. The database file is created automatically.

### PostgreSQL (Recommended for Production)

For larger deployments and better performance:

```env
DATABASE_URL=postgresql://botuser:password@localhost:5432/botdb

# Or using docker
DATABASE_URL=postgresql://botuser:password@postgres:5432/botdb
```

**Setup PostgreSQL with Docker:**

```bash
docker run -d \
  --name versioncheckbot-postgres \
  -e POSTGRES_DB=botdb \
  -e POSTGRES_USER=botuser \
  -e POSTGRES_PASSWORD=your_secure_password \
  -v postgres-data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16-alpine
```

**Initialize Database:**

```bash
alembic upgrade head
```

## Configuration

### Required Settings

```env
# Telegram bot token - REQUIRED
BOT_TOKEN=your_token_here
```

### Optional Settings

```env
# Admin users (comma-separated Telegram IDs)
ADMIN_IDS=123456789,987654321

# NVD API key for better CVE rate limits
NVD_API_KEY=your_api_key

# Database (SQLite default)
DATABASE_URL=sqlite:///./data/bot.db

# Cache TTL (in seconds)
RELEASE_TTL=21600        # 6 hours
PRODUCTS_TTL=86400       # 24 hours
CVE_TTL=43200            # 12 hours

# Performance
MAX_PARALLEL=15          # Concurrent API requests

# Rate limiting
RATE_LIMIT_PER_MINUTE=20
RATE_LIMIT_PER_HOUR=200

# Scheduler
SCHEDULER_INTERVAL=21600  # 6 hours between checks
NOTIFICATION_ENABLED=true

# Logging
LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Web Panel
WEB_PORT=8000
WEB_HOST=0.0.0.0
WEB_DEBUG=false
```

## Running the Bot

### Development Mode

```bash
python bot.py
```

Watch for initialization messages:
```
✓ Database initialized
✓ Bot started successfully
```

### Production Mode with systemd

Create `/etc/systemd/system/versioncheckbot.service`:

```ini
[Unit]
Description=VersionCheckBot - Software Version Monitoring Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/versioncheckbot
Environment="PATH=/opt/versioncheckbot/venv/bin"
ExecStart=/opt/versioncheckbot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable versioncheckbot
sudo systemctl start versioncheckbot
sudo systemctl status versioncheckbot
```

### With Supervisor

Create `/etc/supervisor/conf.d/versioncheckbot.conf`:

```ini
[program:versioncheckbot]
directory=/opt/versioncheckbot
command=/opt/versioncheckbot/venv/bin/python bot.py
user=botuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/versioncheckbot.log
```

Start:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start versioncheckbot
```

## Verification

### Test Bot Connection

Send a message to your bot:
```
/start
```

### Check Bot Status

```bash
/health
```

### View Logs

```bash
# Docker
docker compose logs -f bot

# File
tail -f logs/app.log
```

## Troubleshooting

### Bot Token Error

**Error**: `RuntimeError: BOT_TOKEN не установлен`

**Solution**:
1. Check `.env` file exists
2. Verify `BOT_TOKEN` is set: `echo $BOT_TOKEN`
3. Get new token from [@BotFather](https://t.me/BotFather)

### Database Connection Error

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
1. Verify PostgreSQL is running: `docker ps | grep postgres`
2. Check `DATABASE_URL` in `.env`
3. Test connection: `psql -U botuser -d botdb -h localhost`

### Port Already in Use

**Error**: `OSError: [Errno 98] Address already in use`

**Solution**:
```bash
# Find process using port
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
WEB_PORT=8001
```

### Memory Issues

**Symptom**: Bot crashes with memory errors

**Solution**:
1. Reduce `MAX_PARALLEL` in `.env`
2. Reduce cache TTL values
3. Use PostgreSQL instead of SQLite
4. Increase system RAM or swap

### Slow Performance

**Symptoms**: Commands taking too long

**Solutions**:
1. Add NVD_API_KEY to reduce rate limiting
2. Increase `MAX_PARALLEL` (if not hitting limits)
3. Switch to PostgreSQL from SQLite
4. Check network connection to APIs

## Next Steps

1. Review [README.md](README.md) for feature overview
2. Check [WEB_PANEL.md](WEB_PANEL.md) for admin dashboard
3. Read [CONTRIBUTING.md](CONTRIBUTING.md) for development
4. Review [SECURITY.md](SECURITY.md) for security considerations
5. Check `.env.example` for all available options
