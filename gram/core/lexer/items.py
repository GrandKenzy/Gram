"""
Flujo de Tokens y Utilidades de Navegación (`gram.core.lexer.items`).
=====================================================================
Define `TokenStream`, un envoltorio iterable e inspeccionable sobre la secuencia
de `TokenType` generada por el lexer, facilitando el trabajo al parser y combinadores.
"""
from __future__ import annotations

from typing import Iterator, Sequence

from gram import errors
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import error


class TokenStream:
    """
    ES:
        Envoltorio de alto nivel sobre una secuencia ordenada de `TokenType`.
        Proporciona cursores de lectura, lookahead ilimitado, consumo condicional
        y métodos de coincidencia ('match', 'check', 'consume').

    EN:
        High-level wrapper over an ordered sequence of `TokenType`.
        Provides reading cursors, lookahead, conditional consumption,
        and pattern matching methods.
    """

    def __init__(self, tokens: Sequence[TokenType]) -> None:
        self._tokens: tuple[TokenType, ...] = tuple(tokens)
        self._pos: int = 0

    @property
    def position(self) -> int:
        """Posición actual del cursor en el flujo de tokens."""
        return self._pos

    @position.setter
    def position(self, pos: int) -> None:
        self._pos = max(0, min(pos, len(self._tokens)))

    @property
    def tokens(self) -> tuple[TokenType, ...]:
        """Tupla inmutable de todos los tokens del flujo."""
        return self._tokens

    def has_next(self) -> bool:
        """Indica si quedan tokens antes de alcanzar el final o un Token.EOF."""
        if self._pos >= len(self._tokens):
            return False
        return self._tokens[self._pos].token != Token.EOF

    def is_eof(self) -> bool:
        """Indica si el cursor ha alcanzado el token EOF o el final de la lista."""
        if self._pos >= len(self._tokens):
            return True
        return self._tokens[self._pos].token == Token.EOF

    def current(self) -> TokenType | None:
        """Devuelve el token en la posición actual sin consumirlo."""
        if 0 <= self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def peek(self, offset: int = 0) -> TokenType | None:
        """
        Inspecciona un token a una distancia relativa sin avanzar el cursor.

        Args:
            offset: Desplazamiento desde la posición actual (0 = actual, 1 = siguiente).
        """
        idx = self._pos + offset
        if 0 <= idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def advance(self) -> TokenType:
        """Consume el token actual y avanza el cursor una posición."""
        token = self.current()
        if token is None:
            # Crear token EOF virtual si se desborda
            line = self._tokens[-1].line if self._tokens else 0
            col = self._tokens[-1].col if self._tokens else 0
            return TokenType(Token.EOF, None, line, col)
        self._pos += 1
        return token

    def next(self) -> TokenType:
        """Alias de `advance()` para compatibilidad con iteradores."""
        return self.advance()

    def check(self, *expected: Token | TokenType | str) -> bool:
        """
        Comprueba si el token actual coincide con alguno de los tipos o valores dados
        sin avanzar el cursor.
        """
        curr = self.current()
        if curr is None:
            return False

        for exp in expected:
            if isinstance(exp, Token) and curr.token == exp:
                return True
            if isinstance(exp, TokenType) and curr == exp:
                return True
            if isinstance(exp, str) and (curr.value == exp or curr.token.name == exp):
                return True
        return False

    def match(self, *expected: Token | TokenType | str) -> bool:
        """
        Si el token actual coincide con alguno de los tipos dados, lo consume y devuelve True.
        En caso contrario, mantiene el cursor y devuelve False.
        """
        if self.check(*expected):
            self.advance()
            return True
        return False

    def consume(self, expected: Token | TokenType | str | None = None, message: str = '') -> TokenType:
        """
        Consume el token actual verificando que coincida con el tipo esperado.

        Args:
            expected: Tipo de token o valor esperado (opcional).
            message: Mensaje de error personalizado en caso de discrepancia.

        Returns:
            El TokenType consumido.

        Raises:
            LexerError: Si el token no coincide con el esperado.
        """
        curr = self.current()
        if curr is None:
            error.LexerError(
                'Fin prematuro del flujo de tokens',
                errors.PARSER_EARLY_EOF,
                message or 'Se esperaba otro token pero se alcanzó el final de la secuencia.',
            ).raise_error()

        if expected is not None and not self.check(expected):
            exp_str = expected.name if isinstance(expected, Token) else str(expected)
            error.LexerError(
                f'Token inesperado: {curr.token.name}',
                errors.PARSER_UNEXPECTED_TOKEN,
                message or f'Se esperaba token {exp_str!r}, pero se encontró {curr.token.name!r} ({curr.value!r}) en línea {curr.line}:{curr.col}.',
            ).raise_error()

        return self.advance()

    def rewind(self, count: int = 1) -> None:
        """Retrocede el cursor la cantidad especificada de posiciones."""
        self._pos = max(0, self._pos - count)

    def reset(self) -> None:
        """Restablece el cursor al inicio del flujo."""
        self._pos = 0

    def slice(self, start: int, end: int | None = None) -> list[TokenType]:
        """Obtiene una subsecuencia de tokens."""
        return list(self._tokens[start:end])

    def filter_tokens(self, *exclude: Token) -> TokenStream:
        """
        Devuelve un nuevo `TokenStream` omitiendo los tipos de token indicados
        (por ejemplo, para filtrar comentarios o espacios).
        """
        filtered = [t for t in self._tokens if t.token not in exclude]
        return TokenStream(filtered)

    def __len__(self) -> int:
        return len(self._tokens)

    def __iter__(self) -> Iterator[TokenType]:
        return iter(self._tokens)

    def __getitem__(self, index: int | slice) -> TokenType | list[TokenType]:
        if isinstance(index, slice):
            return list(self._tokens[index])
        return self._tokens[index]

    def __repr__(self) -> str:
        return f"TokenStream(tokens={len(self._tokens)}, current={self._pos})"


__all__ = ['TokenStream']
