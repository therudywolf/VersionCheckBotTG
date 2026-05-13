# VersionCheckBot - Testing Guide

## Overview

This guide covers testing strategies, best practices, and how to run the test suite.

## Test Structure

```
tests/
├── __init__.py
├── test_version_service.py   # Version matching and comparison tests
├── test_cache.py              # Caching mechanism tests
└── test_parser.py             # Version string parsing tests
```

## Running Tests

### Quick Start

```bash
# Run all tests
pytest tests/ -v --no-cov

# Run with coverage report
pytest tests/ --cov=bot --cov-report=html

# Watch mode (requires pytest-watch)
ptw tests/
```

### Test Filtering

```bash
# Run specific test file
pytest tests/test_version_service.py

# Run specific test class
pytest tests/test_version_service.py::TestVersionServiceMatching

# Run specific test
pytest tests/test_version_service.py::TestVersionServiceMatching::test_find_release_by_patch_version

# Run tests matching pattern
pytest tests/ -k "version"

# Run all except slow tests
pytest tests/ -m "not slow"
```

### Continuous Testing

```bash
# Install pytest-watch
pip install pytest-watch

# Run with auto-reload on file changes
ptw tests/

# Run with specific arguments
ptw tests/ -- -v --tb=short
```

## Test Coverage

### Current Coverage

- Core version matching logic: ✓ 85%+
- Cache utilities: ✓ 80%+
- Parser utilities: ✓ 75%+
- Database models: ⚠️ 40% (needs expansion)
- API handlers: ⚠️ 30% (needs expansion)

### Generate Coverage Report

```bash
# Generate HTML report
pytest tests/ --cov=bot --cov-report=html
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
# or
start htmlcov/index.html  # Windows

# Generate terminal report
pytest tests/ --cov=bot --cov-report=term-missing

# Generate XML (for CI/CD)
pytest tests/ --cov=bot --cov-report=xml
```

## Writing Tests

### Test File Template

```python
"""
Tests for module_name

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from bot.services.my_service import MyService


class TestMyService:
    """Test suite for MyService"""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        return MyService()
    
    @pytest.fixture
    async def async_service(self):
        """Create service instance for async testing"""
        return MyService()
    
    def test_simple_operation(self, service):
        """Test a simple synchronous operation"""
        result = service.simple_method("input")
        assert result == "expected_output"
    
    @pytest.mark.asyncio
    async def test_async_operation(self, async_service):
        """Test an asynchronous operation"""
        result = await async_service.async_method("input")
        assert result is not None
    
    def test_error_handling(self, service):
        """Test error handling"""
        with pytest.raises(ValueError):
            service.method_that_raises()
    
    @patch('bot.services.my_service.external_function')
    def test_with_mock(self, mock_func, service):
        """Test with mocked dependency"""
        mock_func.return_value = "mocked_result"
        result = service.method_that_calls_external()
        assert result == "mocked_result"
        mock_func.assert_called_once()
    
    @pytest.mark.parametrize("input_val,expected", [
        ("test1", "output1"),
        ("test2", "output2"),
        ("test3", "output3"),
    ])
    def test_multiple_inputs(self, service, input_val, expected):
        """Test with multiple input scenarios"""
        result = service.method(input_val)
        assert result == expected
```

### Mocking Best Practices

```python
# Mock external API calls
@patch('bot.services.cve_service.requests.get')
async def test_cve_fetch(mock_get):
    mock_get.return_value.json.return_value = {
        'vulnerabilities': [{'id': 'CVE-2024-0001'}]
    }
    
    service = CVEService()
    result = await service.fetch_cves('python', '3.11')
    assert len(result) == 1

# Mock async functions
@patch('bot.services.version_service.fetch_release_data')
async def test_version_check(mock_fetch):
    mock_fetch = AsyncMock(return_value={'version': '3.11', 'eol': '2027-10-31'})
    
    service = VersionService()
    result = await service.check('python', '3.11')
    assert result['version'] == '3.11'
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await async_function()
    assert result is not None

# Multiple async operations
@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test multiple async operations"""
    results = await asyncio.gather(
        async_op1(),
        async_op2(),
        async_op3(),
    )
    assert all(results)
```

