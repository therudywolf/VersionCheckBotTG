"""Fuzzy string matching for product name suggestions."""
try:
    from rapidfuzz import process, fuzz
    
    def sugg(query: str, choices: list, n: int = 5) -> list:
        """
        Find best matches using rapidfuzz.
        
        Args:
            query: Search query
            choices: List of choices to search in
            n: Maximum number of results
            
        Returns:
            List of best matching choices
        """
        return [m for m, _ in process.extract(query, choices, scorer=fuzz.WRatio, limit=n)]
except ImportError:
    import difflib
    
    def sugg(query: str, choices: list, n: int = 5) -> list:
        """
        Find best matches using difflib (fallback).
        
        Args:
            query: Search query
            choices: List of choices to search in
            n: Maximum number of results
            
        Returns:
            List of best matching choices
        """
        return difflib.get_close_matches(query, choices, n=n, cutoff=0.6)

