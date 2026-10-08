"""
Combinador de expresiones condicionales para Gram Framework.
============================================================
Comparte el parser operacional aritmético y valida que el resultado sea una
comparación, una composición lógica o un átomo booleano permitido.
"""
from __future__ import annotations

from typing import Any

from gram.core.ast.nodes import ASTNode
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.combinators.mods import register_custom_mod
from gram.core.lexer.tokens import Token, TokenType
from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
from gram.plugins.source.expressions.evaluator import (
    ArithmeticNode,
    BinaryOpNode,
    BooleanNode,
    ExpressionASTNode,
    GroupNode,
    UnaryOpNode,
    VariableNode,
)
from gram.utilities import error
from gram.utilities.error.codes import CodeError


class ConditionalSyntaxError(Exception):
    """Error de sintaxis específico de expresiones condicionales."""


COMP_OPS: set[Token] = {
    Token.EQUAL,
    Token.NOT_EQUAL,
    Token.LESS,
    Token.LESS_EQUAL,
    Token.GREATER,
    Token.GREATER_EQUAL,
}
LOGIC_AND_OPS = {Token.LOGIC_AND, Token.AND_LOGIC}
LOGIC_OR_OPS = {Token.LOGIC_OR, Token.OR_LOGIC}
LOGIC_NOT_OPS = {Token.NOT_LOGIC, Token.LOGIC_NOT, Token.EXCLAMATION}


class ConditionalExpr(Combinator):
    """Parser de condiciones que conserva la jerarquía operacional en el AST."""

    code: int = 7050
    name: str = "ConditionalExpr"
    description: str = (
        "Analizador de expresiones condicionales, comparaciones y operadores lógicos."
    )
    header_class: bool = True

    def __init__(
        self,
        allow_ident_boolean: bool = True,
        allow_boolean_literals: bool = True,
        no_simplify: bool = True,
        grouping: bool = True,
    ) -> None:
        super().__init__()
        self.header_class = True
        self.allow_ident_boolean = allow_ident_boolean
        self.allow_boolean_literals = allow_boolean_literals
        self.no_simplify = no_simplify
        self.grouping = grouping
        self._arithmetic = ArithmeticExpr(allow_ident=True, allow_logical=True)

    def is_valid_condition_atom(self, tokens: list[TokenType]) -> bool:
        """Determina si los tokens contienen una comparación o un átomo booleano válido."""
        if any(token.token in COMP_OPS for token in tokens):
            return True
        if (
            self.allow_boolean_literals
            and len(tokens) == 1
            and tokens[0].token == Token.BOOL
        ):
            return True
        return (
            self.allow_ident_boolean
            and len(tokens) == 1
            and tokens[0].token == Token.IDENT
        )

    def _is_valid_condition(self, expression: ArithmeticNode) -> bool:
        if isinstance(expression, BinaryOpNode):
            operator = expression.op_token.token
            if operator in COMP_OPS:
                return True
            if operator in LOGIC_AND_OPS | LOGIC_OR_OPS:
                return (
                    self._is_valid_condition(expression.left)
                    and self._is_valid_condition(expression.right)
                )
            return False

        if isinstance(expression, UnaryOpNode):
            if expression.op_token.token in LOGIC_NOT_OPS:
                return self._is_valid_condition(expression.operand)
            return False

        if isinstance(expression, GroupNode):
            return self._is_valid_condition(expression.expr)

        if isinstance(expression, BooleanNode):
            return self.allow_boolean_literals

        if isinstance(expression, VariableNode):
            return self.allow_ident_boolean

        return False

    def parse(
        self,
        analyzer: Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> ASTNode | None:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        saved_pos = parser.pos
        result = self._arithmetic.parse(analyzer, current, ignore_errors=True)

        if isinstance(result, ExpressionASTNode) and self._is_valid_condition(
            result.expression
        ):
            if not self.grouping:
                result = self._strip_groups(result)
            for node in result.walk():
                node.no_simplify = self.no_simplify
            return result

        parser.restore(saved_pos, node=target_node)
        if ignore_errors:
            return None

        err_code = CodeError((2, 1, 1, 0, 1), "Conditional.InvalidCondition")
        token_value = current.value if current is not None else parser.peek()
        error.ParserError(
            "La expresión condicional requiere una comparación, un operador lógico "
            "con condiciones válidas o un átomo booleano permitido.",
            err_code,
            f"Expresión no válida cerca de {token_value!r}.",
        ).raise_error()

    @classmethod
    def _strip_groups(cls, node: ExpressionASTNode) -> ExpressionASTNode:
        flattened: list[ASTNode] = []
        for child in node.children:
            if isinstance(child, ExpressionASTNode):
                child = cls._strip_groups(child)
            if isinstance(child, ExpressionASTNode) and child.name == "Group":
                flattened.extend(child.children)
            else:
                flattened.append(child)
        node.children = []
        for child in flattened:
            node.add_child(child)
        return node

    def __repr__(self) -> str:
        return f"ConditionalExpr(ident_bool={self.allow_ident_boolean})"


CombinatorAdditionalStack.register(ConditionalExpr)
register_custom_mod(ConditionalExpr)

__all__ = ["ConditionalExpr", "ConditionalSyntaxError"]
