# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-05-12

### Changed
- Re-license the project from MIT to GNU Affero General Public License v3.0.
- Add repository hygiene notes for secrets, local state, and generated files.

### Fixed
- Fix `rapidfuzz.process.extract()` tuple unpacking (3-tuple, not 2-tuple)
- Fix `await` on synchronous `_save_to_disk()` in CVE service
- Fix `signal.SIGTERM` crash on Windows
- Fix double shutdown (remove explicit call, keep only `post_shutdown` callback)
- Fix raw SQL string in health check (`text("SELECT 1")` for SQLAlchemy 2.0)
- Fix decorator order: `@error_handler` is now outermost on all handlers
- Fix callback data parsing: use `:` separator so product slugs with `_` work correctly
- Fix `admin_cache_clear`: now clears actual global caches instead of empty `TTLCache()`
- Fix `admin_broadcast`: skip "broadcast" keyword from message text
- Fix `compare_command`: use `reply_markdown` instead of `reply_text`
- Fix CVE scheduler notification check to be per-user (was blocking other subscribers)
- Fix `monitoring_service.subscribe()`: resolve slug before product existence check
- Fix `rate_limiter`: initialize from config values instead of hardcoded defaults
- Fix `SUBSCRIPTION_EXISTS` error message template (condition was always `True`)
- Fix `subscriptions_command`: handle `callback_query.message` for pagination

### Added
- Implement all admin sub-commands: `mode`, `access`, `grant`, `revoke`, `make_admin`, `remove_admin`, `backup`
- Implement `/alerts` command with notification settings toggle UI
- Implement `/favorites` command with add/remove/list and inline keyboard
- Implement `/history` command showing query history with timestamps
- Add `VersionService.shared()` singleton to prevent aiohttp session leaks
- Add consistent `@rate_limit_handler` and `@access_required` to `messages.py` and `inline.py`
- Add graceful scheduler shutdown via `asyncio.Event`

### Removed
- Remove all `debug_log` pollution and `#region` markers
- Remove duplicate imports in `version_service.py`
- Remove redundant `validate_config()` function

## [2.0.0] - 2025-01-15

### Added
- Full architecture refactor to modular structure
- Subscription system with automatic status change notifications
- NVD API integration for CVE search and monitoring
- `/history` command for query history
- `/stats` command for admin statistics
- `/admin` command with sub-commands
- `/export` and `/import` for subscription management
- `/compare` for side-by-side version comparison
- Rate limiting (per-user, per-minute and per-hour)
- Persistent TTL cache with disk storage
- Retry logic with exponential backoff for API requests
- Circuit breaker for external API fault tolerance
- Inline keyboards for quick actions
- SQLite database with SQLAlchemy ORM and Alembic migrations
- Background scheduler for automatic subscription and CVE checks
- Improved parser supporting multiple version formats
- Fuzzy matching for product name suggestions
- Structured logging with file rotation
- Docker and Docker Compose support
- Access control (open/restricted modes, admin panel)

### Changed
- Modular project structure (`handlers/`, `services/`, `models/`, `utils/`)
- Optimized API requests with connection pooling
- Improved message formatting

## [1.0.0] - 2024-10-01

### Added
- Basic version checks via endoflife.date API
- Inline mode for use in any chat
- `.txt` file processing
- `/start`, `/check`, `/help` commands
- Docker support

[2.1.0]: https://github.com/therudywolf/VersionCheckBotTG/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/therudywolf/VersionCheckBotTG/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/therudywolf/VersionCheckBotTG/releases/tag/v1.0.0
