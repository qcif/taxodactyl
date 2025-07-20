"""Generic utility functions."""

import re
from pathlib import Path


def deduplicate(sequence, key=None):
    """Remove duplicates from a sequence while preserving order.

    If key() func is provided, uniqueness will be determined by key(element).
    If no key is provided, the element itself will be used to determine
    uniqueness.
    """
    if key:
        seen = set()
        return [
            item for item in sequence
            if key(item)
            and key(item) not in seen
            and not seen.add(key(item))
        ]
    return list(dict.fromkeys(sequence))


def serialize(obj):
    """Serialize an object to a JSON string."""
    if hasattr(obj, 'to_json'):
        return obj.to_json()
    if type(obj).__name__ == 'method':
        return f'method:{obj.__name__}'
    if isinstance(obj, Path):
        return f"Path({obj})"
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON"
                    " serializable")


def path_safe_str(value):
    """Return a path-safe version of a string."""
    return re.sub(r'[^\w\d\-\_\.]', '_', str(value))


def existing_path(path):
    """Check if a path exists and return a Path object."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path '{path.absolute()}' does not exist.")
    return path.absolute()
