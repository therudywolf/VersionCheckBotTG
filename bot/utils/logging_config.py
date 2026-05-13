"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Logging configuration with structured logging and rotation."""
import logging
import logging.handlers
import sys
import uuid
from pathlib import Path
from typing import Optional
from config import settings


class ContextFilter(logging.Filter):
    """Filter to add context to log records."""
    
    def filter(self, record):
        """Add correlation ID if not present."""
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = getattr(record, 'correlation_id', str(uuid.uuid4())[:8])
        return True


def setup_logging():
    """Setup logging configuration with structured logging and rotation."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    
    # Set log level from config
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add context filter
    context_filter = ContextFilter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=logs_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - "
        "%(pathname)s:%(lineno)d - %(funcName)s - %(message)s",
        date_format
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (only errors and above)
    error_handler = logging.handlers.RotatingFileHandler(
        filename=logs_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return root_logger


def get_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:8]


def log_with_context(logger: logging.Logger, level: int, message: str, 
                     correlation_id: Optional[str] = None, **kwargs):
    """
    Log message with context.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        correlation_id: Optional correlation ID
        **kwargs: Additional context fields
    """
    extra = kwargs.copy()
    if correlation_id:
        extra['correlation_id'] = correlation_id
    logger.log(level, message, extra=extra)
