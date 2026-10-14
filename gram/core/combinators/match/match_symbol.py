"""
Symbol and Pattern Matching Combinator (`gram.core.combinators.match.match_symbol`).
====================================================================================
Validates character sequences, operators, or textual patterns against the current
token's value using compiled regular expressions, with optional relabeling to
a synthesized `CustomToken`.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import CustomToken

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


def generador_expr(*parts: Any) -> str:
    """
    Build a regular expression string from literal strings and character ranges.

    Example:
        `generador_expr('#', ['A', 'F'], ['a', 'f'], [0, 9])` -> `'#[A-Fa-f0-9]'`

    Args:
        *parts (Any): Literal strings or 2-element lists/tuples representing
            inclusive character or digit ranges `[start, end]`.

    Returns:
        str: Compiled-ready regular expression pattern string.
    """
    result: list[str] = []
    char_class: list[str] = []

    def flush_class() -> None:
        if char_class:
            result.append("[" + "".join(char_class) + "]")
            char_class.clear()

    for part in parts:
        if isinstance(part, str):
            flush_class()
            result.append(re.escape(part))
            continue

        if isinstance(part, (list, tuple)) and len(part) == 2:
            start, end = part
            if isinstance(start, str) and isinstance(end, str):
                char_class.append(f"{re.escape(start)}-{re.escape(end)}")
                continue
            if isinstance(start, int) and isinstance(end, int):
                char_class.append(f"{start}-{end}")
                continue

        errors.GrammarError(
            "InvalidRegexGeneratorPart",
            errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
            f"Componente de expresión regular inválido en generador_expr: {part!r}.",
            "Use cadenas literales o pares [inicio, fin] de caracteres o enteros.",
        ).raise_error()

    flush_class()
    return "".join(result)


class MatchSeqSymbol(Combinator):
    """
    Combinator that evaluates the textual value of the current token against
    a regular expression pattern, a list of allowed symbol strings, or a literal string.
    """

    def __init__(
        self,
        pattern: str | None = None,
        symbols: list[str] | None = None,
        regex: str | None = None,
        custom_token_name: str | None = None,
        is_pattern: bool = True,
        case_sensitive: bool = False,
        raw: bool = False,
    ) -> None:
        """
        Initialize the symbol pattern matcher.

        Args:
            pattern (str | None): Pattern or literal text to match.
            symbols (list[str] | None): Candidate symbol strings joined via `|`.
            regex (str | None): Explicit regular expression (overrides `pattern`).
            custom_token_name (str | None): Optional name to relabel the matched token
                with a `CustomToken`.
            is_pattern (bool): If False, escapes `pattern` for exact literal matching.
            case_sensitive (bool): If False, enables case-insensitive matching.
            raw (bool): Reserved flag for raw unnormalized evaluation.
        """
        super().__init__()
        if regex is not None:
            actual_pattern = regex
            is_pattern = True
        elif symbols is not None:
            actual_pattern = "|".join(re.escape(s) for s in symbols)
            is_pattern = True
        elif pattern is not None:
            actual_pattern = pattern
        else:
            actual_pattern = ""

        self.pattern: str = actual_pattern
        self.symbols: list[str] | None = symbols
        self.regex: str | None = regex
        self.custom_token_name: str | None = custom_token_name
        self.is_pattern: bool = is_pattern
        self.case_sensitive: bool = case_sensitive
        self.raw: bool = raw

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern_str = actual_pattern if is_pattern else re.escape(actual_pattern)
        self._regex: re.Pattern[str] = re.compile(pattern_str, flags)

    def parse(self, analyzer: ASTAnalyzer) -> Any | None:
        """
        Evaluate the current token's value against the compiled regular expression.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any | None: Delegated AST node if matched, or `None` on mismatch.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingMatchSeqSymbol", "Procesando match de símbolo", set_target=True
        )
        father.note(f"Evaluando patrón {self.pattern!r}", "normal")

        try:
            if parser.empty():
                father.note("Salida inesperada. No se encontró ningún Token.", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "SymbolUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba un símbolo coincidente con {self.pattern!r}, pero se alcanzó EOF.",
                        "Complete la expresión antes del final del archivo.",
                    ),
                    pos=parser.pos,
                )
                return None

            tok = parser.peek()
            if tok is None:
                return None

            val_str = str(tok.value) if tok.value is not None else ""
            if not self._regex.fullmatch(val_str):
                father.note(
                    f"Patrón {self.pattern!r} no coincidió con {val_str!r}", "warn"
                )
                analyzer.report_error(
                    errors.ParserError(
                        "SymbolMismatch",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"El valor {val_str!r} en línea {tok.line}, columna {tok.col} "
                        f"no coincide con el patrón esperado {self.pattern!r}.",
                        "Verifique el operador o símbolo utilizado.",
                    ),
                    pos=parser.pos,
                )
                return None

            if self.custom_token_name:
                tok.token = CustomToken(self.custom_token_name, val_str)

            father.note(f"MatchSeqSymbol exitoso: {val_str!r}", "success")
            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return analyzer.delegate_return_node(tok)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"MatchSeqSymbol({self.pattern!r})"


MatchSymbol = MatchSeqSymbol

__all__ = [
    "MatchSeqSymbol",
    "MatchSymbol",
    "generador_expr",
]