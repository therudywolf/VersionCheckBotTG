import re
from rapidfuzz import process

def parse_tokens(text: str, slugs: list[str]) -> list[tuple[str,str]]:
    """
    Разбивает строку на токены, возвращает список (slug, version).
    """
    tokens = re.split(r"[\n,;]+", text)
    results = []
    for t in tokens:
        tok = t.strip()
        if not tok:
            continue
        # Попытка через regex
        m = re.search(r"(?P<name>[A-Za-z0-9\-\s+.]+?)\s*(?:v|версия)?\s*(?P<version>[0-9]+(?:\.[0-9]+)*)", tok, re.IGNORECASE)
        if m:
            name = m.group('name').strip().lower().replace(' ', '-')
            version = m.group('version')
        else:
            name_guess, score = process.extractOne(tok, slugs)
            version_m = re.search(r"[0-9]+(?:\.[0-9]+)*", tok)
            version = version_m.group() if version_m else ''
            name = name_guess
        results.append((name, version))
    return results