"""
Core Parser Engine (`gram.core.parser.core`).
=============================================
Defines the high-level `Parser` entry class that binds a lexed token stream
to `ParseState` and delegates grammatical evaluation to `ASTAnalyzer`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.ast import ASTAnalyzer
from gram.core.parser.control import ParseState

if TYPE_CHECKING:
    from gram.core.combinators import RuleItem
    from gram.core.lexer import TokenType


class Parser(ParseState):
    """
    Main syntactic parser managing token stream state and triggering AST analysis.
    """

    def __init__(self, tokens: list[TokenType], log_file: str | None = None) -> None:
        """
        Initialize the parser with a list of lexed tokens.

        Args:
            tokens (list[TokenType]): Sequence of tokens produced by the lexer.
            log_file (str | None): Optional log file path for diagnostic telemetry.
        """
        super().__init__(log_file)
        self.tokens = tokens

    def parse(self, entrypoint: type[RuleItem]) -> Any:
        """
        Execute syntactic analysis starting from the given grammar entrypoint rule.

        Args:
            entrypoint (type[RuleItem]): The root grammar rule class to evaluate.

        Returns:
            Any: The resulting AST or visitor output from `ASTAnalyzer.process()`.
        """
        if not self.tokens:
            self.error('Cannot start syntactic analysis: token stream is empty.')
            self.report_error(
                errors.ParserError(
                    'ParserNotStarted',
                    errors.PARSER_NOT_STARTED,
                    'No se puede iniciar el análisis sintáctico porque la lista de tokens está vacía.',
                    'Asegúrese de ejecutar el analizador léxico y pasar sus tokens al Parser.',
                )
            )
            return None

        self.debug('Starting syntactic analysis')
        analyzer = ASTAnalyzer(self, entrypoint)
        return analyzer.process()


__all__ = ['Parser']