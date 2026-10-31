"""
Core Parser Engine (`gram.core.parser.core`).
=============================================
Defines the high-level `Parser` entry class that binds a lexed token stream
to `ParseState` and delegates grammatical evaluation to `ASTAnalyzer`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.ast import ASTAnalyzer
from gram.core.parser.control import ParseState
from gram.core.parser.conversions import ConversionTarget

from dataclasses import dataclass

if TYPE_CHECKING:
    from gram.core.combinators import RuleItem
    from gram.core.lexer import TokenType
    from gram.sessions import Session


@dataclass(slots=True, frozen=True)
class TokenInfo:
    line: int
    col: int
    token: TokenType
    token_pos: int


class Parser(ParseState):
    """
    Main syntactic parser managing token stream state and triggering AST analysis.
    """

    def __init__(
        self,
        tokens: list[TokenType],
        log_file: str | None = None,
        *,
        conversions: Mapping[str, ConversionTarget] | None = None,
        session: "Session | None" = None,
        source: str | Sequence[str] | None = None,
    ) -> None:
        """
        Initialize the parser with a list of lexed tokens.

        Args:
            tokens (list[TokenType]): Sequence of tokens produced by the lexer.
            log_file (str | None): Optional log file path for diagnostic telemetry.
            conversions (Mapping[str, ConversionTarget] | None): Initial logical
                token conversions.
            session (Session | None): Optional session providing parser settings.
            source (str | Sequence[str] | None): Optional original source code string or lines.
        """
        super().__init__(log_file, conversions=conversions, session=session)
        self.tokens = tokens
        self.source = source if isinstance(source, str) else ("\n".join(source) if isinstance(source, (list, tuple)) else None)
        self._reset_indent_levels()
        self.analyzer_ast_instance: ASTAnalyzer | None = None

    def reset(
        self,
        tokens: list[TokenType],
        log_file: str | None = None,
        *,
        conversions: Mapping[str, ConversionTarget] | None = None,
        source: str | Sequence[str] | None = None,
    ) -> "Parser":
        """Reuse this parser instance for a fresh token stream.

        The session reference is preserved while cursor, diagnostics, hooks,
        conversions, and analyzer state are reset to constructor-equivalent
        values. Existing callers that instantiate ``Parser`` directly are
        unaffected.
        """
        prev_source = self.source
        ParseState.__init__(
            self,
            log_file,
            conversions=conversions,
            session=self.session,
        )
        self.tokens = tokens
        if source is not None:
            self.source = source if isinstance(source, str) else "\n".join(source)
        else:
            self.source = prev_source
        self._reset_indent_levels()
        self.analyzer_ast_instance = None
        return self

    def parse(
        self,
        entrypoint: type[RuleItem],
        mode: Literal["Many", "Some"] = "Many",
        *,
        trace: Literal["off", "basic", "detailed"] = "basic",
    ):
        """
        Execute syntactic analysis starting from the given grammar entrypoint rule.

        Args:
            entrypoint (type[RuleItem]): The root grammar rule class to evaluate.
            mode (Literal['Many', 'Some']): Top-level repetition mode ('Many' for 0+ or 'Some' for 1+).
            trace (Literal['off', 'basic', 'detailed']): Raytracing mode for the AST analyzer.

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
        analyzer = ASTAnalyzer(
            self,
            entrypoint,
            mode=mode,
            trace=trace,
            session=self.session,
        )
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


__all__ = ['Parser', 'TokenInfo']
