"""
Parser State and Cursor Control (`gram.core.parser.control`).
=============================================================
Provides the `ParseState` class, managing physical and virtual token cursors,
speculative lookahead, bracket-aware whitespace skipping, formal error reporting,
and stack-based diagnostic telemetry.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from gram import config, errors
from gram.core.lexer import Token, TokenType
from gram.core.parser import Checkpoint
from gram.utilities import Diagnostics, Format, error
from gram.core.parser.hookr import Hookr

class ParseState(Diagnostics):
    """
    Manages token stream navigation, backtracking checkpoints, virtual lookahead,
    and diagnostic telemetry for the parser.
    """

    def __init__(self, file: str | None = None) -> None:
        """
        Initialize the parser state and underlying diagnostics stack.

        Args:
            file (str | None): Optional log file identifier for diagnostics output.
        """
        self.pos: int = 0
        self.vpos: int = 0
        self.bracket_depth: int = 0
        self.tokens: list[TokenType] = []
        self.storage: dict[str, TokenType] = {}
        self.tk_tags: dict[int, frozenset[str]] = {}
        self._token_overrides: dict[int, TokenType] = {}
        # Cursor position that the most recent `restore()` abandoned.
        self._restore_from_pos: int = 0
        super().__init__(
            file or 'parser-log',
            'PARSER',
            'pending',
            True,
            config.INFO_GENERATE_LOGFILE,
            config.INFO_GENERATE_LOGFILE_ON_ERROR,
        )
        self.hookr = Hookr()

    def load(self, checkpoint: Checkpoint) -> None:
        self.pos = checkpoint.pos
        self.vpos = checkpoint.vpos
        self.bracket_depth = checkpoint.bracket_depth
        self._targets = list(checkpoint.targets)
        self.storage = dict(checkpoint.storage)
        self.tk_tags = dict(checkpoint.tk_tags)

        # Revert indices first replaced after the checkpoint, then recover the
        # exact values of indices that were already replaced when it was saved.
        saved_overrides = dict(checkpoint.token_overrides)
        for idx, orig_tok in self._token_overrides.items():
            if idx not in saved_overrides:
                self.tokens[idx] = orig_tok
        for idx, saved_token in checkpoint.token_values:
            self.tokens[idx] = saved_token
        self._token_overrides = saved_overrides

    def report_error(self, err: error.Error) -> error.Error:
        """
        Record a diagnostic error and raise it immediately if configured to exit on error.

        Args:
            err (error.Error): The error instance to record.

        Returns:
            error.Error: The supplied error instance, even when a hook omits it.
        """
        recorded = self.record_failure(err)
        if (
            recorded is not None
            and not getattr(err, '_suppress_raise', False)
            and config.ERROR_EXIT_ON_ERROR
        ):
            err.raise_error()
        return err

    def _report_empty_or_eof(self, operation: str) -> None:
        """
        Report `PARSER_NOT_STARTED` if the token list is empty, or
        `PARSER_EARLY_EOF` if the cursor has exhausted the token stream.

        Args:
            operation (str): Name of the cursor operation that triggered the failure.
        """
        if not self.tokens:
            self.error(f'{operation} failed: token stream is empty or uninitialized.')
            self.report_error(
                errors.ParserError(
                    'ParserNotStarted',
                    errors.PARSER_NOT_STARTED,
                    f'No se puede ejecutar "{operation}" porque el flujo de tokens está vacío.',
                    'Inicialice el parser con una lista válida de tokens antes de analizar.',
                )
            )
        else:
            self.error(f'{operation} failed: unexpected EOF at pos={self.pos}.')
            self.report_error(
                errors.ParserError(
                    'UnexpectedEOF',
                    errors.PARSER_EARLY_EOF,
                    f'Fin de archivo (EOF) prematuro durante "{operation}" en la posición {self.pos}.',
                    'Verifique que todas las expresiones y bloques estén cerrados correctamente.',
                )
            )

    def snapshot(self) -> dict[str, int]:
        """Return a dictionary of the current cursor and delimiter state."""
        return {
            'pos': self.pos,
            'vpos': self.vpos,
            'bracket_depth': self.bracket_depth,
        }

    def sender(self, msg: str, nt: Format.LogType) -> None:  # type: ignore
        """Emit a diagnostic note to the active node if parser logging is enabled."""
        if config.PARSER_ADD_INFO:
            self.current().note(msg, nt)

    # ==========================================================================
    # POSITIONS AND SIZES
    # ==========================================================================

    def count(self) -> int:
        """Return the total number of tokens in the stream."""
        return len(self.tokens)

    def remaining(self) -> int:
        """Return the number of unconsumed tokens remaining from the physical cursor."""
        return max(0, len(self.tokens) - self.pos)

    # ==========================================================================
    # PRIMITIVE CHECKS
    # ==========================================================================

    def empty(self) -> bool:
        """Return True if all tokens in the stream have been consumed."""
        return self.pos >= len(self.tokens)

    def is_eof(self) -> bool:
        """Return True if the stream is exhausted or the current token is EOF."""
        if self.empty():
            return True
        return self.tokens[self.pos].token == Token.EOF

    def normalice_index(self, index: int) -> int:
        """Clamp an index within the valid token stream boundaries `[0, count()]`."""
        return max(0, min(len(self.tokens), index))

    def validate_pos(self, pos: int, *, allow_end: bool = False) -> bool:
        """
        Check whether a position index is within the valid bounds of the token stream.

        Args:
            pos (int): Position index to validate.
            allow_end (bool): If True, allows `pos == len(self.tokens)` (for cursors/slices).
        """
        upper = len(self.tokens) if allow_end else len(self.tokens) - 1
        return 0 <= pos <= upper

    # ==========================================================================
    # BASIC CURSOR CONTROL
    # ==========================================================================

    def peek(self) -> TokenType | None:
        """Return the token at the current physical cursor without consuming it."""
        if self.empty():
            self._report_empty_or_eof('peek')
            return None

        if not self.validate_pos(self.pos):
            self.error(f'peek out of bounds. current: {self.pos}, total: {self.count()}')
            self.report_error(
                errors.ParserError(
                    'CursorOutOfBounds',
                    errors.PARSER_SYNTAX_ERROR,
                    f'El cursor físico ({self.pos}) está fuera de los límites ({self.count()}).',
                    'Revise las operaciones de desplazamiento del cursor en el parser.',
                )
            )
            return None

        tok = self.tokens[self.pos]
        self.debug(f'Peeked {tok}. Line={tok.line}, Col={tok.col}, Type={tok.token.name}')
        return tok

    def consume(self, expected: Token | str | None = None) -> TokenType | None:
        """
        Consume and return the current token, optionally verifying it matches `expected`.

        Args:
            expected (Token | str | None): Expected token type, token name, or lexeme value.
        """
        if self.empty():
            self._report_empty_or_eof('consume')
            return None

        token = self.tokens[self.pos]
        if expected is None:
            self.advance(1)
            return token

        matches_expected = (
            token.token == expected
            if isinstance(expected, Token)
            else token.token.name == expected or token.value == expected
        )

        if not matches_expected:
            exp_name = expected.name if isinstance(expected, Token) else expected
            self.error(
                f'Token mismatch at line={token.line}, col={token.col}: '
                f'expected {exp_name!r}, got {token.token.name!r} ({token.value!r})'
            )
            self.report_error(
                errors.ParserError(
                    'UnexpectedToken',
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f'Se esperaba el token "{exp_name}", pero se encontró "{token.token.name}" '
                    f'(valor={token.value!r}) en línea {token.line}, columna {token.col}.',
                    'Verifique la sintaxis cerca de la posición indicada.',
                )
            )
            return None

        self.advance(1)
        return token

    def advance(self, steps: int = 1) -> None:
        """
        Move the physical cursor forward by `steps` tokens.

        Args:
            steps (int): Number of positions to advance.
        """
        target = self.pos + steps
        if not self.validate_pos(target, allow_end=True):
            self.error(f'advance exceeded bounds. current: {self.pos}, target: {target}')
            self.report_error(
                errors.ParserError(
                    'AdvanceOutOfBounds',
                    errors.PARSER_EARLY_EOF,
                    f'Intento de avanzar el cursor fuera de límites (actual={self.pos}, destino={target}, total={self.count()}).',
                    'Asegúrese de no avanzar más allá del final del flujo de tokens.',
                )
            )
            return
        self.pos = target

    # ==========================================================================
    # ADVANCED CURSOR CONTROL
    # ==========================================================================

    def consume_if(self, *expected: Token | str) -> TokenType | None:
        """
        Consume and return the current token only if it matches any of `expected`.
        """
        if self.empty():
            return None

        current = self.tokens[self.pos]
        for exp in expected:
            if isinstance(exp, Token) and current.token == exp:
                return self.consume()
            if isinstance(exp, str) and (current.token.name == exp or current.value == exp):
                return self.consume()
        return None

    def peek_dist(self, offset: int = 0) -> TokenType | None:
        """
        Return the token at `self.pos + offset` without moving the physical cursor.
        """
        target = self.pos + offset
        if not self.validate_pos(target):
            self.error(f'peek_dist out of bounds. current: {self.pos}, target: {target}')
            self.report_error(
                errors.ParserError(
                    'LookaheadOutOfBounds',
                    errors.PARSER_EARLY_EOF,
                    f'Exploración lookahead fuera de rango (actual={self.pos}, destino={target}, total={self.count()}).',
                    'Verifique la cantidad de tokens restantes antes de inspeccionar con offset.',
                )
            )
            return None
        return self.tokens[target]

    # ==========================================================================
    # LOOKAHEAD, SAVEPOINTS, AND BACKTRACKING
    # ==========================================================================

    def lookahead(self, count: int = 1) -> list[TokenType | None]:
        """Return a list of the next `count` tokens starting from the physical cursor."""
        return [self.peek_dist(c) for c in range(count)]

    def matches(self, *expected: Token | str, offset: int = 0) -> bool:
        """
        Return True if the token at `self.pos + offset` matches any of `expected`.
        """
        target = self.pos + offset
        if not self.validate_pos(target):
            return False

        token = self.tokens[target]
        for exp in expected:
            if isinstance(exp, str):
                if token.token.name == exp or str(token.value) == exp:
                    return True
            elif token.token == exp:
                return True
        return False

    def slice(self, start: int, end: int) -> list[TokenType]:
        """
        Return a slice of tokens between indices `start` and `end`.
        """
        if start > end:
            self.error(f'Invalid slice range: start={start} > end={end}')
            self.report_error(
                errors.ParserError(
                    'InvalidSliceRange',
                    errors.PARSER_SYNTAX_ERROR,
                    f'Rango de corte inválido en slice: start ({start}) es mayor que end ({end}).',
                    'Asegúrese de que el índice inicial sea menor o igual al índice final.',
                )
            )
            return []

        for label, idx in (('start', start), ('end', end)):
            if not self.validate_pos(idx, allow_end=True):
                self.error(f'slice index out of bounds. current={self.pos}, {label}={idx}')
                self.report_error(
                    errors.ParserError(
                        'SliceOutOfBounds',
                        errors.PARSER_SYNTAX_ERROR,
                        f'El índice {label}={idx} en slice excede los límites del flujo de tokens (total={self.count()}).',
                        'Verifique los límites del flujo antes de realizar el corte.',
                    )
                )
                return []

        return self.tokens[start:end]

    def savepoint(self, name: str) -> Checkpoint:
        cp = Checkpoint(
            pos=self.pos,
            vpos=self.vpos,
            bracket_depth=self.bracket_depth,
            targets=tuple(self._targets),
            storage=tuple(self.storage.items()),
            tk_tags=tuple(self.tk_tags.items()),
            token_overrides=tuple(self._token_overrides.items()),
            name=name,
            token_values=tuple((idx, self.tokens[idx]) for idx in self._token_overrides),
        )
        self.success(
            f'Savepoint created: pos={cp.pos}, virtual={cp.vpos}, target={cp.target}'
        )
        self.hookr.ran('save', cp)
        return cp
    
    def replace_token_at(self, index: int, new_token: TokenType) -> None:
        """Replace token at `index` in-place while recording original for checkpoint rollback."""
        if 0 <= index < len(self.tokens):
            if index not in self._token_overrides:
                self._token_overrides[index] = self.tokens[index]
            self.tokens[index] = new_token

    def restore(self, checkpoint: Checkpoint) -> None:
        """
        Restore the parser state and diagnostic target stack to a given `Checkpoint`.
        """
        self._restore_from_pos = self.pos
        self.load(checkpoint)
        if checkpoint.target is not None:
            self.advice(
                f'Checkpoint {checkpoint.name} is restoring target to {checkpoint.target}'
            )
        self.success(f'Backtracking: restored checkpoint {checkpoint.name}')
        self.hookr.ran('restore', checkpoint)

    # ==========================================================================
    # VIRTUAL CURSOR CONTROL
    # ==========================================================================

    def future(self) -> TokenType | None:
        """Consume and return the token at the virtual cursor, advancing `vpos` by 1."""
        if self.empty():
            self._report_empty_or_eof('future')
            return None

        if not self.validate_pos(self.vpos):
            self.error(f'future exceeded bounds: {self.vpos} >= {self.count()}')
            self.report_error(
                errors.ParserError(
                    'VirtualCursorOutOfBounds',
                    errors.PARSER_EARLY_EOF,
                    f'El cursor virtual ({self.vpos}) alcanzó el final del flujo de tokens ({self.count()}).',
                    'Sincronice o restablezca el cursor virtual antes de consumir más tokens.',
                )
            )
            return None

        token = self.tokens[self.vpos]
        self.debug(f'Virtual consume [{self.vpos}]: {token}')
        self.vpos += 1
        return token

    def peek_vtoken(self, offset: int = 0) -> TokenType | None:
        """Return the token at `self.vpos + offset` without advancing the virtual cursor."""
        target = self.vpos + offset
        if not self.validate_pos(target):
            self.error(f'peek_vtoken exceeded bounds: {target} >= {self.count()}')
            self.report_error(
                errors.ParserError(
                    'VirtualPeekOutOfBounds',
                    errors.PARSER_EARLY_EOF,
                    f'Inspección virtual fuera de límites (destino={target}, total={self.count()}).',
                    'Verifique el límite de tokens disponibles durante la exploración virtual.',
                )
            )
            return None
        return self.tokens[target]

    def set_vtoken(
        self, pos: int | Literal['sync', 'end', 'start', 'front', 'back']
    ) -> None:
        """
        Position the virtual cursor using an explicit index or a relative preset.
        """
        if pos == 'start':
            resolved = 0
        elif pos == 'end':
            resolved = max(0, self.count() - 1)
        elif pos == 'sync':
            resolved = self.pos
        elif pos == 'front':
            resolved = self.pos + 1
        elif pos == 'back':
            resolved = self.pos - 1
        else:
            resolved = pos

        if not self.validate_pos(resolved, allow_end=True):
            self.error(f'Invalid position for set_vtoken: {resolved} (total={self.count()})')
            self.report_error(
                errors.ParserError(
                    'InvalidVirtualPosition',
                    errors.PARSER_SYNTAX_ERROR,
                    f'Posición inválida para set_vtoken: {resolved} (total de tokens={self.count()}).',
                    'Proporcione un índice dentro del rango válido de tokens.',
                )
            )
            return
        self.vpos = resolved

    def rollback(self) -> None:
        """Reset the virtual cursor back to the current physical cursor position."""
        self.vpos = self.pos
        self.advice(
            f'Virtual cursor rolled back: physical={self.pos}, virtual={self.vpos}'
        )

    def commit(self) -> list[TokenType]:
        """
        Advance the physical cursor to match the virtual cursor and return all
        tokens consumed in the range `[pos, vpos)`.
        """
        if self.vpos <= self.pos:
            self.error(
                f'Cannot commit backward or empty virtualization: '
                f'physical={self.pos}, virtual={self.vpos}'
            )
            self.report_error(
                errors.ParserError(
                    'InvalidVirtualCommit',
                    errors.PARSER_SYNTAX_ERROR,
                    f'No se puede confirmar (commit) una virtualización nula o hacia atrás '
                    f'(físico={self.pos}, virtual={self.vpos}).',
                    'Asegúrese de que el cursor virtual haya avanzado más allá del cursor físico.',
                )
            )
            return []

        if not self.validate_pos(self.vpos, allow_end=True):
            self.error(
                f'Virtual position out of bounds: size={self.count()}, virtual={self.vpos}'
            )
            self.report_error(
                errors.ParserError(
                    'VirtualCommitOutOfBounds',
                    errors.PARSER_EARLY_EOF,
                    f'La posición virtual ({self.vpos}) excede el tamaño del flujo ({self.count()}).',
                    'Verifique el avance del cursor virtual antes de ejecutar commit.',
                )
            )
            return []

        if not self.validate_pos(self.pos, allow_end=True):
            self.error(
                f'Physical position out of bounds: size={self.count()}, physical={self.pos}'
            )
            self.report_error(
                errors.ParserError(
                    'PhysicalCommitOutOfBounds',
                    errors.PARSER_SYNTAX_ERROR,
                    f'La posición física ({self.pos}) es inválida para el tamaño del flujo ({self.count()}).',
                    'Restaure un checkpoint válido antes de confirmar tokens.',
                )
            )
            return []

        consumed: list[TokenType] = self.tokens[self.pos : self.vpos]
        self.success(
            f'Commit succeeded. Consumed {len(consumed)} tokens ({self.pos} --> {self.vpos})'
        )
        self.pos = self.vpos
        return consumed

    def peek_next_line(self) -> TokenType | None:
        """Return the first token located on a subsequent line without advancing the physical cursor."""
        if self.empty() or self.is_eof():
            return None

        current = self.peek()
        if current is None:
            return None

        self.set_vtoken('sync')
        while True:
            vc = self.future()
            if vc is None or vc.token == Token.EOF:
                self.rollback()
                return None

            if vc.line != current.line:
                self.rollback()
                return vc

    def skip_until_newline(self) -> list[TokenType]:
        """
        Consume and return all tokens on the current line, positioning the physical cursor at the next line.
        """
        if self.empty() or self.is_eof():
            return []

        current = self.peek()
        if current is None:
            return []

        self.set_vtoken('sync')
        while True:
            vc = self.future()
            if vc is None or vc.token == Token.EOF:
                self.vpos -= 1
                if self.vpos > self.pos:
                    return self.commit()
                self.rollback()
                return []

            if vc.line != current.line:
                self.vpos -= 1
                if self.vpos > self.pos:
                    return self.commit()
                self.rollback()
                return []

    # ==========================================================================
    # CONTEXT AND DELIMITER CONTROL
    # ==========================================================================

    def enter_delimiter(self) -> None:
        """Increment the open bracket delimiter nesting depth."""
        self.bracket_depth += 1

    def exit_delimiter(self) -> None:
        """Decrement the open bracket delimiter nesting depth (clamped at 0)."""
        self.bracket_depth = max(0, self.bracket_depth - 1)

    def in_bracket(self) -> bool:
        """Return True if the parser is currently inside open bracket delimiters."""
        return self.bracket_depth > 0

    def skip_whitespace(self, *extra: Token) -> None:
        """
        Skip NEWLINE, INDENT, DEDENT, and any `extra` tokens while inside brackets.
        """
        if self.bracket_depth <= 0:
            return

        whitespace_types = {Token.NEWLINE, Token.INDENT, Token.DEDENT, *extra}
        n_tokens = len(self.tokens)
        while self.pos < n_tokens and self.tokens[self.pos].token in whitespace_types:
            self.pos += 1

    @contextmanager
    def transaction(self, name: str) -> Iterator[Checkpoint]:
        """
        Context manager executing a parsing block atomically, restoring state on exception.
        """
        cp = self.savepoint(f'transaction-{name}')
        try:
            yield cp
        except Exception:
            self.restore(cp)
            raise

    def quit(self, tok: Token) -> int:
        """
        Remove all occurrences of token type `tok` from the stream and clamp cursors.
        """
        initial_size = len(self.tokens)
        self.tokens = [t for t in self.tokens if t.token != tok]
        removed = initial_size - len(self.tokens)
        self.success(f'Removed {removed} tokens of type {tok.name}')

        self.pos = self.normalice_index(self.pos)
        self.vpos = self.normalice_index(self.vpos)
        return removed

    def synchronize(
        self, sync_tokens: tuple[Token, ...] | None = None
    ) -> tuple[list[TokenType], TokenType | None]:
        """
        Advance the physical cursor until a synchronization token is reached
        (panic-mode error recovery).
        """
        if sync_tokens is None:
            sync_tokens = (Token.NEWLINE, Token.DEDENT, Token.EOF)

        discarded: list[TokenType] = []
        breaker: TokenType | None = None
        while not self.empty():
            current = self.tokens[self.pos]
            if current.token in sync_tokens:
                breaker = current
                break
            discarded.append(current)
            self.pos += 1

        if discarded:
            until_msg = f" until {breaker.token.name}" if breaker is not None else " until EOF"
            self.advice(f'Discarded {len(discarded)} tokens during synchronization{until_msg}')
        return discarded, breaker


__all__ = [
    'Diagnostics',
    'ParseState',
]
