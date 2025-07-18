import re
from typing import List, Tuple, Optional

_SEP = re.compile(r'[\s,;\n]+')

def parse(text:str) -> List[Tuple[str, Optional[str]]]:
    raw = [t.strip() for t in _SEP.split(text) if t.strip()]
    out = []
    i=0
    while i < len(raw):
        tok = raw[i]
        ver = None
        if i+1 < len(raw) and raw[i+1][0].isdigit():
            ver = raw[i+1]; i+=1
        else:
            m = re.match(r'^([a-zA-Z][\w\-]*?)(\d[\w.\-]*)$', tok)
            if m: tok, ver = m.groups()
        out.append((tok.lower(), ver))
        i+=1
    # deduplicate preserving order
    seen=set(); result=[]
    for s,v in out:
        key=(s,v)
        if key not in seen:
            seen.add(key); result.append((s,v))
    return result
