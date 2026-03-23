"""Retry and backoff configuration for Try steps.

These are builder-layer classes that produce raw dicts at build time.
No Pydantic models are used.

Usage::

    Retry(
        "http.default_retry",
        max_retries=3,
        backoff=Backoff(initial_delay=1, max_delay=60, multiplier=2),
    )

    # String predicate shorthand:
    Retry("http.default_retry", max_retries=5)

    # Expression predicate:
    Retry(expr("e.code == 429"), max_retries=3)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

__all__ = [
    "Retry",
    "Backoff",
]


class Backoff:
    """Exponential backoff configuration for retries.

    Args:
        initial_delay: Initial delay in seconds before the first retry.
        max_delay: Maximum delay in seconds between retries.
        multiplier: Multiplier applied to the delay after each retry.
    """

    def __init__(
        self,
        *,
        initial_delay: Union[int, float],
        max_delay: Union[int, float],
        multiplier: Union[int, float],
    ) -> None:
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier

    def _to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for YAML serialization."""
        return {
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "multiplier": self.multiplier,
        }


class Retry:
    """Retry configuration for Try steps.

    Args:
        predicate: Retry predicate — a string name (e.g.
            ``"http.default_retry"``) or an expression.
        max_retries: Maximum number of retry attempts.
        backoff: Optional ``Backoff`` instance for exponential backoff.
    """

    def __init__(
        self,
        predicate: Any,
        *,
        max_retries: int,
        backoff: Optional[Backoff] = None,
    ) -> None:
        if not predicate:
            raise ValueError("Retry requires a predicate")
        self.predicate = predicate
        self.max_retries = max_retries
        self.backoff = backoff

    def _to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for YAML serialization."""
        d: Dict[str, Any] = {
            "predicate": self.predicate,
            "max_retries": self.max_retries,
        }
        if self.backoff is not None:
            d["backoff"] = self.backoff._to_dict()
        return d
