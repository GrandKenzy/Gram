"""
Combinador ConditionalExpr para Gram Framework.
==============================================
Analiza expresiones condicionales requeridas en sentencias de control de flujo
(if, while, ternarios, etc.).

A diferencia de ArithmeticExpr, ConditionalExpr:
- EXIGE que la expresión contenga una relación de comparación (==, !=, <, <=, >, >=)
  o un valor booleano explícito (true, false, o un identificador booleano como flag).
- Soporta operadores lógicos encadenados: && (AND) y || (OR) con precedencia canónica.
- Soporta negación lógica unaria: ! o not.
- Soporta agrupaciones con paréntesis: (a > b && c < d).
- Soporta expresiones aritméticas completas a los lados de cada comparación:
  ejemplo: 10 + 20 > 5, x * 2 == y + 1.
- RECHAZA expresiones puramente aritméticas sin operador de comparación o valor booleano
  (ejemplo: '10 + 20' o 'x + y' fallan con error de sintaxis claro).
"""
from __future__ import annotations

from typing import Any
from gram.core.combinators.base import Combinator
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.mods import register_custom_mod
from gram.core.lexer.tokens import Token, TokenType
from gram.errors import codes
from gram.utilities import error
from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
from gram.plugins.source.expressions.evaluator import ArithmeticSyntaxError


class ConditionalSyntaxError(ArithmeticSyntaxError):
    """Error de sintaxis específico de expresiones condicionales."""
    pass


COMP_OPS: set[Token] = {
    Token.EQUAL,
    Token.NOT_EQUAL,
    Token.LESS,
    Token.LESS_EQUAL,
    Token.GREATER,
    Token.GREATER_EQUAL,
}


def _is_comp_op(tok: TokenType) -> bool:
    """Verifica si el token corresponde a un operador relacional de comparación."""
    if tok.token in COMP_OPS:
        return True
    return isinstance(tok.value, str) and tok.value in ("==", "!=", "<", "<=", ">", ">=")


def _is_logic_and(tok: TokenType) -> bool:
    """Verifica si el token corresponde al operador lógico AND (&& o and)."""
    if tok.token in (Token.LOGIC_AND, Token.AND_LOGIC):
        return True
    return tok.token in (Token.KEYWORD, Token.IDENT) and str(tok.value).lower() == "and"


def _is_logic_or(tok: TokenType) -> bool:
    """Verifica si el token corresponde al operador lógico OR (|| u or)."""
    if tok.token in (Token.LOGIC_OR, Token.OR_LOGIC):
        return True
    return tok.token in (Token.KEYWORD, Token.IDENT) and str(tok.value).lower() == "or"


def _is_logic_not(tok: TokenType) -> bool:
    """Verifica si el token corresponde a una negación lógica (! o not)."""
    if tok.token in (Token.NOT_LOGIC, Token.LOGIC_NOT, Token.EXCLAMATION):
        return True
    return tok.token in (Token.KEYWORD, Token.IDENT) and str(tok.value).lower() == "not"


