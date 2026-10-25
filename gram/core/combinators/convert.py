"""Logical identifier-to-token conversion combinator."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import CustomToken, Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Convert(Combinator):
    """Convert an exact identifier locally or register a future conversion."""

    def __init__(
        self,
        name: str,
        target: Token | CustomToken | str,
        *,
        scope: bool = False,
    ) -> None:
        super().__init__()
        if not isinstance(name, str) or not name:
            errors.GrammarError(
                "InvalidConvertName",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                "Convert requiere un nombre de identificador no vacío.",
                "Pase el nombre exacto del IDENT que desea convertir.",
            ).raise_error()

        if isinstance(target, str):
            resolved = Token.from_string(target)
            if resolved is None:
                errors.GrammarError(
                    "InvalidConvertTarget",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"No se pudo resolver el token destino {target!r}.",
                    "Use un miembro de Token, CustomToken o un nombre válido de Token.",
                ).raise_error()
            target = resolved
        elif not isinstance(target, (Token, CustomToken)):
            errors.GrammarError(
                "InvalidConvertTarget",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                "Convert requiere un token destino válido.",
                "Use Token.X, CustomToken(...) o el nombre de un Token.",
            ).raise_error()

        self.name = name
        self.target = target
        self.scope = bool(scope)

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        parser = analyzer.parser
        if self.scope:
            try:
                parser.register_conversion(self.name, self.target)
            except ValueError as exc:
                analyzer.report_error(
                    errors.GrammarError(
                        "ConversionConflict",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        str(exc),
                        "Use una conversión distinta o elimine la definición anterior.",
                    ),
                    pos=parser.pos,
                )
                return None

        current = parser.peek()
        if current is None:
            return [] if self.scope else None

        if current.token == Token.IDENT and str(current.value) == self.name:
            converted = copy.copy(current)
            converted.token = self.target
            parser.replace_token_at(parser.pos, converted)

        return []

    def __repr__(self) -> str:
        target = getattr(self.target, "name", str(self.target))
        return f"Convert({self.name!r}, {target!r}, scope={self.scope!r})"


__all__ = ["Convert"]
