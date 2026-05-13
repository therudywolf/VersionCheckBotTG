# VersionCheckBot - Architecture & Design

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram API                             │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────▼────────────┐
         │    Bot Core (Async)    │
         │  python-telegram-bot   │
         └───────────┬────────────┘
                     │
        ┌────────────▼────────────────┐
        │    Message Handlers         │
        ├─────────────────────────────┤
        │ • Commands                  │
        │ • Messages                  │
        │ • Callbacks                 │
        │ • Inline Queries            │
        └────────────────────────────┘
                     │
        ┌────────────▼────────────────┐
        │   Business Logic            │
        ├─────────────────────────────┤
        │ • Version Service           │
        │ • CVE Service               │
        │ • Notification Service      │
        │ • Monitoring Service        │
        └────────────────────────────┘
                     │
        ┌────────────▼────────────────┐
        │    Database Layer           │
        ├─────────────────────────────┤
        │ • SQLAlchemy ORM            │
        │ • Models                    │
        │ • Migrations (Alembic)      │
        └────────────────────────────┘
                     │
        ┌────────────▼────────────────────────────┐
        │   External APIs                        │
        ├────────────────────────────────────────┤
        │ • endoflife.date (Product versions)    │
        │ • NVD/NIST (CVE data)                  │
        └────────────────────────────────────────┘
```

## Core Components

### 1. Bot Core (`bot.py`)

**Responsibility**: Main application orchestration

- Initializes Telegram bot with python-telegram-bot
- Registers all handlers
- Manages application lifecycle
- Handles graceful shutdown
- Sets up logging and error handling

**Key Classes**:
- `Application`: Main Telegram application

**Dependencies**:
- python-telegram-bot
- config
- all handler modules

### 2. Handlers Module (`bot/handlers/`)

**Responsibility**: Process user input and commands

#### `commands.py` - Command Handlers
- `/start` - Initialize user
- `/check` - Check version status
- `/cve` - Find CVE vulnerabilities
- `/subscribe` - Subscribe to monitoring
- `/subscriptions` - List user subscriptions
- `/health` - Bot status
- And 15+ more commands

#### `messages.py` - Message Handlers
- Text message processing
- File uploads (`.txt` with product lists)
- Fuzzy matching for product names

#### `callbacks.py` - Button Callbacks
- Inline button responses
- Pagination handlers
- Action confirmations

#### `inline.py` - Inline Queries
- `@botname product version` in any chat
- Real-time search with completions

### 3. Services Module (`bot/services/`)

**Responsibility**: Business logic and external integrations

#### `version_service.py`
```python
# Core version checking logic
- Fetch product information from endoflife.date
- Match user versions against releases
- Calculate EOL status
- Handle aliases (python → Python, nodejs → node.js)
```

**Key Methods**:
```python
async def check_version(product, version) -> VersionInfo
async def get_products() -> List[str]
async def find_release(product, version) -> Release
```

#### `cve_service.py`
```python
# CVE vulnerability tracking
- Query NVD API for vulnerabilities
- Cache results with TTL
- Circuit breaker for rate limiting
- Handle API errors gracefully
```

#### `notification_service.py`
```python
# User notifications
- Send messages to subscribed users
- Handle send failures
- Track delivery status
```

#### `monitoring_service.py`
```python
# Subscription monitoring
- Periodic checks of subscriptions
- Status change detection
- Notification triggering
- Statistics gathering
```

### 4. Database Module (`bot/database/`)

**Responsibility**: Data persistence

#### Models (`bot/models/`)
```
User → Subscription → CVERecord
   → UserSettings
   → QueryHistory
   → Favorite
   → Admin
   → Notification
   → UserStats
```

**Key Models**:
- `User`: Telegram users
- `Subscription`: Version monitoring subscriptions
- `CVERecord`: Cached CVE data
- `QueryHistory`: User search history
- `UserSettings`: Personal preferences
- `Notification`: Alert queue

#### Database Operations
- SQLAlchemy ORM for queries
- Alembic for migrations
- Connection pooling
- Async session management

### 5. Utilities Module (`bot/utils/`)

**Responsibility**: Shared functionality

- `fuzzy.py`: Fuzzy matching for product names
- `parser.py`: Version string parsing
- `cache.py`: In-memory caching with TTL
- `rate_limiter.py`: API rate limiting
- `circuit_breaker.py`: Failure protection
- `pagination.py`: Message pagination
- `access_control.py`: Permission checking
- `logging_config.py`: Structured logging

### 6. Scheduler Module (`bot/scheduler/`)

**Responsibility**: Async background tasks

```python
# Periodic subscription checks
- Run every SCHEDULER_INTERVAL seconds
- Check all active subscriptions
- Detect status changes
- Send notifications
- Update statistics
```

### 7. Web Panel Module (`bot/web/`)

**Responsibility**: Admin dashboard and API

#### `app.py` - FastAPI Application
```python
GET /api/health              # Bot status
GET /api/stats               # System statistics
GET /api/users               # User listing
GET /api/subscriptions       # Subscription listing
POST /api/admin/broadcast    # Send messages
```

#### `static/index.html` - Dashboard UI
- Real-time metrics
- User management
- Broadcast interface
- System monitoring

## Data Flow

### Version Check Flow

```
User: "/check python 3.11"
   │
   └─→ CommandHandler.check()
       │
       ├─→ VersionService.check_version("python", "3.11")
       │   │
       │   ├─→ Cache: Check if cached
       │   │   (Return if valid)
       │   │
       │   └─→ endoflife.date API
       │       │
       │       └─→ Cache result
       │
       ├─→ CVEService.get_cves() [optional]
       │
       └─→ Format response
           └─→ Telegram.send_message()
