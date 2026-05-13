"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""User-friendly error messages."""
from typing import Optional


class ErrorMessages:
    """Centralized error messages for users."""
    
    # General errors
    GENERIC_ERROR = "Произошла ошибка при обработке запроса. Попробуйте позже."
    RATE_LIMIT_EXCEEDED = "Превышен лимит запросов. Подождите немного."
    INVALID_INPUT = "Неверный формат входных данных."
    NOT_FOUND = "Данные не найдены."
    
    # Product errors
    PRODUCT_NOT_FOUND = "Продукт '{product}' не найден."
    PRODUCT_INVALID = "Неверный формат названия продукта: {product}"
    VERSION_INVALID = "Неверный формат версии: {version}"
    
    # Subscription errors
    SUBSCRIPTION_EXISTS = "Вы уже подписаны на {product}"
    SUBSCRIPTION_NOT_FOUND = "Подписка не найдена."
    SUBSCRIPTION_ALREADY_CANCELLED = "Подписка уже отменена."
    
    # CVE errors
    CVE_NOT_FOUND = "CVE для {product} не найдены."
    CVE_API_ERROR = "Ошибка при получении данных CVE. Попробуйте позже."
    
    # File errors
    FILE_TOO_LARGE = "Файл слишком большой. Максимальный размер: {max_size}MB"
    FILE_INVALID_TYPE = "Неподдерживаемый тип файла. Нужен .txt файл."
    FILE_EMPTY = "Файл пуст."
    FILE_READ_ERROR = "Ошибка при чтении файла."
    
    # Database errors
    DB_ERROR = "Ошибка базы данных. Попробуйте позже."
    
    # Permission errors
    ADMIN_ONLY = "Эта команда доступна только администраторам."
    PERMISSION_DENIED = "У вас нет прав для выполнения этой операции."
    
    @staticmethod
    def format(message: str, **kwargs) -> str:
        """
        Format error message with parameters.
        
        Args:
            message: Error message template
            **kwargs: Parameters to format
            
        Returns:
            Formatted error message
        """
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
