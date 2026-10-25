"""Extensible registry for multiline lexer delimiters."""
from __future__ import annotations

from collections.abc import Mapping


# The spelling is kept as requested for API compatibility.
MULTLINE: dict[str, str] = {
    '"""': '"""',
    "'''": "'''",
}


def add_multline(opening: str, closing: str) -> None:
    """Register or replace a multiline opening/closing delimiter pair."""
    if not isinstance(opening, str) or not opening:
        raise ValueError("El delimitador de apertura no puede estar vacío.")
    if not isinstance(closing, str) or not closing:
        raise ValueError("El delimitador de cierre no puede estar vacío.")
    MULTLINE[opening] = closing


def remove_multline(opening: str) -> str | None:
    """Remove a multiline delimiter pair and return its closing delimiter."""
    return MULTLINE.pop(opening, None)


def list_multline() -> dict[str, str]:
    """Return a detached copy of the registered multiline delimiters."""
    return dict(MULTLINE)


def get_multline() -> Mapping[str, str]:
    """Return the live registry for lexer internals."""
    return MULTLINE


__all__ = [
    "MULTLINE",
    "add_multline",
    "get_multline",
    "list_multline",
    "remove_multline",
]
