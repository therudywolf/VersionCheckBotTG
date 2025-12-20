"""Parser for extracting product names and versions from text."""
import re
from typing import List, Tuple, Optional

_sep = re.compile(r'[\s,;\n]+')
_version_pattern = re.compile(r'^(\d+\.\d+(?:\.\d+)?(?:[-.]\w+)?)$', re.IGNORECASE)
_product_version_pattern = re.compile(r'^([a-zA-Z][\w\-]*?)(\d+[\w.\-]*)$', re.IGNORECASE)


def parse(text: str) -> List[Tuple[str, Optional[str]]]:
    """
    Parse text to extract product names and versions.
    
    Supports multiple formats:
    - "python 3.11"
    - "python3.11"
    - "nodejs 22, python 3.10"
    - "python; nodejs 22"
    - "python\nnodejs 22"
    
    Args:
        text: Input text containing product names and versions
        
    Returns:
        List of tuples (product_slug, version) where version can be None
    """
    if not text or not text.strip():
        return []
    
    toks = [t.strip() for t in _sep.split(text) if t.strip()]
    res = []
    i = 0
    
    while i < len(toks):
        tok = toks[i]
        ver = None
        
        # Check if next token is a version
        if i + 1 < len(toks):
            next_tok = toks[i + 1]
            if _version_pattern.match(next_tok) or next_tok[0].isdigit():
                ver = next_tok
                i += 1
        
        # Try to extract version from current token (e.g., "python3.11")
        if not ver:
            match = _product_version_pattern.match(tok)
            if match:
                tok, ver = match.groups()
        
        # Clean product name
        product_slug = _clean_product_name(tok)
        if product_slug:
            res.append((product_slug.lower(), ver.lower() if ver else None))
        
        i += 1
    
    # Remove duplicates while preserving order
    seen = set()
    uniq = []
    for s, v in res:
        if (s, v) not in seen:
            seen.add((s, v))
            uniq.append((s, v))
    
    return uniq


def _clean_product_name(name: str) -> str:
    """
    Clean and validate product name.
    
    Args:
        name: Raw product name
        
    Returns:
        Cleaned product name or empty string if invalid
    """
    if not name:
        return ""
    
    # Remove common prefixes/suffixes
    name = name.strip()
    name = re.sub(r'^@', '', name)  # Remove @ prefix
    name = re.sub(r'[^\w\-]', '', name)  # Keep only alphanumeric, underscore, hyphen
    
    # Minimum length check
    if len(name) < 2:
        return ""
    
    return name


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
    
    # Should start with letter and contain only alphanumeric, underscore, hyphen
    return bool(re.match(r'^[a-zA-Z][\w\-]*$', slug))


def validate_version(version: str) -> bool:
    """
    Validate version format.
    
    Args:
        version: Version string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not version:
        return False
    
    # Basic version pattern: digits, dots, hyphens, letters
    return bool(re.match(r'^[\d.]+[\w.\-]*$', version))
