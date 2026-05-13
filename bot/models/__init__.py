"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Database models."""
from bot.models.user import User
from bot.models.subscription import Subscription
from bot.models.cve_record import CVERecord
from bot.models.notification import Notification
from bot.models.query_history import QueryHistory
from bot.models.favorite import Favorite
from bot.models.user_settings import UserSettings
from bot.models.admin import Access, BotMode
from bot.models.user_stats import UserStats

__all__ = ["User", "Subscription", "CVERecord", "Notification", "QueryHistory", "Favorite", "UserSettings", "Access", "BotMode", "UserStats"]
