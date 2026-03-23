"""GCP Workflows standard library constants.

Canonical sets of callable stdlib functions, retry predicates/policies,
expression-context builtins, and the standard library namespace prefixes.

These constants power validation (e.g. "is this ``call:`` target a known
stdlib function?") and are re-exported from the package root for user
convenience.

Reference: https://cloud.google.com/workflows/docs/reference/stdlib/overview
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard library callable functions  (used in ``call:`` steps)
# ---------------------------------------------------------------------------
# Sorted by module, then function name within each module.

STDLIB_FUNCTIONS: frozenset[str] = frozenset(
    {
        # base64
        "base64.decode",
        "base64.encode",
        # events
        "events.await_callback",
        "events.create_callback_endpoint",
        # experimental.executions
        "experimental.executions.execution_error",
        "experimental.executions.map",
        "experimental.executions.run",
        # hash
        "hash.compute_checksum",
        "hash.compute_hmac",
        # http
        "http.delete",
        "http.get",
        "http.patch",
        "http.post",
        "http.put",
        "http.request",
        # json
        "json.decode",
        "json.encode",
        "json.encode_to_string",
        # list
        "list.concat",
        "list.prepend",
        # map
        "map.delete",
        "map.get",
        "map.merge",
        "map.merge_nested",
        # math
        "math.abs",
        "math.floor",
        "math.max",
        "math.min",
        # sys
        "sys.get_env",
        "sys.log",
        "sys.now",
        "sys.sleep",
        "sys.sleep_until",
        # text
        "text.decode",
        "text.encode",
        "text.find_all",
        "text.find_all_regex",
        "text.match_regex",
        "text.replace_all",
        "text.replace_all_regex",
        "text.split",
        "text.substring",
        "text.to_lower",
        "text.to_upper",
        "text.url_decode",
        "text.url_encode",
        "text.url_encode_plus",
        # time
        "time.format",
        "time.parse",
        # uuid
        "uuid.generate",
    }
)

# ---------------------------------------------------------------------------
# Retry predicates and policies  (used in retry ``predicate:`` fields)
# ---------------------------------------------------------------------------
# ``http.default_retry`` and ``http.default_retry_non_idempotent`` are
# *retry policies* (predicate + backoff combined).  The ``_predicate``
# variants are bare predicates.  ``retry.*`` entries are convenience
# predicates/backoff configs.

RETRY_PREDICATES: frozenset[str] = frozenset(
    {
        # http retry policies (predicate + backoff)
        "http.default_retry",
        "http.default_retry_non_idempotent",
        # http retry predicates (predicate only)
        "http.default_retry_predicate",
        "http.default_retry_predicate_non_idempotent",
        # retry module
        "retry.always",
        "retry.default_backoff",
        "retry.never",
    }
)

# ---------------------------------------------------------------------------
# Expression-context built-in functions
# ---------------------------------------------------------------------------
# These are bare function names that can be called inside ``${...}``
# expressions.  They are NOT namespaced (no dot prefix) and should not be
# treated as variable references during variable analysis.

EXPRESSION_BUILTINS: frozenset[str] = frozenset(
    {
        "bool",
        "double",
        "int",
        "keys",
        "len",
        "not",
        "string",
        "type",
    }
)

# ---------------------------------------------------------------------------
# Standard library module namespaces
# ---------------------------------------------------------------------------
# Top-level namespace prefixes for the stdlib.  Useful for quick checks
# like "does this call target start with a known stdlib namespace?".

STDLIB_NAMESPACES: frozenset[str] = frozenset(
    {
        "base64",
        "events",
        "experimental.executions",
        "hash",
        "http",
        "json",
        "list",
        "map",
        "math",
        "retry",
        "sys",
        "text",
        "time",
        "uuid",
    }
)

# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def is_stdlib_call(name: str) -> bool:
    """Return ``True`` if *name* is a known GCP Workflows stdlib function."""
    return name in STDLIB_FUNCTIONS


def is_retry_predicate(name: str) -> bool:
    """Return ``True`` if *name* is a known retry predicate or policy."""
    return name in RETRY_PREDICATES


def is_expression_builtin(name: str) -> bool:
    """Return ``True`` if *name* is an expression-context built-in function."""
    return name in EXPRESSION_BUILTINS


def is_stdlib_namespace(name: str) -> bool:
    """Return ``True`` if *name* is a known stdlib module namespace."""
    return name in STDLIB_NAMESPACES
