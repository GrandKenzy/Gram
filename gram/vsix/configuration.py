"""Fluent language-configuration builder for VS Code extensions."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from gram import config
from gram.core.lexer.tokens import Token
from gram.vsix.extract import SyntaxMetadata


class LanguageConfiguration:
    """Build a VS Code language configuration, starting from Gram's known tokens."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    @property
    def line_comment_token(self) -> str | None:
        """Return the explicit line-comment token, if one was configured."""
        return self._values.get("comments", {}).get("lineComment")

    def LineComment(self, token: str) -> LanguageConfiguration:
        self._values.setdefault("comments", {})["lineComment"] = token
        return self

    def BlockComment(self, start: str, end: str) -> LanguageConfiguration:
        self._values.setdefault("comments", {})["blockComment"] = [start, end]
        return self

    def Brackets(self, *pairs: Sequence[str] | str) -> LanguageConfiguration:
        normalized = self._normalize_pairs(pairs)
        self._values["brackets"] = normalized
        return self

    def AutoClosingPairs(
        self,
        *pairs: Sequence[str] | dict[str, Any],
    ) -> LanguageConfiguration:
        normalized: list[dict[str, Any]] = []
        for pair in pairs:
            if isinstance(pair, dict):
                normalized.append(dict(pair))
            else:
                values = list(pair)
                if len(values) != 2:
                    raise ValueError("Cada par de autocierre debe tener exactamente dos elementos.")
                normalized.append({"open": values[0], "close": values[1]})
        self._values["autoClosingPairs"] = normalized
        return self

    def SurroundingPairs(self, *pairs: Sequence[str] | str) -> LanguageConfiguration:
        self._values["surroundingPairs"] = self._normalize_pairs(pairs)
        return self

    def IndentationRules(
        self,
        increase: str | None = None,
        decrease: str | None = None,
    ) -> LanguageConfiguration:
        rules: dict[str, str] = {}
        if increase is not None:
            rules["increaseIndentPattern"] = increase
        if decrease is not None:
            rules["decreaseIndentPattern"] = decrease
        self._values["indentationRules"] = rules
        return self

    @staticmethod
    def _normalize_pairs(pairs: Sequence[Sequence[str] | str]) -> list[list[str]]:
        if len(pairs) == 1 and not isinstance(pairs[0], str):
            first = list(pairs[0])
            if len(first) == 2 and all(isinstance(item, str) for item in first):
                pairs = [first]
            else:
                pairs = first

        normalized: list[list[str]] = []
        for pair in pairs:
            if isinstance(pair, str) or len(pair) != 2:
                raise ValueError("Cada par debe contener exactamente dos cadenas.")
            opening, closing = pair
            if not isinstance(opening, str) or not isinstance(closing, str):
                raise ValueError("Cada par debe contener exactamente dos cadenas.")
            normalized.append([opening, closing])
        return normalized

    def build(self, metadata: SyntaxMetadata | None = None) -> dict[str, Any]:
        """Return a fresh configuration with defaults inferred from Gram's token catalog."""
        token_names = set(metadata.token_types) if metadata is not None else {token.name for token in Token}
        pairs = [
            pair
            for left, right, pair in (
                ("LBRACE", "RBRACE", ["{", "}"]),
                ("LBRACKET", "RBRACKET", ["[", "]"]),
                ("LPAREN", "RPAREN", ["(", ")"]),
            )
            if left in token_names and right in token_names
        ]
        base: dict[str, Any] = {
            "comments": {"lineComment": config.LEXER_COMMENT_TOKEN},
            "brackets": pairs,
            "autoClosingPairs": [
                {"open": opening, "close": closing}
                for opening, closing in pairs
            ],
            "surroundingPairs": [list(pair) for pair in pairs],
        }

        if "STRING" in token_names:
            base["autoClosingPairs"].extend([
                {"open": '"', "close": '"', "notIn": ["string"]},
                {"open": "'", "close": "'", "notIn": ["string", "comment"]},
            ])
            base["surroundingPairs"].extend([['"', '"'], ["'", "'"]])

        for key, value in self._values.items():
            if key == "comments":
                base.setdefault(key, {}).update(value)
            else:
                base[key] = value
        return base


__all__ = ["LanguageConfiguration"]
