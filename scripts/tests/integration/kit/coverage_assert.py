"""Assertion walker for ``db_coverage.json`` fixtures.

The walker compares an ``expected`` document (a literal JSON fixture captured
from a verified run) against the ``actual`` document produced by the current
run and enforces four tiered rules:

1. Structural key-set match at the top level (``coverage``, ``ncbi_urls``),
   for the ``coverage`` category layer (``candidate``, ``toi``, ``pmi``), and
   for the analysis-target layer immediately below each category and below
   ``ncbi_urls`` (species keys).
2. Below the analysis-target layer (e.g. ``related``, ``country``, ``blast``,
   ``taxonomy``), keys are allowed to drift — recurse with type-only rules.
3. Leaf values must share the same type as the expected value.
4. Non-null propagation: if the expected leaf is truthy, the actual leaf must
   be truthy too.

Two entry points:

- :func:`assert_matches` — raise ``AssertionError`` on any tier violation.
- :func:`semantic_diff` — return a structured list of :class:`Change`
  records classified as ``WOULD_FAIL`` (tier violation) or ``TOLERATED``
  (value drift within the same type, or a key drift below the analysis
  layer).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

TOP_LEVEL_KEYS = {"coverage", "ncbi_urls"}


class ChangeKind(Enum):
    WOULD_FAIL = "WOULD_FAIL"
    TOLERATED = "TOLERATED"


@dataclass
class Change:
    path: str
    kind: ChangeKind
    reason: str
    expected: Any = field(default=None)
    actual: Any = field(default=None)


def assert_matches(expected: dict, actual: dict) -> None:
    """Raise ``AssertionError`` if ``actual`` violates any tiered rule."""
    changes = semantic_diff(expected, actual)
    failures = [c for c in changes if c.kind is ChangeKind.WOULD_FAIL]
    if not failures:
        return
    lines = [
        f"  {c.path}: {c.reason}"
        for c in failures
    ]
    raise AssertionError(
        "db_coverage.json does not match expected fixture:\n"
        + "\n".join(lines)
    )


def semantic_diff(expected: dict, actual: dict) -> list[Change]:
    """Return a structured diff between ``expected`` and ``actual``."""
    changes: list[Change] = []
    _walk_root(expected, actual, "$", changes)
    return changes


def _walk_root(exp: Any, act: Any, path: str, changes: list[Change]) -> None:
    if not _both_dicts(exp, act, path, changes):
        return
    _check_structural_keys(exp, act, path, changes)
    if "coverage" in exp and "coverage" in act:
        _walk_coverage(
            exp["coverage"],
            act["coverage"],
            f"{path}.coverage",
            changes,
        )
    if "ncbi_urls" in exp and "ncbi_urls" in act:
        _walk_analysis_target_map(
            exp["ncbi_urls"],
            act["ncbi_urls"],
            f"{path}.ncbi_urls",
            changes,
        )


def _walk_coverage(
    exp: Any,
    act: Any,
    path: str,
    changes: list[Change],
) -> None:
    """Structural key-set match on the category layer (candidate/toi/pmi)."""
    if not _both_dicts(exp, act, path, changes):
        return
    _check_structural_keys(exp, act, path, changes)
    for cat in set(exp) & set(act):
        _walk_analysis_target_map(
            exp[cat],
            act[cat],
            f"{path}.{cat}",
            changes,
        )


def _walk_analysis_target_map(
    exp: Any,
    act: Any,
    path: str,
    changes: list[Change],
) -> None:
    """Structural key-set match on the analysis-target layer (species keys).

    Below this layer, recurse with type-only rules — sub-object keys may
    differ from the fixture (tolerated) so long as the value types match.
    """
    if not _both_dicts(exp, act, path, changes):
        return
    _check_structural_keys(exp, act, path, changes)
    for key in set(exp) & set(act):
        _walk_typed(exp[key], act[key], _join(path, key), changes)


def _walk_typed(
    exp: Any,
    act: Any,
    path: str,
    changes: list[Change],
) -> None:
    """Recurse below the analysis layer with type-only, key-tolerant rules."""
    if isinstance(exp, dict):
        if not isinstance(act, dict):
            changes.append(Change(
                path,
                ChangeKind.WOULD_FAIL,
                f"type mismatch: expected dict, got {_typename(act)}",
                expected=exp,
                actual=act,
            ))
            return
        exp_keys = set(exp)
        act_keys = set(act)
        for k in sorted(exp_keys - act_keys):
            changes.append(Change(
                _join(path, k),
                ChangeKind.TOLERATED,
                "expected key missing (tolerated below analysis layer)",
                expected=exp[k],
            ))
        for k in sorted(act_keys - exp_keys):
            changes.append(Change(
                _join(path, k),
                ChangeKind.TOLERATED,
                "extra key (tolerated below analysis layer)",
                actual=act[k],
            ))
        for k in exp_keys & act_keys:
            _walk_typed(exp[k], act[k], _join(path, k), changes)
        return

    _check_leaf(exp, act, path, changes)


def _check_leaf(
    exp: Any,
    act: Any,
    path: str,
    changes: list[Change],
) -> None:
    # Non-null propagation: a truthy expected must not become falsy.
    if exp and not act:
        changes.append(Change(
            path,
            ChangeKind.WOULD_FAIL,
            (
                f"non-null propagation: expected truthy {exp!r},"
                f" got {act!r}"
            ),
            expected=exp,
            actual=act,
        ))
        return

    if not _same_type(exp, act):
        changes.append(Change(
            path,
            ChangeKind.WOULD_FAIL,
            f"type mismatch: expected {_typename(exp)}, got {_typename(act)}",
            expected=exp,
            actual=act,
        ))
        return

    if exp != act:
        changes.append(Change(
            path,
            ChangeKind.TOLERATED,
            f"value drift: {exp!r} -> {act!r}",
            expected=exp,
            actual=act,
        ))


def _check_structural_keys(
    exp: dict,
    act: dict,
    path: str,
    changes: list[Change],
) -> None:
    missing = set(exp) - set(act)
    extra = set(act) - set(exp)
    for k in sorted(missing):
        changes.append(Change(
            _join(path, k),
            ChangeKind.WOULD_FAIL,
            "missing required key",
            expected=exp[k],
        ))
    for k in sorted(extra):
        changes.append(Change(
            _join(path, k),
            ChangeKind.WOULD_FAIL,
            "unexpected extra key",
            actual=act[k],
        ))


def _both_dicts(
    exp: Any,
    act: Any,
    path: str,
    changes: list[Change],
) -> bool:
    if isinstance(exp, dict) and isinstance(act, dict):
        return True
    changes.append(Change(
        path,
        ChangeKind.WOULD_FAIL,
        (
            f"type mismatch: expected {_typename(exp)},"
            f" got {_typename(act)}"
        ),
        expected=exp,
        actual=act,
    ))
    return False


def _same_type(a: Any, b: Any) -> bool:
    # Treat bool as distinct from int even though ``bool`` subclasses ``int``.
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool)
    if a is None or b is None:
        return a is None and b is None
    return type(a) is type(b)


def _typename(v: Any) -> str:
    if v is None:
        return "null"
    return type(v).__name__


def _join(path: str, key: Any) -> str:
    if isinstance(key, str):
        return f"{path}[{key!r}]"
    return f"{path}[{key}]"
