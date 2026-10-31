"""
Fluent Token Requirement & Transformation Combinator (`gram.core.combinators.req`).
===================================================================================
Provides the `Req` combinator for chaining lexical validations (case, prefix,
suffix, length, numeric bounds, digit counts) and value transformations on a
matched token before delegating it to the AST.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from typing import ClassVar, TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer.tokens import CustomToken, Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Req(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.REQ
    """
    Fluent combinator for requiring, validating, and transforming a target token.

    Example:
        `Req(Token.IDENT).is_snake_case().min(3).apply_lower()`
    """

    def __init__(self, target_token: Token | CustomToken | str) -> None:
        """
        Initialize the fluent requirement combinator.

        Args:
            target_token (Token | CustomToken | str): Expected token type or name.
        """
        super().__init__()
        if isinstance(target_token, (Token, CustomToken)):
            self.target_token: str = target_token.name
        else:
            self.target_token = str(target_token)
        self._operations: list[Callable[[TokenType], TokenType]] = []

    def _add_op(self, op: Callable[[TokenType], TokenType]) -> Req:
        self._operations.append(op)
        return self

    # ==========================================================================
    # FLUENT VALIDATIONS
    # ==========================================================================

    def is_lower(self) -> Req:
        """Require the token value string to be all lowercase."""
        def op(t: TokenType) -> TokenType:
            if not str(t.value).islower():
                raise ValueError(f"El token '{t.value}' no está en minúsculas.")
            return t
        return self._add_op(op)

    def is_upper(self) -> Req:
        """Require the token value string to be all uppercase."""
        def op(t: TokenType) -> TokenType:
            if not str(t.value).isupper():
                raise ValueError(f"El token '{t.value}' no está en mayúsculas.")
            return t
        return self._add_op(op)

    def is_snake_case(self) -> Req:
        """Require the token value string to follow `snake_case` formatting."""
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            if val != val.lower() or " " in val:
                raise ValueError(f"El token '{t.value}' no cumple el formato snake_case.")
            return t
        return self._add_op(op)

    def is_camel_case(self) -> Req:
        """Require the token value string to follow `camelCase` / `PascalCase` formatting."""
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            if "_" in val or " " in val or not (val and val[0].isalpha()):
                raise ValueError(f"El token '{t.value}' no cumple el formato camelCase.")
            return t
        return self._add_op(op)

    def startswith(self, prefix: str) -> Req:
        """Require the token value string to start with `prefix`."""
        def op(t: TokenType) -> TokenType:
            if not str(t.value).startswith(prefix):
                raise ValueError(f"El token '{t.value}' no empieza con '{prefix}'.")
            return t
        return self._add_op(op)

    def endswith(self, suffix: str) -> Req:
        """Require the token value string to end with `suffix`."""
        def op(t: TokenType) -> TokenType:
            if not str(t.value).endswith(suffix):
                raise ValueError(f"El token '{t.value}' no termina con '{suffix}'.")
            return t
        return self._add_op(op)

    def length(self, n: int) -> Req:
        """Require the string representation of the token value to have exact length `n`."""
        def op(t: TokenType) -> TokenType:
            if len(str(t.value)) != n:
                raise ValueError(f"El token '{t.value}' no tiene longitud exacta de {n}.")
            return t
        return self._add_op(op)

    def min(self, n: int | float) -> Req:
        """Require numeric value `>= n` (or string length `>= n` for non-numeric tokens)."""
        def op(t: TokenType) -> TokenType:
            if isinstance(t.value, (int, float)):
                if t.value < n:
                    raise ValueError(f"El valor {t.value} es menor al mínimo permitido ({n}).")
            elif len(str(t.value)) < n:
                raise ValueError(f"El token '{t.value}' tiene longitud menor al mínimo ({n}).")
            return t
        return self._add_op(op)

    def max(self, n: int | float) -> Req:
        """Require numeric value `<= n` (or string length `<= n` for non-numeric tokens)."""
        def op(t: TokenType) -> TokenType:
            if isinstance(t.value, (int, float)):
                if t.value > n:
                    raise ValueError(f"El valor {t.value} supera el máximo permitido ({n}).")
            elif len(str(t.value)) > n:
                raise ValueError(f"El token '{t.value}' tiene longitud mayor al máximo ({n}).")
            return t
        return self._add_op(op)

    def equal(self, expected: Any) -> Req:
        """Require the token value to equal `expected`."""
        def op(t: TokenType) -> TokenType:
            if str(t.value) != str(expected):
                raise ValueError(f"Se esperaba el valor '{expected}', pero se recibió '{t.value}'.")
            return t
        return self._add_op(op)

    def unequal(self, not_expected: Any) -> Req:
        """Require the token value to differ from `not_expected`."""
        def op(t: TokenType) -> TokenType:
            if str(t.value) == str(not_expected):
                raise ValueError(f"El valor del token no debe ser igual a '{not_expected}'.")
            return t
        return self._add_op(op)

    def mindig(self, n: int) -> Req:
        """Require at least `n` numeric digits inside the token value."""
        def op(t: TokenType) -> TokenType:
            digs = sum(c.isdigit() for c in str(t.value))
            if digs < n:
                raise ValueError(f"El token '{t.value}' contiene menos de {n} dígitos.")
            return t
        return self._add_op(op)

    def maxdig(self, n: int) -> Req:
        """Require at most `n` numeric digits inside the token value."""
        def op(t: TokenType) -> TokenType:
            digs = sum(c.isdigit() for c in str(t.value))
            if digs > n:
                raise ValueError(f"El token '{t.value}' excede el máximo de {n} dígitos.")
            return t
        return self._add_op(op)

    def contains(self, *items: str) -> Req:
        """Require the token value string to contain all substrings in `items`."""
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            for item in items:
                if item not in val:
                    raise ValueError(f"El token '{val}' no contiene la subcadena requerida '{item}'.")
            return t
        return self._add_op(op)

    def excludes(self, *items: str) -> Req:
        """Require the token value string to exclude all substrings in `items`."""
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            for item in items:
                if item in val:
                    raise ValueError(f"El token '{val}' contiene la subcadena prohibida '{item}'.")
            return t
        return self._add_op(op)

    # ==========================================================================
    # FLUENT TRANSFORMATIONS
    # ==========================================================================

    def apply_lower(self) -> Req:
        """Convert the token value string to lowercase."""
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).lower()
            return t
        return self._add_op(op)

    def apply_upper(self) -> Req:
        """Convert the token value string to uppercase."""
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).upper()
            return t
        return self._add_op(op)

    def apply_camel(self) -> Req:
        """Convert a snake_case or space-separated token value to camelCase."""
        def op(t: TokenType) -> TokenType:
            parts = str(t.value).replace("_", " ").split()
            if parts:
                t.value = parts[0].lower() + "".join(x.title() for x in parts[1:])
            return t
        return self._add_op(op)

    def transform(self, target_fn: Callable[[Any], Any]) -> Req:
        """Apply an arbitrary callable `target_fn` to transform `t.value`."""
        def op(t: TokenType) -> TokenType:
            try:
                t.value = target_fn(t.value)
            except Exception as exc:
                fn_name = getattr(target_fn, "__name__", str(target_fn))
                raise ValueError(f"No se pudo transformar mediante {fn_name}: {exc}") from exc
            return t
        return self._add_op(op)

    def replace(self, old: str, new: str) -> Req:
        """Replace occurrences of `old` with `new` in the token value string."""
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).replace(old, new)
            return t
        return self._add_op(op)

    def change(self, new_val: Any) -> Req:
        """Override the token value with `new_val`."""
        def op(t: TokenType) -> TokenType:
            t.value = new_val
            return t
        return self._add_op(op)

    def addl(self, prefix: str) -> Req:
        """Prepend `prefix` to the token value string."""
        def op(t: TokenType) -> TokenType:
            t.value = prefix + str(t.value)
            return t
        return self._add_op(op)

    def addr(self, suffix: str) -> Req:
        """Append `suffix` to the token value string."""
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value) + suffix
            return t
        return self._add_op(op)

    def apply_zfill(self, width: int) -> Req:
        """Zero-pad the token value string on the left to `width` characters."""
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).zfill(width)
            return t
        return self._add_op(op)

    # ==========================================================================
    # PARSING EXECUTION
    # ==========================================================================

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Validate the current token against `self.target_token` and all chained
        operations, consuming and delegating the transformed token on success.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingReq", "Procesando requerimientos de Token", set_target=True
        )
        father.note(f"Evaluando Req para <{self.target_token}>", "normal")

        try:
            if parser.empty():
                father.note("Fin de archivo inesperado en combinador Req.", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "ReqUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        f"Fin de archivo inesperado al evaluar Req(<{self.target_token}>).",
                        "Asegúrese de proporcionar el token requerido.",
                    ),
                    pos=parser.pos,
                )
                return None

            active_token = parser.peek()
            if active_token is None:
                return None

            token_name = getattr(active_token.token, "name", str(active_token.token))
            if token_name != self.target_token and str(active_token.token) != self.target_token:
                father.note(
                    f"Se esperaba {self.target_token}, se recibió {token_name}",
                    "error",
                )
                analyzer.report_error(
                    errors.ParserError(
                        "ReqTokenMismatch",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"Req esperaba '{self.target_token}', pero encontró '{token_name}' "
                        f"({active_token.value!r}) en línea {active_token.line}, columna {active_token.col}.",
                        "Verifique el tipo de token en esta posición.",
                    ),
                    pos=parser.pos,
                )
                return None

            cloned_token = copy.copy(active_token)
            for idx, operation in enumerate(self._operations, start=1):
                try:
                    cloned_token = operation(cloned_token)
                except ValueError as exc:
                    father.note(
                        f"Req validación fallida (Paso {idx}): {exc}", "error"
                    )
                    analyzer.report_error(
                        errors.GrammarError(
                            "ReqConstraintFailed",
                            errors.GRAMMAR_COMBINATOR_FAILED,
                            f"Fallo en requerimiento de Req(<{self.target_token}>): {exc}",
                            f"Línea {active_token.line}, Columna {active_token.col}.",
                        ),
                        pos=parser.pos,
                    )
                    return None

            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            father.note(
                f"Req validado exitosamente: {cloned_token.value!r}", "success"
            )
            return analyzer.delegate_return_node(cloned_token)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Req({self.target_token!r}, ops={len(self._operations)})"


__all__ = ["Req"]