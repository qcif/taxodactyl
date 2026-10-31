"""Validation for BLAST retrieval and context selection settings."""

import math


def positive_hit_cap(value):
    """Accept positive integers without truncating fractional input."""
    try:
        result = int(str(value))
    except (ValueError, TypeError):
        raise ValueError("blast_max_target_seqs must be an integer >= 1") from None
    if result < 1:
        raise ValueError("blast_max_target_seqs must be an integer >= 1")
    return result


def context_identity(value):
    """Accept a finite identity fraction, including both endpoints."""
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError("blast_context_min_identity must be a number in [0, 1]") from None
    if isinstance(value, bool) or not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError("blast_context_min_identity must be a finite number in [0, 1]")
    return result
