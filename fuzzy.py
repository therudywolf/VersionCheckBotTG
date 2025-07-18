try:
    from rapidfuzz import process, fuzz
    def suggest(q, choices, n=5):
        return process.extract(q, choices, scorer=fuzz.WRatio, limit=n)
except ImportError:
    import difflib
    def suggest(q, choices, n=5):
        return [(m,100) for m in difflib.get_close_matches(q, choices,n=n,cutoff=0.6)]
