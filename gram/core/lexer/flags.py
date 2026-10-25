"""Bit flags attached to lexical tokens."""
from __future__ import annotations

from enum import IntFlag


class TokenFlags(IntFlag):
    NONE = 0
    SIMPLE_QUOTE = 1 << 0
    CHAR = 1 << 1


NONE = TokenFlags.NONE
SIMPLE_QUOTE = TokenFlags.SIMPLE_QUOTE
CHAR = TokenFlags.CHAR

__all__ = ["CHAR", "NONE", "SIMPLE_QUOTE", "TokenFlags"]
