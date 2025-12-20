"""Custom exceptions for better error handling."""
from typing import Optional


class BotError(Exception):
    """Base exception for bot errors."""
    def __init__(self, message: str, user_message: Optional[str] = None):
        self.message = message
        self.user_message = user_message or message
        super().__init__(self.message)


class APIError(BotError):
    """Error related to external API calls."""
    def __init__(self, message: str, api_name: str = "Unknown", retryable: bool = True):
        self.api_name = api_name
        self.retryable = retryable
        user_message = f"Ошибка при обращении к {api_name}. Попробуйте позже."
        super().__init__(message, user_message)


class DatabaseError(BotError):
    """Error related to database operations."""
    def __init__(self, message: str, retryable: bool = True):
        self.retryable = retryable
        user_message = "Ошибка базы данных. Попробуйте позже."
        super().__init__(message, user_message)


class ValidationError(BotError):
    """Error related to input validation."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        user_message = f"Ошибка валидации: {message}"
        super().__init__(message, user_message)


class NotFoundError(BotError):
    """Error when resource is not found."""
    def __init__(self, message: str, resource_type: Optional[str] = None):
        self.resource_type = resource_type
        user_message = f"Не найдено: {message}"
        super().__init__(message, user_message)


class PermissionError(BotError):
    """Error related to permissions."""
    def __init__(self, message: str = "Недостаточно прав"):
        user_message = "У вас нет прав для выполнения этой операции."
        super().__init__(message, user_message)


class RateLimitError(BotError):
    """Error when rate limit is exceeded."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        self.retry_after = retry_after
        user_message = "Превышен лимит запросов. Подождите немного."
        if retry_after:
            user_message += f" Попробуйте через {retry_after} секунд."
        super().__init__(message, user_message)

