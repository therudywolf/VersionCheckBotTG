# VersionCheckBot - Development Guide

## Overview

This guide is for developers who want to contribute to or extend VersionCheckBot.

## Project Structure

```
VersionCheckBotTG/
├── bot/                       # Main bot module
│   ├── database/             # Database initialization & models setup
│   ├── handlers/             # Command and message handlers
│   ├── models/               # SQLAlchemy ORM models
│   ├── scheduler/            # Async task scheduling
│   ├── services/             # Business logic services
│   ├── utils/                # Utility functions
│   └── web/                  # Web management panel (FastAPI)
├── tests/                     # Unit tests (pytest)
├── alembic/                   # Database migrations
├── scripts/                   # Utility scripts
├── bot.py                     # Main entry point
├── config.py                  # Configuration & settings
└── requirements.txt           # Python dependencies
```

## Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/therudywolf/VersionCheckBotTG.git
cd VersionCheckBotTG

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dev dependencies
pip install -r requirements.txt
pip install -e .  # Install in editable mode
```

### 2. Configure for Development

```bash
cp .env.example .env
# Edit .env - set a test bot token from @BotFather
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v --no-cov

# Run specific test
pytest tests/test_version_service.py -v

# Run with coverage
pytest tests/ --cov=bot --cov-report=html
```

## Code Standards

### Style Guide

- **PEP 8**: Follow Python style guide
- **Line Length**: Max 100 characters
- **Docstrings**: Use Google-style docstrings

```python
def check_version(product: str, version: str) -> dict:
    """Check software version status.
    
    Args:
        product: Software product name
        version: Version string to check
        
    Returns:
        Dictionary with version status information
        
    Raises:
        ValueError: If product or version is invalid
    """
```

### Linting

```bash
# Install linting tools
pip install pylint black flake8 mypy

# Format code
black bot/ --line-length=100

# Lint code
pylint bot/ --disable=all --enable=E,F

# Type checking
mypy bot/
```

### License Headers

All Python files must start with AGPL-3.0 header:

```python
"""
VersionCheckBot - Description of module

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
```

Use the included script to add headers:
```bash
python scripts/add_license_headers.py
```

## Working with the Code

### Adding a New Handler

1. Create file in `bot/handlers/`
2. Import in `bot/handlers/__init__.py`
3. Register in `bot.py`

```python
# bot/handlers/my_handler.py
from telegram import Update
from telegram.ext import ContextTypes

async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mycommand"""
    user_id = update.effective_user.id
    await update.message.reply_text("Response here")
```

### Adding a New Model

1. Create in `bot/models/`
2. Import in `bot/models/__init__.py`
3. Create migration: `alembic revision --autogenerate -m "Add new model"`

```python
# bot/models/my_model.py
from sqlalchemy import Column, Integer, String, DateTime
from bot.database.db import Base
from datetime import datetime

class MyModel(Base):
    __tablename__ = "my_models"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)
```

### Adding a New Service

1. Create in `bot/services/`
2. Implement with async/await pattern

```python
# bot/services/my_service.py
from typing import Optional

class MyService:
    """Service for handling my functionality"""
    
    async def process_data(self, data: str) -> Optional[dict]:
        """Process data and return result"""
        try:
            result = await self._fetch_data(data)
            return result
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return None
    
    async def _fetch_data(self, data: str) -> dict:
        """Internal method to fetch data"""
        # Implementation
        pass
```

### Working with Database

#### Query Examples

```python
from bot.database.db import get_session
from bot.models.user import User
from sqlalchemy import select

async with get_session() as session:
    # Get all users
    result = await session.execute(select(User))
    users = result.scalars().all()
    
    # Get user by ID
    user = await session.get(User, user_id)
    
    # Filter
    result = await session.execute(
        select(User).where(User.is_admin == True)
    )
```

#### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add user email field"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/test_version_service.py

# Specific test
pytest tests/test_version_service.py::TestVersionServiceMatching::test_find_release

# With coverage
pytest tests/ --cov=bot --cov-report=html

# Verbose output
pytest tests/ -v --tb=short
```

### Writing Tests

```python
# tests/test_my_feature.py
import pytest
from unittest.mock import Mock, patch
from bot.services.my_service import MyService

class TestMyService:
    @pytest.fixture
    async def service(self):
        return MyService()
    
    @pytest.mark.asyncio
    async def test_process_data(self, service):
        result = await service.process_data("test")
        assert result is not None
        assert "key" in result
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        with patch('bot.services.my_service.fetch_external') as mock:
            mock.side_effect = Exception("API Error")
            result = await service.process_data("test")
            assert result is None
```

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring
- `test/description` - Tests

### Commit Messages

```
feat: Add new version comparison command
fix: Handle missing API responses correctly
docs: Update installation guide
refactor: Simplify database session management
test: Add test coverage for fuzzy matching
```

### Pull Request Process

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and commit: `git commit -m "feat: Add feature"`
4. Push to fork: `git push origin feature/my-feature`
5. Open Pull Request
6. Wait for CI/tests to pass
7. Address review comments
8. Merge when approved

## Performance Optimization

### Profiling

```python
import cProfile
import pstats
from io import StringIO

pr = cProfile.Profile()
pr.enable()

# Code to profile
my_function()

pr.disable()
s = StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats()
print(s.getvalue())
```

### Async/Await Best Practices

```python
# Good: Concurrent operations
async def fetch_multiple():
    tasks = [
        fetch_version(product1),
        fetch_version(product2),
        fetch_version(product3),
    ]
    results = await asyncio.gather(*tasks)

# Bad: Sequential operations
async def fetch_multiple():
    r1 = await fetch_version(product1)
    r2 = await fetch_version(product2)
    r3 = await fetch_version(product3)
```

### Database Query Optimization

```python
# Bad: N+1 query problem
for user in users:
    subscriptions = session.query(Subscription).filter_by(user_id=user.id)

# Good: Join query
subscriptions = session.query(User, Subscription).join(Subscription)
```

## Debugging

### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
```

### Using Python Debugger

```python
import pdb

async def my_function():
    data = fetch_data()
    pdb.set_trace()  # Execution pauses here
    process(data)
```

### Common Issues

**Bot not responding to commands**
- Check handler registration in `bot.py`
- Verify command filters
- Check logs for exceptions

**Database errors**
- Verify migrations run: `alembic current`
- Check database connection in logs
- Test query manually with `psql` or `sqlite3`

**Memory leaks**
- Check async task cleanup
- Verify session closing in context managers
- Monitor with `memory_profiler`

## Documentation

### Docstring Format

```python
async def process_version(product: str, version: str) -> dict:
    """Process and validate version information.
    
    This function checks if the version is valid for the given product
    and returns status information including EOL dates.
    
    Args:
        product: Name of the software product
        version: Version string to process
        
    Returns:
        Dictionary with keys:
            - status: str - Release status
            - eol_date: datetime - End of life date or None
            - is_vulnerable: bool - Whether CVEs exist
            
    Raises:
        ValueError: If product is not found
        InvalidVersionError: If version format is invalid
        
    Example:
        >>> result = await process_version('python', '3.11')
        >>> print(result['status'])
        'active'
    """
```

## Resources

- [Python-Telegram-Bot Docs](https://python-telegram-bot.readthedocs.io/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/)
- [Google Docstring Style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

## Questions?

- Check existing issues/discussions
- Review similar code patterns in the codebase
- Open a discussion on GitHub
- Check [SECURITY.md](SECURITY.md) for security concerns
