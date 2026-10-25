"""Strict zero-width parser expectations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer import Token

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


ExpectedKind = Literal["newline", "count", "ncount", "indent"]


class Expected(Combinator):
    """Assert a strict property of the remaining token stream."""

    def __init__(self, kind: ExpectedKind | str, value: int | None = None) -> None:
        super().__init__()
        normalized = str(kind).lower()
        if normalized not in {"newline", "count", "ncount", "indent"}:
            errors.GrammarError(
                "InvalidExpectedKind",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"Tipo de Expected no soportado: {kind!r}.",
                "Use newline, count, ncount o indent.",
            ).raise_error()
        if normalized == "newline" and value is not None:
            errors.GrammarError(
                "InvalidExpectedValue",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                "Expected('newline') no recibe un valor numérico.",
                "Use Expected.newline().",
            ).raise_error()
        if normalized != "newline" and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            errors.GrammarError(
                "InvalidExpectedValue",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"Expected({normalized!r}) requiere un entero no negativo.",
                "Proporcione un valor válido para count, ncount o indent.",
            ).raise_error()
        self.kind: ExpectedKind = normalized  # type: ignore[assignment]
        self.value = value

    @classmethod
    def newline(cls) -> Expected:
        return cls("newline")

    @classmethod
    def count(cls, value: int) -> Expected:
        return cls("count", value)

    @classmethod
    def ncount(cls, value: int) -> Expected:
        return cls("ncount", value)

    @classmethod
    def indent(cls, value: int) -> Expected:
        return cls("indent", value)

    def _fail(self, analyzer: ASTAnalyzer, message: str, advice: str) -> None:
        error_label = {
            "newline": "Newline",
            "count": "Count",
            "ncount": "NCount",
            "indent": "Indent",
        }[self.kind]
        analyzer.report_error(
            errors.ParserError(
                f"Expected{error_label}Mismatch",
                errors.PARSER_UNEXPECTED_TOKEN,
                message,
                advice,
            ),
            pos=analyzer.parser.pos,
        )

    def _newline_matches(self, parser: Any) -> bool:
        previous = None
        for token in reversed(parser.tokens[: parser.pos]):
            if token.token not in (Token.NEWLINE, Token.INDENT, Token.DEDENT):
                previous = token
                break
        if previous is None:
            return False

        for token in parser.tokens[parser.pos :]:
            if token.token in (Token.NEWLINE, Token.INDENT, Token.DEDENT):
                continue
            return token.line > previous.line
        return False

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        parser = analyzer.parser

        if self.kind == "newline":
            if self._newline_matches(parser):
                return []
            self._fail(
                analyzer,
                "Expected.newline() requiere que el siguiente token significativo esté en otra línea.",
                "Separe la expresión actual de la siguiente mediante un salto de línea.",
            )
            return None

        remaining = sum(
            1 for token in parser.tokens[parser.pos :] if token.token != Token.EOF
        )
        expected = self.value

        if self.kind == "count":
            matches = remaining == expected
        elif self.kind == "ncount":
            matches = remaining != expected
        else:
            matches = parser.current_indent_level() == expected

        if matches:
            return []

        if self.kind == "indent":
            actual = parser.current_indent_level()
            self._fail(
                analyzer,
                f"Se esperaba indentación {expected}, pero la indentación actual es {actual}.",
                "Ajuste la indentación del bloque al nivel esperado.",
            )
        else:
            self._fail(
                analyzer,
                f"Expected.{self.kind}({expected}) no coincide: quedan {remaining} tokens.",
                "Verifique la cantidad exacta de tokens restantes.",
            )
        return None

    def __repr__(self) -> str:
        if self.kind == "newline":
            return "Expected.newline()"
        return f"Expected.{self.kind}({self.value})"


__all__ = ["Expected"]
