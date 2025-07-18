import re
from typing import List, Tuple, Optional

_SPLIT = re.compile(r'[\s,\n]+')

def parse_items(text: str) -> List[Tuple[str, Optional[str]]]:
    tokens = [t.strip() for t in _SPLIT.split(text) if t.strip()]
    res = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        ver = None
        if i + 1 < len(tokens) and re.match(r'^\d', tokens[i + 1]):
            ver = tokens[i + 1]
            i += 1
        else:
            m = re.match(r'^([a-zA-Z\-_]+)(\d[\d.\-a-zA-Z]*)$', tok)
            if m:
                tok, ver = m.groups()
        res.append((tok.lower(), ver))
        i += 1
    return res
