"""Slug suggestions (RapidFuzz if available, difflib fallback)."""
from typing import List

try:
    from rapidfuzz import fuzz, process  # type: ignore

    def suggest(query: str, choices: List[str], limit: int = 5) -> List[str]:
        return [m for m, _ in process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)]

except ModuleNotFoundError:
    import difflib

    def suggest(query: str, choices: List[str], limit: int = 5) -> List[str]:
        return difflib.get_close_matches(query, choices, n=limit, cutoff=0.6)
