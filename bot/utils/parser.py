"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Parser for extracting product names and versions from free-form text."""
from typing import List, Optional, Tuple


CLAUSE_SEPARATORS = {",", ";", "\n", "\r"}
TOKEN_SEPARATORS = set(" \t()[]{}\"'`")
VERSION_OPERATORS = set("<>=~^")
PRODUCT_VERSION_SEPARATORS = {":", "/", "\\"}

STOP_WORDS = {
    "check", "find", "show", "version", "versions", "release", "releases",
    "eol", "status", "please", "pls", "for", "of", "the", "and", "or",
    "проверь", "проверить", "найди", "покажи", "версия", "версии",
    "релиз", "релизы", "статус", "для", "по", "и", "или", "пожалуйста",
}

VERSION_HINT_WORDS = {
    "lts", "stable", "current", "latest", "security", "only", "jre", "jdk",
}

PRODUCT_ALIASES = {
    ".net": "dotnet",
    "net": "dotnet",
    "node": "nodejs",
    "node.js": "nodejs",
    "node-js": "nodejs",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "golang": "go",
    "k8s": "kubernetes",
    "kube": "kubernetes",
    "jdk": "java",
    "openjdk": "java",
}


def parse(text: str) -> List[Tuple[str, Optional[str]]]:
    """
    Parse a natural-language query into product/version pairs.

    The parser is intentionally heuristic: Telegram users usually type
    "node.js 22", "python>=3.11", "nginx/1.24", or short Russian phrases,
    not strict machine-readable expressions.
    """
    if not text or not text.strip():
        return []

    tokens = _tokenize(text)
    pairs: List[Tuple[str, Optional[str]]] = []
    pending_product: Optional[str] = None
    i = 0

    while i < len(tokens):
        token = tokens[i]
        lowered = token.lower()

        if token == "|":
            if pending_product:
                pairs.append((pending_product, None))
                pending_product = None
            i += 1
            continue

        if lowered in STOP_WORDS or lowered in VERSION_HINT_WORDS:
            i += 1
            continue

        if _is_version_token(token):
            if pending_product:
                pairs.append((pending_product, _normalize_version(token)))
                pending_product = None
            i += 1
            continue

        embedded = _split_embedded_version(token)
        if embedded:
            product, version = embedded
            if pending_product:
                pairs.append((pending_product, None))
                pending_product = None
            pairs.append((product, version))
            i += 1
            continue

        product = _clean_product_name(token)
        if not product:
            i += 1
            continue

        if pending_product:
            pairs.append((pending_product, None))

        version, next_index = _find_nearby_version(tokens, i + 1)
        if version:
            pairs.append((product, version))
            pending_product = None
            i = next_index
        else:
            pending_product = product
            i += 1

    if pending_product:
        pairs.append((pending_product, None))

    return _dedupe(pairs)


def _tokenize(text: str) -> List[str]:
    """Tokenize text while preserving version punctuation like dots and dashes."""
    tokens: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            tokens.append("".join(current))
            current.clear()

    for char in text:
        if char in CLAUSE_SEPARATORS:
            flush()
            tokens.append("|")
        elif char in TOKEN_SEPARATORS:
            flush()
        elif char in PRODUCT_VERSION_SEPARATORS or char in VERSION_OPERATORS:
            flush()
        else:
            current.append(char)

    flush()
    return tokens


def _find_nearby_version(tokens: List[str], start: int) -> Tuple[Optional[str], int]:
    """Find a version close to a product token without crossing another product."""
    i = start
    skipped = 0
    while i < len(tokens) and skipped < 4:
        token = tokens[i]
        lowered = token.lower()

        if token == "|":
            return None, start
        if lowered in STOP_WORDS or lowered in VERSION_HINT_WORDS:
            skipped += 1
            i += 1
            continue
        if _is_version_token(token):
            return _normalize_version(token), i + 1
        if _clean_product_name(token):
            return None, start

        skipped += 1
        i += 1

    return None, start


def _split_embedded_version(token: str) -> Optional[Tuple[str, str]]:
    """Split compact input like python3.11, php8.3, go1.22, or ruby-3.2."""
    cleaned = token.strip().strip(".,;")
    if not cleaned or _is_version_token(cleaned):
        return None

    first_digit = next((idx for idx, char in enumerate(cleaned) if char.isdigit()), -1)
    if first_digit <= 0:
        return None

    product_part = cleaned[:first_digit].rstrip("-_.")
    version_part = cleaned[first_digit:]
    product = _clean_product_name(product_part)
    version = _normalize_version(version_part)

    if not product or not validate_version(version):
        return None
    return product, version


def _clean_product_name(name: str) -> str:
    """Clean and normalize a product slug or common alias."""
    if not name:
        return ""

    value = name.strip().strip(".,;").lstrip("@").lower()
    if not value or value in STOP_WORDS or value in VERSION_HINT_WORDS:
        return ""

    allowed = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            allowed.append(char)

    cleaned = "".join(allowed).strip("-_.")
    if len(cleaned) < 2 or cleaned.isdigit():
        return ""

    alias_key = cleaned
    slug = PRODUCT_ALIASES.get(alias_key, cleaned.replace(".", ""))
    return PRODUCT_ALIASES.get(slug, slug)


def _is_version_token(token: str) -> bool:
    """Return True when token looks like a version rather than a product name."""
    version = _normalize_version(token)
    if not version or not any(char.isdigit() for char in version):
        return False

    if not version[0].isdigit():
        return False

    return all(
        char.isalnum() or char in {".", "-", "_", "+", "*"}
        for char in version
    )


def _normalize_version(version: str) -> str:
    """Normalize version text for matching against release cycles."""
    if not version:
        return ""

    value = version.strip().strip(".,;").lower()
    while value and value[0] in VERSION_OPERATORS:
        value = value[1:]

    if len(value) > 1 and value[0] == "v" and value[1].isdigit():
        value = value[1:]

    for suffix in (".x", "-x", "_x"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]

    return value.strip(".-_+")


def _dedupe(items: List[Tuple[str, Optional[str]]]) -> List[Tuple[str, Optional[str]]]:
    seen = set()
    result = []
    for product, version in items:
        key = (product, version)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def validate_product_slug(slug: str) -> bool:
    """
    Validate product slug format.

    Args:
        slug: Product slug to validate

    Returns:
        True if valid, False otherwise
    """
    if not slug or len(slug) < 2:
        return False

    value = slug.strip().lstrip("@")
    if not value or not value[0].isalpha():
        return False

    return all(char.isalnum() or char in {"_", "-"} for char in value)


def validate_version(version: str) -> bool:
    """
    Validate version format.

    Args:
        version: Version string to validate

    Returns:
        True if valid, False otherwise
    """
    return _is_version_token(version)
