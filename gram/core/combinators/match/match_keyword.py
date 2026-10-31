"""
Keyword Matching Combinator (`gram.core.combinators.match.match_keyword`).
==========================================================================
Validates that the token currently under the parser cursor is a registered
`Token.KEYWORD` matching an exact keyword identifier.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer.tokens import Token
from gram.core.lexer.words import Keyword

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class MatchKeyword(Combinator):
    """
    Atomic combinator that validates whether the current token is a `Token.KEYWORD`
    matching the expected keyword lexeme.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.TERMINAL_KEYWORD

    def __init__(self, keyword: str | Keyword) -> None:
        """
        Initialize the keyword matcher with the target keyword name or `Keyword` object.

        Args:
            keyword (str | Keyword): Expected keyword string (e.g., `'def'`, `'if'`)
                or `Keyword` instance.
        """
        super().__init__()
        self.keyword: str = (
            keyword.name if isinstance(keyword, Keyword) else str(keyword)
        )

    def parse(self, analyzer: ASTAnalyzer) -> Any | None:
        """
        Verify that the current token is a `Token.KEYWORD` with value `self.keyword`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any | None: Delegated AST node on match, or `None` on mismatch.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingMatchKeyword",
            "Procesando match de palabra clave",
            set_target=True,
        )
        father.note(f"Revisando Keyword: {self.keyword}", "normal")

        try:
            if parser.empty():
                father.note("Salida inesperada. No se encontró ningún Token.", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "EmptyTokenStream",
                        errors.PARSER_EARLY_EOF,
                        f"Salida inesperada (EOF) al buscar la palabra clave {self.keyword!r}.",
                        "Verifique que la expresión esté completa.",
                    ),
                    pos=parser.pos,
                )
                return None

            current = parser.peek()
            if current is None:
                return None

            if current.token != Token.KEYWORD:
                father.note(
                    f"El Token actual no es de tipo KEYWORD. Line: {current.line}, Col: {current.col}",
                    "error",
                )
                analyzer.report_error(
                    errors.ParserError(
                        "KeywordTypeMismatch",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"Se esperaba la palabra clave {self.keyword!r}, pero se obtuvo el token "
                        f"'{current.token.name}' ({current.value!r}) en línea {current.line}, columna {current.col}.",
                        f"Asegúrese de colocar la palabra clave '{self.keyword}' en esta posición.",
                    ),
                    pos=parser.pos,
                )
                return None

            if current.value != self.keyword:
                father.note(
                    f"El Token actual no coincide con el esperado: "
                    f"current={current.value}, expected={self.keyword}. "
                    f"Line: {current.line}, Col: {current.col}",
                    "error",
                )
                analyzer.report_error(
                    errors.ParserError(
                        "KeywordValueMismatch",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"Se esperaba la palabra clave {self.keyword!r}, pero se encontró "
                        f"{current.value!r} en línea {current.line}, columna {current.col}.",
                        f"Reemplace {current.value!r} por {self.keyword!r}.",
                    ),
                    pos=parser.pos,
                )
                return None

            father.note(
                f"Se encontró el keyword {current}. Line: {current.line}, Col: {current.col}",
                "success",
            )
            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return analyzer.delegate_return_node(current)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"MatchKeyword({self.keyword!r})"


__all__ = ["MatchKeyword"]