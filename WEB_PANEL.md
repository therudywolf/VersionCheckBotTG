# VersionCheckBot - Web Management Panel

## Overview

The web management panel provides a modern, real-time interface for monitoring and managing your VersionCheckBot instance. It includes:

- **📊 Real-time Dashboard** - System status, user statistics, subscription metrics
- **👥 User Management** - View active users, joined dates, last activity
- **📢 Broadcast Messages** - Send notifications to all or specific users
- **📈 Analytics** - Detailed usage statistics and trends
- **⚙️ System Status** - Database health, API status, version info

## Quick Start

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run web panel alongside bot
python -m uvicorn bot.web.app:app --reload --host 0.0.0.0 --port 8000
```

Access the dashboard at: `http://localhost:8000`

### Production with Docker

```bash
# Using docker-compose with both bot and web panel
docker compose -f docker-compose.prod.yml up -d
```

The web panel will be available at: `http://localhost:8000`

## API Reference

### Health Check
```bash
GET /api/health
```
Returns bot health status.

### System Statistics
```bash
GET /api/stats
```
Returns comprehensive system statistics:
- User count and activity
- Query statistics
- Subscription metrics
- Cache status
- Database status

### Users
```bash
GET /api/users?limit=50&offset=0
```
List users with pagination.

### Subscriptions
```bash
GET /api/subscriptions?user_id=123&product=python&limit=50&offset=0
```
List subscriptions with optional filters.

### Broadcast Message
```bash
POST /api/admin/broadcast
Content-Type: application/json

{
    "message": "Important announcement",
    "user_ids": [123, 456, 789]  // Optional: specific users
}
```
Send broadcast message to users.

## Features

### Dashboard
- **Real-time metrics** updated every 30 seconds
- **Status indicators** showing bot, database, and API health
- **Quick overview** of key statistics

### Users Management
- Browse registered users
- View join dates and last activity
- Quick user lookup

### Broadcasting
- Send messages to all users or specific users
- Preview message before sending
- Track delivery status

### Admin Tools
- System health checks
- Database connectivity status
- Performance metrics
- Uptime tracking

## Configuration

The web panel reads configuration from `.env`:

```env
# Web Panel (optional)
WEB_PORT=8000
WEB_HOST=0.0.0.0

# Admin Authentication (optional)
# Not yet implemented - currently requires local access only
ADMIN_TOKEN=your_secure_token_here
```

## Security Considerations

⚠️ **Current Implementation:**
- Web panel currently accessible without authentication (local network only)
- Recommended for internal/protected networks

✅ **For Production:**
1. **Enable Authentication**
   - Implement JWT-based authentication
   - Add ADMIN_TOKEN validation
   - Use HTTPS/TLS

2. **Network Security**
   - Place behind reverse proxy (nginx, Caddy)
   - Use firewall rules to restrict access
   - Enable authentication middleware

3. **Data Protection**
   - All sensitive endpoints should require authentication
   - Use environment variables for sensitive config
   - Implement rate limiting

## Environment Variables

```env
# Web Panel Configuration
WEB_PORT=8000                    # Port for web panel
WEB_HOST=0.0.0.0               # Bind address
WEB_DEBUG=false                  # Debug mode

# Database (shared with bot)
DATABASE_URL=sqlite:///./bot.db  # SQLite or PostgreSQL

# Logging
LOG_LEVEL=INFO
```

## Development

### Project Structure
```
bot/web/
├── __init__.py
├── app.py           # FastAPI application
└── static/
    └── index.html   # Dashboard UI
```

### Adding New Endpoints

1. **Create a new route in `bot/web/app.py`:**

```python
@app.get("/api/custom-endpoint")
async def custom_endpoint():
    """Description"""
    return {"status": "ok"}
```

2. **Update the frontend in `static/index.html`:**

```javascript
async function loadCustomData() {
    const response = await fetch('/api/custom-endpoint');
    const data = await response.json();
    // Process data
}
```

### Running Tests

```bash
pytest tests/ -v --no-cov
```

### Code Quality

```bash
# Lint
pylint bot/

# Format
black bot/ --line-length=100

# Type checking
mypy bot/
```

## Troubleshooting

### Web panel not connecting to database
- Check `DATABASE_URL` in `.env`
- Verify database is running: `docker ps` (if using Docker)
- Check database logs: `docker logs versioncheckbot-db`

### Port already in use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or change port in .env
WEB_PORT=8001
```

### Authentication issues
- Ensure `.env` file is properly formatted
- Check database connectivity
- Review logs: `tail -f logs/app.log`

## Performance Tips

1. **Database Optimization**
   - Use PostgreSQL instead of SQLite for production
   - Create proper indexes on frequently queried columns
   - Monitor query performance

2. **Caching**
   - Enable Redis for caching if available
   - Adjust TTL values in configuration
   - Monitor cache hit rates

3. **Load Testing**
   ```bash
   # Using Apache Bench
   ab -n 1000 -c 10 http://localhost:8000/api/stats
   
   # Using wrk
   wrk -t12 -c400 -d30s http://localhost:8000/api/stats
   ```

## Future Enhancements

- [ ] Authentication and authorization
- [ ] Advanced analytics and reporting
- [ ] Real-time WebSocket updates
- [ ] Subscription management UI
- [ ] CVE vulnerability dashboard
- [ ] Dark mode
- [ ] Mobile-responsive design improvements
- [ ] Export/backup functionality
- [ ] Custom alert configuration
- [ ] API key management

## License

SPDX-License-Identifier: AGPL-3.0-or-later

This web panel is part of VersionCheckBot and is licensed under the GNU Affero General Public License v3.0 or later.

## Support

For issues, questions, or feature requests:
- Create a GitHub issue
- Check existing documentation
- Review logs for error messages
