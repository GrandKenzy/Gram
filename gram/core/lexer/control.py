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
from typing import ClassVar

from gram import config, errors
from gram.core.lexer.multiline import get_multline
from gram.core.lexer import tokens
from gram.core.lexer.tokens import MAP_SYMBOLS, Token, TokenType
from gram.utilities import Diagnostics, Format
from gram.utilities.info.stack import StackInfo


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
    ) -> None:
        """
        Initialize the lexical state, load the source lines, and set up the
        `Diagnostics` telemetry stack.

        Args:
            source (Sequence[str] | str | Path): Source code string, lines, or file path.
            logfile (str | None): Optional log file name for lexer diagnostics.
        """
        super().__init__(
            logfile or "lexer-log",
            "LEXER",
            "Registro y diagnóstico del analizador léxico",
            True,
            config.INFO_GENERATE_LOGFILE and config.LEXER_ADD_INFO,
            config.INFO_GENERATE_LOGFILE_ON_ERROR,
        )
        LexerState._active_instance = self

        self.source: list[str] = []
        self.line: int = 0
        self.col: int = 0
        self.indents: list[int] = [0]
        self.comments: list[TokenType] = []

        self._load_source(source)

        if config.LEXER_COMMENT_TOKEN not in tokens.MAP_SYMBOLS:
            self.error(
                f"El símbolo {config.LEXER_COMMENT_TOKEN!r} no es válido para comentarios."
            )
            self.report_error(
                errors.LexerError(
                    "InvalidCommentSymbol",
                    errors.LEXER_UNEXPECTED_CHARACTER,
                    f"El símbolo {config.LEXER_COMMENT_TOKEN!r} configurado en LEXER_COMMENT_TOKEN "
                    "no existe en MAP_SYMBOLS.",
                    "Configure un símbolo registrado en MAP_SYMBOLS (ej. '#').",
                )
            )
            self.comment_token: Token | str = "#"
        else:
            self.comment_token = tokens.MAP_SYMBOLS[config.LEXER_COMMENT_TOKEN]
        self.block_comment_token = getattr(config, 'LEXER_BLOCK_COMMENT_TOKEN', None)
        self.multiline = self._build_multiline_registry()

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
        if not config.LEXER_SUPPORT_DOCSTRINGS:
            registry.pop('"""', None)
            registry.pop("'''", None)
        if (
            getattr(config, "LEXER_SUPPORT_BLOCK_COMMENTS", True)
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
            cls._fallback_stack = StackInfo(
                "lexer-log",
                "LEXER",
                "Registro y diagnóstico del analizador léxico",
                expose_nodes=True,
                generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR,
                generate_log_file=config.INFO_GENERATE_LOGFILE and config.LEXER_ADD_INFO,
            )
        return cls._fallback_stack

    @classmethod
    def reset_stack(cls) -> StackInfo:
        """Reset and return a fresh fallback `StackInfo` instance."""
        cls._fallback_stack = StackInfo(
            "lexer-log",
            "LEXER",
            "Registro y diagnóstico del analizador léxico",
            expose_nodes=True,
            generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR,
            generate_log_file=config.INFO_GENERATE_LOGFILE,
        )
        if cls._active_instance is not None:
            cls._active_instance.stack = cls._fallback_stack
            cls._active_instance._targets.clear()
        return cls._fallback_stack

    def sender(self, msg: str, nt: Format.LogType) -> None:  # type: ignore[override]
        """Emit a diagnostic note to the active node if `LEXER_ADD_INFO` is enabled."""
        if config.LEXER_ADD_INFO:
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
            and config.ERROR_EXIT_ON_ERROR
        ):
            err.raise_error()
        return err

    def fail(self, name: str, code: errors.CodeError, *caution: str) -> None:
        """
        Log a lexical error to the active telemetry node, record it in diagnostics,
        and raise errors.LexerError unless suppressed by error hooks.
        """
        if getattr(config, "LEXER_ADD_ERROR", True):
            self.error(f"Error léxico: {name}")
        err = errors.LexerError(name, code, *caution)
        res = self.record_failure(err)
        if res is not None and not getattr(err, "_suppress_raise", False):
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
        if not marker or not getattr(config, 'LEXER_SUPPORT_BLOCK_COMMENTS', True):
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
                symbol = MAP_SYMBOLS.get(marker)
                if isinstance(symbol, str) and line_str.startswith(symbol, pos):
                    return len(symbol)
                # Preserve support for single-character aliases of the token.
                if MAP_SYMBOLS.get(char) == marker:
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
        indent = len(line_str) - len(line_str.lstrip(" "))

        if not getattr(config, "SUPPORT_INDENT", True):
            self.col = indent
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
                    f"Indentación inválida en línea {self.line + 1}: {indent} espacios",
                    errors.LEXER_INDENTATION_MISMATCH,
                    f"El nivel de indentación actual ({indent}) no concuerda con ningún bloque anterior: {self.indents}.",
                )

        self.col = indent
        return generated


__all__ = ["LexerState"]
