"""
Lexer State and Cursor Control (`gram.core.lexer.control`).
===========================================================
Provides the `LexerState` base class inheriting from `Diagnostics`, managing
line/column cursors, indentation levels, comment detection, stack-based
telemetry, and formal `report_error` handling for the lexical analyzer.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from gram import config, errors
from gram.core.lexer.multiline import get_multline
from gram.core.lexer import tokens
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import Diagnostics, Format
from gram.utilities.info.stack import StackInfo

if TYPE_CHECKING:  # pragma: no cover - typing-only circular import guard
    from gram.sessions import Session


class LexerState(Diagnostics):
    """
    Manages source line navigation, character cursors, indentation stack,
    comment stripping, and stack-based diagnostic telemetry for the `Lexer`.
    """

    _fallback_stack: ClassVar[StackInfo | None] = None
    _active_instance: ClassVar[LexerState | None] = None

    def __init__(
        self,
        source: Sequence[str] | str | Path,
        logfile: str | None = None,
        *,
        session: "Session | None" = None,
    ) -> None:
        """
        Initialize the lexical state, load the source lines, and set up the
        `Diagnostics` telemetry stack.

        Args:
            source (Sequence[str] | str | Path): Source code string, lines, or file path.
            logfile (str | None): Optional log file name for lexer diagnostics.
        """
        self.session = session
        self.telemetry_enabled = bool(self.get_config("LEXER_ADD_INFO", True))
        super().__init__(
            logfile or "lexer-log",
            "LEXER",
            "Registro y diagnóstico del analizador léxico",
            True,
            self.get_config("INFO_GENERATE_LOGFILE", False)
            and self.get_config("LEXER_ADD_INFO", True),
            self.get_config("INFO_GENERATE_LOGFILE_ON_ERROR", False),
        )
        LexerState._active_instance = self

        self.source: list[str] = []
        self.line: int = 0
        self.col: int = 0
        self.indents: list[int] = [0]
        self.comments: list[TokenType] = []

        self._load_source(source)

        comment_token = self.get_config("LEXER_COMMENT_TOKEN", "#")
        symbol_map = self.get_symbols()
        if comment_token not in symbol_map:
            self.error(
                f"El símbolo {comment_token!r} no es válido para comentarios."
            )
            self.report_error(
                errors.LexerError(
                    "InvalidCommentSymbol",
                    errors.LEXER_UNEXPECTED_CHARACTER,
                    f"El símbolo {comment_token!r} configurado en LEXER_COMMENT_TOKEN "
                    "no existe en MAP_SYMBOLS.",
                    "Configure un símbolo registrado en MAP_SYMBOLS (ej. '#').",
                )
            )
            self.comment_token: Token | str = "#"
        else:
            self.comment_token = symbol_map[comment_token]
        self.block_comment_token = self.get_config("LEXER_BLOCK_COMMENT_TOKEN", None)
        self.multiline = self._build_multiline_registry()

        self.info_node = None
        if self.telemetry_enabled:
            self.info_node = self.node(
                "LEXER",
                f"Inicializando lexer con {len(self.source)} líneas",
                set_target=True,
            )
            self.success(
                f"Lexer inicializado. Procesando {len(self.source)} líneas de entrada"
            )

    def _load_source(self, source: Sequence[str] | str | Path) -> None:
        """Load source lines from a string, `Path`, or sequence of strings."""
        if isinstance(source, str):
            self.source = source.splitlines()
        elif isinstance(source, Path):
            if not source.exists():
                self.error(f"El archivo {source} no existe")
                self.report_error(
                    errors.LexerError(
                        "FileNotFound",
                        errors.LEXER_FILE_NOT_FOUND,
                        f"El archivo fuente '{source}' no existe.",
                        "Verifique la ruta del archivo proporcionado al Lexer.",
                    )
                )
            else:
                self.source = source.read_text(encoding="utf-8").splitlines()
                Format.FileTar.set(source.resolve())
        else:
            self.source = [s.rstrip("\r\n") for s in source]

    def _build_multiline_registry(self) -> dict[str, str]:
        """Build the active delimiter table for this lexer instance."""
        registry = dict(get_multline())
        if not self.get_config("LEXER_SUPPORT_DOCSTRINGS", True):
            registry.pop('"""', None)
            registry.pop("'''", None)
        if (
            self.get_config("LEXER_SUPPORT_BLOCK_COMMENTS", True)
            and self.block_comment_token
        ):
            registry[self.block_comment_token] = "*/"
        return registry

    def multiline_match(self, col_override: int | None = None) -> tuple[str, str] | None:
        """Return the longest active multiline delimiter at the current column."""
        pos = self.col if col_override is None else col_override
        for opening in sorted(self.multiline, key=len, reverse=True):
            if self.currline.startswith(opening, pos):
                return opening, self.multiline[opening]
        return None

    def get_config(self, name: str, default=None):
        """Return a session setting, falling back to the legacy global config."""
        if self.session is not None:
            return self.session.config.get(name, getattr(config, name, default))
        return getattr(config, name, default)

    def get_keyword(self, name: str):
        """Return a keyword from the session catalog or legacy global catalog."""
        if self.session is not None:
            return self.session.get_keyword(name)
        from gram.core.lexer import words

        return words.get_keyword(name)

    def get_symbols(self):
        """Return the symbol map visible to this lexer instance."""
        if self.session is not None:
            return self.session.symbols
        return tokens.MAP_SYMBOLS

    def sorted_symbols(self) -> list[str]:
        """Return visible symbols in maximal-munch order."""
        if self.session is not None:
            return self.session.symbol_order
        return tokens.get_sorted_symbols()

    def keyword_count(self) -> int:
        """Return the count of keywords visible to this lexer."""
        if self.session is not None:
            return self.session.keyword_count()
        from gram.core.lexer import words

        return words.count_keywords()

    def process_multiline(
        self,
        opening: str,
        closing: str,
        *,
        token: Token = Token.STRING,
        description: str = "",
        decode_escapes: bool = False,
    ) -> TokenType:
        """Consume one registered multiline construct across source lines."""
        start = self.col
        start_line = self.line
        self.col += len(opening)
        chars: list[str] = []

        while self.has_lines():
            if self.currline.startswith(closing, self.col):
                self.col += len(closing)
                return TokenType(
                    token,
                    "".join(chars),
                    start_line,
                    start,
                    description=description,
                )

            if self.col >= len(self.currline):
                chars.append("\n")
                self.line += 1
                self.col = 0
                continue

            char = self.advance()
            if decode_escapes and char == "\\":
                if self.col >= len(self.currline):
                    chars.append("\\")
                    continue
                escaped = self.advance()
                from gram.core.lexer.visitors.strings import process_escape

                chars.append(process_escape(escaped, self))
            else:
                chars.append(char)

        self.report_error(
            errors.LexerError(
                "UnclosedMultilineLiteral",
                errors.LEXER_UNCLOSED_STRING,
                f"Literal multiline sin cerrar iniciado en línea {start_line + 1}, columna {start}.",
                f"Se esperaba el delimitador de cierre {closing!r}.",
            )
        )
        return TokenType(Token.ERROR, "".join(chars), start_line, start)

    @classmethod
    def get_stack(cls) -> StackInfo:
        """Return the active lexer diagnostic stack (or a fallback stack if uninitialized)."""
        if cls._active_instance is not None:
            return cls._active_instance.stack
        if cls._fallback_stack is None:
            enabled = bool(getattr(config, "LEXER_ADD_INFO", True))
            cls._fallback_stack = StackInfo(
                "lexer-log",
                "LEXER",
                "Registro y diagnóstico del analizador léxico",
                expose_nodes=enabled,
                generate_on_error=getattr(config, "INFO_GENERATE_LOGFILE_ON_ERROR", False),
                generate_log_file=getattr(config, "INFO_GENERATE_LOGFILE", False)
                and enabled,
            )
        return cls._fallback_stack

    @classmethod
    def reset_stack(cls) -> StackInfo:
        """Reset and return a fresh fallback `StackInfo` instance."""
        active = cls._active_instance
        enabled = (
            active.get_config("LEXER_ADD_INFO", True)
            if active is not None
            else bool(getattr(config, "LEXER_ADD_INFO", True))
        )
        cls._fallback_stack = StackInfo(
            "lexer-log",
            "LEXER",
            "Registro y diagnóstico del analizador léxico",
            expose_nodes=enabled,
            generate_on_error=getattr(config, "INFO_GENERATE_LOGFILE_ON_ERROR", False),
            generate_log_file=getattr(config, "INFO_GENERATE_LOGFILE", False) and enabled,
        )
        if cls._active_instance is not None:
            cls._active_instance.stack = cls._fallback_stack
            cls._active_instance._targets.clear()
        return cls._fallback_stack

    def sender(self, msg: str, nt: Format.LogType) -> None:  # type: ignore[override]
        """Emit a diagnostic note to the active node if `LEXER_ADD_INFO` is enabled."""
        if self.get_config("LEXER_ADD_INFO", True):
            self.current().note(msg, nt)

    def report_error(self, err: errors.Error) -> errors.Error:
        """
        Record a lexical diagnostic error and raise it immediately if configured
        to exit on error.
        """
        res = self.record_failure(err)
        if (
            res is not None
            and not getattr(err, "_suppress_raise", False)
            and self.get_config("ERROR_EXIT_ON_ERROR", True)
        ):
            err.raise_error()
        return err

    def fail(self, name: str, code: errors.CodeError, *caution: str) -> None:
        """
        Log a lexical error to the active telemetry node, record it in diagnostics,
        and raise errors.LexerError unless suppressed by error hooks.
        """
        if self.get_config("LEXER_ADD_ERROR", True):
            self.error(f"Error léxico: {name}")
        err = errors.LexerError(name, code, *caution)
        res = self.record_failure(err)
        if (
            res is not None
            and not getattr(err, "_suppress_raise", False)
            and self.get_config("ERROR_EXIT_ON_ERROR", True)
        ):
            err.raise_error()

    # ==========================================================================
    # LINE AND CHARACTER NAVIGATION
    # ==========================================================================

    @property
    def currline(self) -> str:
        """Return the current source line string, or `''` if out of bounds."""
        if 0 <= self.line < len(self.source):
            return self.source[self.line]
        return ""

    def has_lines(self) -> bool:
        """Return True if unprocessed source lines remain."""
        return self.line < len(self.source)

    def is_empty(self) -> bool:
        """Return True if the current line is empty or contains only whitespace."""
        return self.currline.strip() == ""

    def peek(self, offset: int = 0) -> str:
        """Return the character at `self.col + offset` on the current line, or `''`."""
        target = self.col + offset
        line_str = self.currline
        if 0 <= target < len(line_str):
            return line_str[target]
        return ""

    def advance(self, steps: int = 1) -> str:
        """Consume and return the current character, advancing `self.col` by `steps`."""
        char = self.peek()
        self.col += steps
        return char

    # ==========================================================================
    # INDENTATION AND COMMENTS
    # ==========================================================================

    def is_comment_start(self, char: str, col_override: int | None = None) -> bool:
        """Return True if `char` at the current column starts a line comment."""
        pos = self.col if col_override is None else col_override
        if self.is_block_comment_start(pos):
            return True
        return self._comment_length(char, pos) > 0

    def is_block_comment_start(self, col_override: int | None = None) -> bool:
        """Return whether a configured block-comment opener starts at `col`."""
        marker = self.block_comment_token
        if not marker or not self.get_config("LEXER_SUPPORT_BLOCK_COMMENTS", True):
            return False
        pos = self.col if col_override is None else col_override
        return self.currline.startswith(marker, pos)

    def _comment_length(self, char: str, pos: int) -> int:
        """Return the length of the complete comment marker at `pos`, or zero."""
        comment_config = self.comment_token
        line_str = self.currline
        markers = (
            comment_config
            if isinstance(comment_config, (tuple, list, set))
            else (comment_config,)
        )
        for marker in markers:
            if isinstance(marker, str):
                if marker and line_str.startswith(marker, pos):
                    return len(marker)
            elif isinstance(marker, Token):
                symbol = self.get_symbols().get(marker)
                if isinstance(symbol, str) and line_str.startswith(symbol, pos):
                    return len(symbol)
                # Preserve support for single-character aliases of the token.
                if self.get_symbols().get(char) == marker:
                    return 1
        return 0

    def process_comment(self) -> TokenType:
        """Consume the remainder of the current physical line as a `Token.COMMENT`."""
        start = self.col
        line_str = self.currline

        comment_len = self._comment_length(self.peek(), self.col) or 1

        self.col += comment_len
        content = line_str[self.col :]
        self.col = len(line_str)

        self.debug(f"Comentario detectado en línea {self.line + 1}, columna {start}")
        return TokenType(Token.COMMENT, content, self.line, start)

    def process_indent(self) -> list[TokenType]:
        """
        Calculate leading indentation on the current line and emit `Token.INDENT`
        or `Token.DEDENT` tokens as needed.
        """
        generated: list[TokenType] = []
        line_str = self.currline
        leading_length = len(line_str) - len(line_str.lstrip(" \t"))
        prefix = line_str[:leading_length]
        indent = self.indentation_width(prefix)

        if not self.get_config("SUPPORT_INDENT", True):
            self.col = leading_length
            return generated

        current_indent = self.indents[-1]

        if indent > current_indent:
            self.indents.append(indent)
            generated.append(TokenType(Token.INDENT, indent, self.line, 0))
            self.success(f"INDENT generado: nivel {current_indent} -> {indent}")

        elif indent < current_indent:
            while len(self.indents) > 1 and indent < self.indents[-1]:
                self.indents.pop()
                generated.append(
                    TokenType(Token.DEDENT, self.indents[-1], self.line, 0)
                )
                self.success(f"DEDENT generado: nivel regresó a {self.indents[-1]}")

            if indent != self.indents[-1]:
                self.fail(
                    f"Indentación inválida en línea {self.line + 1}: nivel {indent}",
                    errors.LEXER_INDENTATION_MISMATCH,
                    f"El nivel de indentación actual ({indent}) no concuerda con ningún bloque anterior: {self.indents}.",
                )

        # ``col`` addresses the raw source string; indentation levels use the
        # configured visual width and therefore must not be used as an index
        # when tabs are present.
        self.col = leading_length
        return generated

    def indentation_width(self, prefix: str) -> int:
        """Return the configured visual indentation width for a leading prefix.

        ``LEXER_INDENT_STYLE`` accepts ``"spaces"`` (legacy behavior),
        ``"tabs"`` (tabs use ``LEXER_TAB_WIDTH``), and ``"mixed"`` (spaces
        count one column and tabs advance to the next tab stop). Invalid
        values fall back to ``"spaces"``. Complexity is O(P), where P is the
        length of the leading whitespace prefix.
        """
        style = self.get_config("LEXER_INDENT_STYLE", "spaces")
        if style not in {"spaces", "tabs", "mixed"}:
            style = "spaces"

        try:
            tab_width = int(self.get_config("LEXER_TAB_WIDTH", 4))
        except (TypeError, ValueError):
            tab_width = 4
        tab_width = max(1, tab_width)

        if style == "spaces":
            return prefix.count(" ")
        if style == "tabs":
            return prefix.count("\t") * tab_width

        width = 0
        for char in prefix:
            if char == "\t":
                width += tab_width - (width % tab_width)
            else:
                width += 1
        return width


__all__ = ["LexerState"]