```

### Subscription Flow

```
User: "/subscribe python 3.11"
   │
   └─→ CommandHandler.subscribe()
       │
       ├─→ Database: Create Subscription
       │
       ├─→ Scheduler checks periodically
       │   │
       │   ├─→ Fetch current status
       │   │
       │   ├─→ Compare with stored status
       │   │
       │   └─→ If changed:
       │       └─→ NotificationService.notify()
       │           └─→ Telegram.send_message()
       │
       └─→ Confirmation to user
```

## Configuration Management

### Environment Variables

```
.env (local only, not in git)
    ├── BOT_TOKEN (Telegram token)
    ├── ADMIN_IDS (Admin user IDs)
    ├── NVD_API_KEY (CVE API key)
    ├── DATABASE_URL (SQLite or PostgreSQL)
    ├── LOG_LEVEL
    └── Performance settings
        ├── MAX_PARALLEL
        ├── RATE_LIMIT_PER_MINUTE
        └── CACHE_TTL values
```

### Config Class

```python
class Settings(BaseSettings):
    # Validates environment
    # Provides type safety
    # Includes defaults
    # Runs on startup
```

## Error Handling

### Layers of Protection

1. **API Layer** (endoflife.date, NVD)
   - Circuit breaker
   - Exponential backoff
   - Graceful degradation

2. **Handler Layer**
   - Try/catch for user errors
   - User-friendly messages
   - Logging of exceptions

3. **Database Layer**
   - Connection pooling
   - Transaction management
   - Rollback on errors

4. **Application Layer**
   - Global exception handlers
   - Graceful shutdown
   - Health checks

## Performance Optimization

### Caching Strategy

```
Cache Layer:
├── In-memory (Python dict)
│   ├── Products (24h TTL)
│   ├── Releases (6h TTL)
│   └── CVEs (12h TTL)
│
└── Database
    ├── User subscriptions
    ├── Cached CVE records
    └── Query history
```

### Async/Concurrent Operations

```python
# Concurrent API calls
results = await asyncio.gather(
    api1.fetch(),
    api2.fetch(),
    api3.fetch()
)

# Connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    pool_pre_ping=True
)
```

### Database Optimization

- Indexed fields: `product`, `user_id`, `active`
- Connection pooling with retry logic
- Batch operations for updates
- Proper pagination for large result sets

## Security Architecture

### API Key Management

```
Sensitive Data Flow:
┌─────────────┐
│ Environment │
│   (.env)    │ ← Loaded at startup
└──────┬──────┘
       │
       └─→ Settings object
           │
           └─→ Service classes
               │
               └─→ API requests (HTTPS only)
```

### Rate Limiting

- Per-user rate limits
- API-specific limits
- Circuit breaker for failures
- Exponential backoff

### Access Control

- Telegram user verification
- Admin checks for admin commands
- Public/private command filtering
- Subscription ownership verification

## Scalability Considerations

### Current Design (Single Instance)

- SQLite suitable for <10k users
- Single async bot instance
- In-memory caching
- Polling scheduler

### For Larger Deployments

1. **Database**
   - Use PostgreSQL instead of SQLite
   - Add read replicas
   - Proper indexing

2. **Caching**
   - Redis for distributed cache
   - Cache warming strategies
   - TTL optimization

3. **Message Queue**
   - RabbitMQ or Celery
   - Decouple message sending
   - Better error handling

4. **Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - ELK stack for logs

## Testing Architecture

```
Unit Tests (bot/services/)
   │
   ├─→ Mocked dependencies
   ├─→ Fast execution
   └─→ High coverage

Integration Tests (with DB)
   │
   ├─→ Test database layer
   ├─→ Slower execution
   └─→ Real data validation
```

## Deployment Architecture

### Docker Multi-Stage Build

```dockerfile
Stage 1 (Builder):
├── Install build tools
├── Compile dependencies
└── Create wheel files

Stage 2 (Runtime):
├── Copy wheels from builder
├── Minimal base image
├── Non-root user
└── Health checks
```

### Docker Compose

```
Services:
├── Bot (Python application)
├── Web Panel (FastAPI)
└── PostgreSQL (optional)

Volumes:
├── Bot data
├── Logs
└── Cache
```

## Documentation Structure

- `README.md` - Project overview
- `INSTALLATION.md` - Setup guides
- `DEVELOPMENT.md` - Developer guide
- `TESTING.md` - Test documentation
- `WEB_PANEL.md` - Admin dashboard docs
- `ARCHITECTURE.md` - This file
- `SECURITY.md` - Security guidelines
- `CONTRIBUTING.md` - Contribution guidelines
- `CODE_OF_CONDUCT.md` - Community standards
- `CHANGELOG.md` - Version history

## Key Design Principles

1. **Async-First**: All I/O operations are async
2. **Fail-Safe**: Graceful degradation on errors
3. **Scalable**: Multi-instance capable with Redis
4. **Maintainable**: Clear separation of concerns
5. **Tested**: Good test coverage
6. **Documented**: Comprehensive documentation
7. **Secure**: Sensitive data protection
8. **Observable**: Structured logging
