from typing import List
try:
    from rapidfuzz import process, fuzz
except ImportError:  # fallback to difflib
    import difflib

    def find_best(query: str, choices: List[str], limit: int = 3):
        matches = difflib.get_close_matches(query, choices, n=limit, cutoff=0.6)
        return [(m, 100) for m in matches]

else:
    def find_best(query: str, choices: List[str], limit: int = 3):
        return process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)
