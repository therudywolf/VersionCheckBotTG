try:
    from rapidfuzz import process,fuzz
    def sugg(q,choices,n=5):
        return [m for m,_ in process.extract(q,choices,scorer=fuzz.WRatio,limit=n)]
except ImportError:
    import difflib
    def sugg(q,choices,n=5):
        return difflib.get_close_matches(q,choices,n=n,cutoff=0.6)
