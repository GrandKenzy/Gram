"""
Combinador IsDigit (`gram.plugins.source.expressions.combinators.is_digit`).
============================================================================
Valida si el token actual representa un número o dígito.
Completamente desacoplado y autónomo.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType
from gram.errors import codes
from gram.utilities import error


class IsDigit(Combinator):
    """
    Combinador que valida si el token actual representa un dígito o número.
    Si coincide, consume el token; si no, levanta un error descriptivo.
    """
    code: int = 7010
    name: str = "IsDigit"
    description: str = "Valida si el token actual es un número o dígito."

    def evaluate(self, current: TokenType) -> bool:
        if current.token == Token.NUMBER:
            return True
        if isinstance(current.value, (int, float)):
            return True
        if isinstance(current.value, str):
            val = current.value.strip()
            if val.isdigit():
                return True
            try:
                float(val)
                return True
            except ValueError:
                return False
        return False

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        target_node = self._get_node(analyzer)

        if self.evaluate(current):
            if target_node:
                target_node.note(f"IsDigit reconoció token numérico: {current.value}", "Normal")
            analyzer.parser.advance()
            return current

        if ignore_errors:
            return None

        err_code = codes.CodeError((2, 1, 1, 0, 1), "Arithmetic.DigitExpected")
        error.ParserError(
            f"Se esperaba un número o dígito, pero se encontró '{current.value}' ({getattr(current.token, 'name', current.token)}).",
            err_code,
            f"Línea {current.line}, Columna {current.col}",
        ).raise_error()

    def __repr__(self) -> str:
        return "IsDigit()"


CombinatorAdditionalStack.register(IsDigit)
