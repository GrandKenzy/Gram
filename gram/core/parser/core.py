"""
Core Parser Engine (`gram.core.parser.core`).
=============================================
Defines the high-level `Parser` entry class that binds a lexed token stream
to `ParseState` and delegates grammatical evaluation to `ASTAnalyzer`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.ast import ASTAnalyzer
from gram.core.parser.control import ParseState

from dataclasses import dataclass

if TYPE_CHECKING:
    from gram.core.combinators import RuleItem
    from gram.core.lexer import TokenType


@dataclass(slots=True, frozen=True)
class TokenInfo:
    line: int
    col: int
    token: TokenType
    token_pos: int


# Backward-compatible alias
TokenInf = TokenInfo

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
        self.analyzer_ast_instance: ASTAnalyzer | None = None

    def parse(
        self,
        entrypoint: type[RuleItem],
        mode: Literal["Many", "Some"] = "Many",
    ) -> Any:
        """
        Execute syntactic analysis starting from the given grammar entrypoint rule.

        Args:
            entrypoint (type[RuleItem]): The root grammar rule class to evaluate.
            mode (Literal['Many', 'Some']): Top-level repetition mode ('Many' for 0+ or 'Some' for 1+).

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
        analyzer = ASTAnalyzer(self, entrypoint, mode=mode)
        self.analyzer_ast_instance = analyzer
        return analyzer.process()


    def get_token_info(self) -> TokenInfo | None:
        """
        Return an immutable snapshot of current token metadata at physical cursor.
        """
        current = self.peek()
        if not current:
            return None

        return TokenInfo(
            line=current.line,
            col=current.col,
            token=current,
            token_pos=self.pos,
        )


__all__ = ['Parser', 'TokenInfo', 'TokenInf']