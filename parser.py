import re
from typing import List, Optional, Tuple

_TOKEN_SPLIT = re.compile(r'[\s,;\n]+')

def parse_query(raw: str) -> List[Tuple[str, Optional[str]]]:
    """Return list of (product_slug, version|None)."""
    tokens = [t.strip() for t in _TOKEN_SPLIT.split(raw) if t.strip()]
    out = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        ver = None
        if i + 1 < len(tokens) and tokens[i + 1][0].isdigit():
            ver = tokens[i + 1]
            i += 1
        else:
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9\-_]*)(\d[\w\.-]*)$', tok)
            if m:
                tok, ver = m.groups()
        out.append((tok.lower(), ver))
        i += 1
    return out
