import re
from typing import List, Optional, Tuple
_SPLIT = re.compile(r'[\s,;\n]+')
def parse(text: str) -> List[Tuple[str, Optional[str]]]:
    t = [x.strip() for x in _SPLIT.split(text) if x.strip()]
    out = []
    i = 0
    while i < len(t):
        token = t[i]
        ver = None
        if i+1<len(t) and t[i+1][0].isdigit():
            ver = t[i+1]; i+=1
        else:
            m = re.match(r'^([a-zA-Z][\w\-_]*?)(\d[\w.\-]*)$', token)
            if m:
                token, ver = m.groups()
        out.append((token.lower(), ver))
        i+=1
    return out
