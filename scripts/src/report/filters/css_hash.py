import hashlib


def css_hash(value, length=10):
    """
    Returns a short, CSS-safe hash of a string.
    Useful for unique, deterministic class/id names.
    """
    h = hashlib.sha256(value.encode('utf-8')).hexdigest()
    return h[:length]