### Fixtures

```python
# Reusable fixtures
@pytest.fixture
def sample_user():
    """Create sample user for testing"""
    return {
        'id': 123456,
        'username': 'testuser',
        'first_name': 'Test',
    }

@pytest.fixture
def mock_db():
    """Create mocked database"""
    with patch('bot.database.db.get_session') as mock:
        yield mock

# Fixture with teardown
@pytest.fixture
def temp_file():
    """Create temporary file for testing"""
    path = '/tmp/test_file.txt'
    with open(path, 'w') as f:
        f.write('test data')
    
    yield path
    
    # Cleanup
    import os
    if os.path.exists(path):
        os.remove(path)
```

## Integration Testing

```python
@pytest.mark.integration
class TestIntegration:
    """Integration tests with real components"""
    
    @pytest.mark.asyncio
    async def test_full_version_check_flow(self):
        """Test complete version check flow"""
        # Setup
        service = VersionService()
        
        # Execute
        result = await service.check('python', '3.11')
        
        # Assert
        assert 'status' in result
        assert 'eol_date' in result

    @pytest.mark.asyncio
    async def test_database_operations(self):
        """Test database read/write"""
        async with get_session() as session:
            user = User(telegram_id=123, username='test')
            session.add(user)
            await session.commit()
            
            retrieved = await session.get(User, user.id)
            assert retrieved.username == 'test'
```

## Performance Testing

```python
@pytest.mark.performance
def test_fuzzy_matching_performance():
    """Ensure fuzzy matching is fast enough"""
    from bot.utils.fuzzy import fuzzy_match
    
    start = time.time()
    for _ in range(1000):
        fuzzy_match('python', ['Python', 'node.js', 'java'])
    elapsed = time.time() - start
    
    assert elapsed < 1.0  # Should complete in < 1 second

@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_api_calls():
    """Test performance of concurrent API calls"""
    service = VersionService()
    
    start = time.time()
    results = await asyncio.gather(*[
        service.check(product, '1.0')
        for product in ['python', 'nodejs', 'java']
        for _ in range(10)
    ])
    elapsed = time.time() - start
    
    assert len(results) == 30
    assert elapsed < 5.0  # Should be concurrent, not sequential
```

## Debugging Tests

### Verbose Output

```bash
# Show print statements
pytest tests/ -v -s

# Show local variables on failure
pytest tests/ -l

# Full traceback
pytest tests/ --tb=long
```

### Drop into Debugger

```python
def test_debug():
    result = function_to_debug()
    
    # Drop into pdb
    import pdb; pdb.set_trace()
    
    assert result == expected
```

### Pytest Plugins

```bash
# Install useful plugins
pip install pytest-xdist      # Parallel execution
pip install pytest-timeout    # Timeout for hanging tests
pip install pytest-mock       # Better mocking
pip install pytest-asyncio    # Better async testing

# Use plugins
pytest tests/ -n auto         # Run in parallel
pytest tests/ --timeout=10    # Timeout per test
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=bot
      
      - uses: codecov/codecov-action@v3
```

## Test Checklist

Before committing:
- [ ] All tests pass: `pytest tests/`
- [ ] Coverage is adequate: `pytest tests/ --cov=bot`
- [ ] No linting errors: `pylint bot/`
- [ ] Code is formatted: `black bot/`
- [ ] Type hints are correct: `mypy bot/`

## Common Issues

### Tests Hanging

```bash
# Run with timeout
pytest tests/ --timeout=30

# Or set in pytest.ini
[pytest]
timeout = 30
```

### Flaky Tests

```python
# Mark as flaky and retry
@pytest.mark.flaky(reruns=3)
def test_sometimes_fails():
    ...
```

### Database Conflicts

```python
# Use in-memory SQLite for tests
@pytest.fixture
async def test_db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Pytest Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)
