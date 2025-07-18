import re
from typing import List, Tuple, Optional
_sep=re.compile(r'[\s,;\n]+')
def parse(text:str)->List[Tuple[str,Optional[str]]]:
    toks=[t.strip() for t in _sep.split(text) if t.strip()]
    out=[];i=0
    while i<len(toks):
        tok=toks[i]; ver=None
        if i+1<len(toks) and toks[i+1][0].isdigit():
            ver=toks[i+1]; i+=1
        else:
            m=re.match(r'^([a-zA-Z][\w\-]*?)(\d[\w.\-]*)$', tok)
            if m: tok,ver=m.groups()
        out.append((tok.lower(), ver)); i+=1
    seen=set(); uniq=[]
    for s,v in out:
        if (s,v) not in seen:
            seen.add((s,v)); uniq.append((s,v))
    return uniq
