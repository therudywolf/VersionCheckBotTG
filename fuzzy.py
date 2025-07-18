from typing import List, Tuple
try:
    from rapidfuzz import process, fuzz
    def suggest(q:str, choices:List[str], n:int=5)->List[Tuple[str,int]]:
        return process.extract(q, choices, scorer=fuzz.WRatio, limit=n)
except ImportError:
    import difflib
    def suggest(q:str, choices:List[str], n:int=5)->List[Tuple[str,int]]:
        ms = difflib.get_close_matches(q, choices, n=n, cutoff=0.6)
        return [(m,100) for m in ms]
