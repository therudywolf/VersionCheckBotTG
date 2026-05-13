"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Fuzzy string matching for product name suggestions."""
from typing import List
try:
    from rapidfuzz import process, fuzz
    
    def sugg(query: str, choices: List[str], n: int = 5) -> List[str]:
        """
        Find best matches using rapidfuzz.
        
        Args:
            query: Search query
            choices: List of choices to search in
            n: Maximum number of results
            
        Returns:
            List of best matching choices
        """
        if not choices:
            return []
        return [m for m, _, _ in process.extract(query, choices, scorer=fuzz.WRatio, limit=n)]
except ImportError:
    import difflib
    
    def sugg(query: str, choices: List[str], n: int = 5) -> List[str]:
        """
        Find best matches using difflib (fallback).
        
        Args:
            query: Search query
            choices: List of choices to search in
            n: Maximum number of results
            
        Returns:
            List of best matching choices
        """
        return difflib.get_close_matches(query, choices, n=n, cutoff=0.6)
