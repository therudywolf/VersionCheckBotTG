"""Robust parser for 'slug version' lists with messy separators."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_SEP = re.compile(r"[\s,;\n]+")

def parse(text: str) -> List[Tuple[str, Optional[str]]]:
    tokens = [t.strip() for t in _SEP.split(text) if t.strip()]
    result: list[tuple[str, Optional[str]]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        ver: Optional[str] = None
        # "python 3.12"
        if i + 1 < len(tokens) and tokens[i + 1][0].isdigit():
            ver = tokens[i + 1]
            i += 1
        else:
            # "python3.12"
            m = re.match(r"^([a-zA-Z][\w\-]*?)(\d[\w.\-]*)$", tok)
            if m:
                tok, ver = m.groups()
        result.append((tok.lower(), ver))
        i += 1

    # deduplicate while preserving order
    seen: set[tuple[str, Optional[str]]] = set()
    unique: list[tuple[str, Optional[str]]] = []
    for slug, ver in result:
        if (slug, ver) not in seen:
            seen.add((slug, ver))
            unique.append((slug, ver))
    return unique
