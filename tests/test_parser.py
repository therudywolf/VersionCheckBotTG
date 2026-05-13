"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Tests for parser utility."""
import pytest
from bot.utils.parser import parse, validate_product_slug


class TestParser:
    """Test parser functions."""
    
    def test_parse_single_product(self):
        """Test parsing single product."""
        result = parse("python")
        assert len(result) == 1
        assert result[0] == ("python", None)
    
    def test_parse_product_with_version(self):
        """Test parsing product with version."""
        result = parse("python 3.11")
        assert len(result) == 1
        assert result[0] == ("python", "3.11")
    
    def test_parse_multiple_products(self):
        """Test parsing multiple products."""
        result = parse("python 3.11, nodejs 22")
        assert len(result) == 2
        assert result[0] == ("python", "3.11")
        assert result[1] == ("nodejs", "22")
    
    def test_parse_with_semicolon(self):
        """Test parsing with semicolon separator."""
        result = parse("python; nodejs")
        assert len(result) == 2
    
    def test_parse_with_newlines(self):
        """Test parsing with newline separator."""
        result = parse("python\nnodejs\njava")
        assert len(result) == 3

    def test_parse_free_form_query(self):
        """Test parsing natural-language query."""
        result = parse("проверь python>=3.11 и node.js 22.x")
        assert result == [("python", "3.11"), ("nodejs", "22")]

    def test_parse_product_version_separators(self):
        """Test parsing common product/version separators."""
        assert parse("nginx/1.24") == [("nginx", "1.24")]
        assert parse("ruby-3.2") == [("ruby", "3.2")]

    def test_parse_common_aliases(self):
        """Test common product aliases."""
        assert parse("postgres 16") == [("postgresql", "16")]
        assert parse("golang 1.22.5") == [("go", "1.22.5")]
        assert parse("k8s v1.30") == [("kubernetes", "1.30")]
    
    def test_validate_product_slug(self):
        """Test product slug validation."""
        assert validate_product_slug("python") == True
        assert validate_product_slug("node-js") == True
        assert validate_product_slug("") == False
        assert validate_product_slug("123") == False