class ConditionalExpr(Combinator):
    """
    Combinador sintáctico para expresiones condicionales en Gram Framework.

    Diseñado específicamente para sentencias condicionales (if, while, ternarios),
    garantizando que la expresión analizada sea semánticamente una condición de verdad:
    - Exige una relación de comparación (==, !=, <, <=, >, >=) entre expresiones.
    - O un valor booleano explícito (true, false, flag booleana si allow_ident_boolean=True).
    - Soporta operadores lógicos encadenados: && (AND) y || (OR) con precedencia.
    - Soporta negación lógica unaria: ! o not.
    - Soporta agrupaciones entre paréntesis: (a > b && c < d).
    - RECHAZA expresiones puramente aritméticas sin operador de comparación
      (por ejemplo, '10 + 20' es rechazado de inmediato).
    """

    code: int = 7050
    name: str = "ConditionalExpr"
    description: str = (
        "Analizador de expresiones condicionales y relacionales con soporte para &&, ||, ! y comparaciones."
    )
    header_class: bool = True

    def __init__(
        self,
        allow_ident_boolean: bool = True,
        allow_boolean_literals: bool = True,
    ):
        super().__init__()
        self.header_class = True
        self.allow_ident_boolean = allow_ident_boolean
        self.allow_boolean_literals = allow_boolean_literals
        self._arithmetic = ArithmeticExpr(allow_ident=True)

    def is_valid_condition_atom(self, toks: list[TokenType]) -> bool:
        """Determina si una secuencia atómica analizada constituye una condición de verdad válida."""
        if not toks:
            return False
        # 1. Contiene al menos un operador de comparación (ej. a > 10, 10 + 20 == 30)
        if any(_is_comp_op(t) for t in toks):
            return True
        # 2. Es un literal booleano (true, false)
        if self.allow_boolean_literals and len(toks) == 1 and toks[0].token == Token.BOOL:
            return True
        # 3. Es un identificador aislado usado como bandera booleana (ej. if activo:)
        if self.allow_ident_boolean and len(toks) == 1 and toks[0].token == Token.IDENT:
            return True
        # Cualquier otra combinación (ej. '10 + 20', '42', 'x + y') carece de condición
        return False

    def parse(
        self,
        analyzer: Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> list[TokenType] | None:
        parser = getattr(analyzer, "parser", analyzer)
        target_node = self._get_node(analyzer) if hasattr(analyzer, "parser") else getattr(analyzer, "node", None)
        saved_pos = parser.pos

        # Estado del cursor recursivo
        if current is not None:
            if parser.not_empty() and parser.tokens[parser.pos] is current:
                self._next_tok = None
            else:
                self._next_tok = current
        else:
            self._next_tok = None

        def _peek() -> TokenType | None:
            if self._next_tok is not None:
                return self._next_tok
            if parser.not_empty():
                return parser.current()
            return None

        def _consume() -> TokenType | None:
            if self._next_tok is not None:
                tok = self._next_tok
                self._next_tok = None
                return tok
            if parser.not_empty():
                return parser.consume(node=target_node)
            return None

        def _parse_or() -> list[TokenType] | None:
            left = _parse_and()
            if left is None:
                return None
            result = list(left)
            while _peek() is not None and _is_logic_or(_peek()):
                op = _consume()
                right = _parse_and()
                if right is None:
                    return None
                if op is not None:
                    result.append(op)
                result.extend(right)
            return result

        def _parse_and() -> list[TokenType] | None:
            left = _parse_unary()
            if left is None:
                return None
            result = list(left)
            while _peek() is not None and _is_logic_and(_peek()):
                op = _consume()
                right = _parse_unary()
                if right is None:
                    return None
                if op is not None:
                    result.append(op)
                result.extend(right)
            return result

        def _parse_unary() -> list[TokenType] | None:
            p = _peek()
            if p is not None and _is_logic_not(p):
                op = _consume()
                sub = _parse_unary()
                if sub is None:
                    return None
                return ([op] if op is not None else []) + sub
            return _parse_primary()

        def _parse_primary() -> list[TokenType] | None:
            p = _peek()
            if p is None:
                return None

            # Caso 1: Paréntesis condicional agrupado: ( <cond> )
            if p.token == Token.LPAREN:
                chk_pos = parser.pos
                chk_next = self._next_tok
                lp = _consume()
                inner = _parse_or()
                closing = _peek()
                if inner is not None and closing is not None and closing.token == Token.RPAREN:
                    rp = _consume()
                    res = []
                    if lp is not None:
                        res.append(lp)
                    res.extend(inner)
                    if rp is not None:
                        res.append(rp)
                    return res
                # Si falló como condición agrupada (o es un paréntesis puramente aritmético), revertir
                parser.restore(chk_pos, node=target_node)
                self._next_tok = chk_next

            # Caso 2: Término relacional o booleano evaluado con ArithmeticExpr
            cur_tok = _consume()
            if cur_tok is None:
                return None
            chk_pos = parser.pos
            arith_toks = self._arithmetic.parse(analyzer, cur_tok, ignore_errors=True)
            if arith_toks is None:
                parser.restore(chk_pos, node=target_node)
                self._next_tok = cur_tok
                return None

            # Validar que cumpla la regla de condicional (no puramente aritmética)
            if not self.is_valid_condition_atom(arith_toks):
                parser.restore(chk_pos, node=target_node)
                self._next_tok = cur_tok
                return None

            return arith_toks

        # Ejecutar análisis descendente recursivo
        try:
            tokens_result = _parse_or()
        except Exception:
            tokens_result = None

        if tokens_result is not None:
            return tokens_result

        # Si falló, restaurar parser y emitir error si corresponde
        parser.restore(saved_pos, node=target_node)
        if ignore_errors:
            return None

        err_code = codes.CodeError((2, 1, 1, 0, 1), "Conditional.InvalidCondition")
        error.ParserError(
            f"La expresión condicional requiere un operador de comparación (==, !=, <, <=, >, >=) "
            f"o un valor booleano válido en '{current.value}'. Expresiones puramente aritméticas no son permitidas.",
            err_code,
            f"Línea {current.line}, Columna {current.col}",
        ).raise_error()

    def __repr__(self) -> str:
        return f"ConditionalExpr(ident_bool={self.allow_ident_boolean})"


CombinatorAdditionalStack.register(ConditionalExpr)
register_custom_mod(ConditionalExpr)

__all__ = ["ConditionalExpr", "ConditionalSyntaxError"]
