"""
Token Matching Combinator (`gram.core.combinators.match.match_token`).
======================================================================
Validates that the token currently under the parser cursor matches a specific
token type (`Token` enum, `CustomToken`, or string token identifier).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer.tokens import CustomToken, Token

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class MatchToken(Combinator):
    """
    Atomic combinator that validates whether the current token matches the
    configured token type (`Token`, `CustomToken`, or string identifier).

    Rejects `Token.KEYWORD` tokens (which must be matched via `MatchKeyword`
    or `MatchGroup`). On match, consumes the token and returns the node
    produced by `analyzer.delegate_return_node(current)`.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.TERMINAL_TOKEN

    def __init__(self, token: Token | CustomToken | str) -> None:
        """
        Initialize the token matcher with an expected token or string name.

        Args:
            token (Token | CustomToken | str): Target `Token`, `CustomToken`, or
                canonical token name string.
        """
        super().__init__()
        if isinstance(token, str):
            resolved = Token.from_string(token)
            if not resolved:
                errors.GrammarError(
                    "InvalidTokenReference",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"No se pudo resolver el identificador de token '{token}' a un Token válido.",
                    "Verifique que el nombre corresponda a un miembro válido del enum Token.",
                ).raise_error()
            self.token: Token | CustomToken = resolved  # type: ignore[assignment]
        else:
            self.token = token

    def _delegate_error(
        self,
        name: str,
        code: errors.CodeError,
        *cautions: str,
        analyzer: ASTAnalyzer,
    ) -> None:
        """
        Delegate a `ParserError` to `analyzer.report_error` weighted by the
        current physical cursor position.
        """
        analyzer.report_error(
            errors.ParserError(name, code, *cautions),
            pos=analyzer.parser.pos,
        )

    @property
    def token_name(self) -> str:
        """Return the canonical string name of the expected token."""
        if isinstance(self.token, (Token, CustomToken)) and hasattr(self.token, "name"):
            return self.token.name
        return str(self.token)

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Validate and consume the current token from the active parser stream.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any: AST node produced by `analyzer.delegate_return_node(current)`,
            or `None` if matching fails.
        """
        if not self.token:
            return None

        parser = analyzer.parser
        parser.node(
            "ProcessingMatchToken", "Procesando matcheo de Tokens", set_target=True
        )
        parser.debug(f"Matcheando <{self.token_name}>")

        try:
            if parser.empty():
                parser.error("Salida inesperada. No se encontró ningún Token.")
                self._delegate_error(
                    "EmptyTokenStream",
                    errors.PARSER_EARLY_EOF,
                    f"Salida inesperada al buscar <{self.token_name}>. El flujo de tokens está vacío o en EOF.",
                    analyzer=analyzer,
                )
                return None

            raw_current = parser.peek()
            current = parser.peek_effective()
            if raw_current is None or current is None:
                return None

            location = f"Line: {current.line}, Col: {current.col}"

            if parser.is_eof() and self.token != Token.EOF:
                parser.error(f"Se alcanzó EOF antes de lo esperado. {location}")
                self._delegate_error(
                    "EOFReached",
                    errors.PARSER_EARLY_EOF,
                    f"Se alcanzó el final del archivo (EOF) antes de lo esperado al buscar <{self.token_name}>.",
                    location,
                    analyzer=analyzer,
                )
                return None

            if current.token == Token.KEYWORD:
                parser.error(
                    f"Se encontró un Token de tipo Keyword no consumible para MatchToken: {current}, {location}"
                )
                self._delegate_error(
                    "UnexpectedKeywordToken",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Se esperaba el token <{self.token_name}>, pero se encontró una palabra reservada (Keyword): '{current.value}'.",
                    "Use MatchKeyword o MatchGroup para palabras reservadas en lugar de MatchToken.",
                    location,
                    analyzer=analyzer,
                )
                return None

            if current.token.name != self.token_name:
                parser.error(
                    f"El token actual ({current.token.name}) no coincide con el esperado ({self.token_name}). {location}"
                )
                self._delegate_error(
                    "TokenMismatch",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Discrepancia de tokens: se esperaba <{self.token_name}>, pero se obtuvo <{current.token.name}> ('{current.value}').",
                    location,
                    analyzer=analyzer,
                )
                return None

            parser.success(f"Se consumió el Token {current.token.name}. {location}")
            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return analyzer.delegate_return_node(current)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"MatchToken({self.token_name})"


__all__ = ["MatchToken"]
