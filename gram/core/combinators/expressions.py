"""
Pratt Expression Combinators (`gram.core.combinators.expressions`).
===================================================================
Provides `ArithmeticExpr`, `ConditionalExpr`, and `DualExpr` powered by a
single-pass Top-Down Operator Precedence (Pratt) engine with native strict
parenthesis grouping, $O(1)$ static binding-power tables, and strict operand
validation (`Token` members and named `Ref` combinators).
"""
from __future__ import annotations

from collections import ChainMap
from collections.abc import Iterable, MutableMapping
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.ast.nodes import ASTNode
from gram.core.combinators.base import Combinator
from gram.core.combinators.reference import Ref
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


# ==============================================================================
# 1. BINDING POWER HELPERS & PUBLIC OPERATOR DICTIONARIES
# ==============================================================================

def bind_left(precedence: int) -> tuple[int, int]:
    """
    Compute `(left_bp, right_bp)` for a left-associative binary operator:
    `(2 * p, 2 * p + 1)` -> `((a op b) op c)`.
    """
    bp = precedence * 2
    return (bp, bp + 1)


def bind_right(precedence: int) -> tuple[int, int]:
    """
    Compute `(left_bp, right_bp)` for a right-associative binary operator:
    `(2 * p, 2 * p - 1)` -> `(a op (b op c))`.
    """
    bp = precedence * 2
    return (bp, bp - 1)


# Public dictionary of binary arithmetic & bitwise operators: Token -> (left_bp, right_bp)
ARITHMETIC_BINARY_OPS: dict[Token, tuple[int, int]] = {
    # Exponentiation (right-associative, p=80)
    Token.POW: bind_right(80),
    # Multiplicative (left-associative, p=70)
    Token.STAR: bind_left(70),
    Token.SLASH: bind_left(70),
    Token.FLOOR_DIV: bind_left(70),
    Token.PERCENT: bind_left(70),
    # Additive (left-associative, p=60)
    Token.PLUS: bind_left(60),
    Token.MINUS: bind_left(60),
    # Bitwise Shifts (left-associative, p=50)
    Token.SHL: bind_left(50),
    Token.SHR: bind_left(50),
    # Bitwise AND / XOR / OR (left-associative, p=45, 40, 35)
    Token.AND: bind_left(45),
    Token.XOR: bind_left(40),
    Token.OR: bind_left(35),
}

# Public dictionary of prefix unary arithmetic & bitwise operators: Token -> right_bp
ARITHMETIC_UNARY_OPS: dict[Token, int] = {
    Token.PLUS: 150,
    Token.MINUS: 150,
    Token.NOT: 150,
    Token.INCREMENT: 150,
    Token.DECREMENT: 150,
    Token.SQRT: 150,
}

# Public dictionary of binary comparison & logical operators: Token -> (left_bp, right_bp)
CONDITIONAL_BINARY_OPS: dict[Token, tuple[int, int]] = {
    # Relational & Equality comparisons (left-associative, p=30)
    Token.EQUAL: bind_left(30),
    Token.NOT_EQUAL: bind_left(30),
    Token.LESS: bind_left(30),
    Token.LESS_EQUAL: bind_left(30),
    Token.GREATER: bind_left(30),
    Token.GREATER_EQUAL: bind_left(30),
    # Logical AND (left-associative, p=20)
    Token.AND_LOGIC: bind_left(20),
    Token.LOGIC_AND: bind_left(20),
    # Logical OR (left-associative, p=15)
    Token.OR_LOGIC: bind_left(15),
    Token.LOGIC_OR: bind_left(15),
}

# Public dictionary of prefix unary logical operators: Token -> right_bp
CONDITIONAL_UNARY_OPS: dict[Token, int] = {
    Token.NOT_LOGIC: 50,
    Token.LOGIC_NOT: 50,
    Token.EXCLAMATION: 50,
}

# Live merged views for DualExpr (automatically reflect mutations to the dicts above)
DUAL_BINARY_OPS: ChainMap[Token, tuple[int, int]] = ChainMap(
    CONDITIONAL_BINARY_OPS,
    ARITHMETIC_BINARY_OPS,
)

DUAL_UNARY_OPS: ChainMap[Token, int] = ChainMap(
    CONDITIONAL_UNARY_OPS,
    ARITHMETIC_UNARY_OPS,
)


# ==============================================================================
# 2. EXPRESSION AST NODES
# ==============================================================================

class ASTUnaryOp(ASTNode):
    """
    AST node representing a prefix unary operation (`op operand`).

    Attributes:
        operator (TokenType): The unary operator token.
        operand (ASTNode): The right-hand operand node.
    """

    def __init__(self, operator: TokenType, operand: ASTNode) -> None:
        super().__init__(operator)
        self.operator: TokenType = operator
        self.operand: ASTNode = operand

    def __repr__(self) -> str:
        return f"ASTUnaryOp(op={self.operator.token.name}, operand={self.operand!r})"


class ASTBinaryOp(ASTNode):
    """
    AST node representing an infix binary operation (`left op right`).

    Attributes:
        left (ASTNode): The left-hand operand node.
        operator (TokenType): The infix operator token.
        right (ASTNode): The right-hand operand node.
    """

    def __init__(
        self,
        left: ASTNode,
        operator: TokenType,
        right: ASTNode,
    ) -> None:
        super().__init__(operator)
        self.left: ASTNode = left
        self.operator: TokenType = operator
        self.right: ASTNode = right

    def __repr__(self) -> str:
        return (
            f"ASTBinaryOp(left={self.left!r}, "
            f"op={self.operator.token.name}, "
            f"right={self.right!r})"
        )


# ==============================================================================
# 3. BASE PRATT EXPRESSION COMBINATOR
# ==============================================================================

ValueSpec = Token | str | Ref


class BaseExpr(Combinator):
    """
    Base Top-Down Operator Precedence (Pratt) expression combinator.

    Enforces two architectural invariants:
    1. Only `Token` members (or token name strings) and named `Ref` combinators
       (`Ref(RULE, name=...)`) are permitted as atomic `values`.
    2. Parentheses (`Token.LPAREN` ... `Token.RPAREN`) are handled natively and
       strictly as precedence-resetting groups with bracket-aware whitespace skipping.
    """

    header_class: bool = True
    binary_ops: MutableMapping[Token, tuple[int, int]] = DUAL_BINARY_OPS
    unary_ops: MutableMapping[Token, int] = DUAL_UNARY_OPS

    def __init__(self, *values: ValueSpec | Iterable[ValueSpec]) -> None:
        """
        Initialize the expression combinator with allowed operand values.

        Args:
            *values (ValueSpec | Iterable[ValueSpec]): Allowed operand specifications.
                Each entry must be a `Token`, a valid `Token` string name, or a
                named `Ref(rule, name='...')`. If omitted, defaults to
                `(Token.NUMBER, Token.IDENT)`.
        """
        super().__init__()

        flattened: list[ValueSpec] = []
        for item in values:
            if isinstance(item, (list, tuple, set, frozenset)):
                flattened.extend(item)
            else:
                flattened.append(item)  # type: ignore[arg-type]

        if not flattened:
            flattened = [Token.NUMBER, Token.IDENT]

        ref_list: list[Ref] = []
        tok_set: set[Token] = set()

        for spec in flattened:
            if isinstance(spec, Ref):
                if not spec.name or not spec.name.strip():
                    errors.GrammarError(
                        "UnnamedRefInExpression",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        f"El combinador {self.type()} recibió un Ref({spec.rule_name!r}) sin atributo 'name'.",
                        "Por razones de trazabilidad en el AST de expresiones, use únicamente Refs nombrados: Ref(REGLA, name='alias').",
                    ).raise_error()
                ref_list.append(spec)
            elif isinstance(spec, Token):
                tok_set.add(spec)
            elif isinstance(spec, str):
                resolved = Token.from_string(spec)
                if resolved is None:
                    errors.GrammarError(
                        "InvalidExpressionTokenName",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        f"El nombre '{spec}' no corresponde a ningún Token válido en {self.type()}.",
                        "Pase miembros del enum Token o nombres válidos de Token en 'values'.",
                    ).raise_error()
                else:
                    tok_set.add(resolved)
            else:
                errors.GrammarError(
                    "UnsupportedExpressionValue",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"Valor no permitido en {self.type()}: {spec!r} ({type(spec).__name__}).",
                    "Las expresiones solo admiten miembros de Token y combinadores Ref(..., name='...').",
                ).raise_error()

        self._ref_values: tuple[Ref, ...] = tuple(ref_list)
        self._token_values: frozenset[Token] = frozenset(tok_set)

    def _parse_atom(self, analyzer: ASTAnalyzer, is_after_op: bool) -> ASTNode | None:
        """
        Parse a prefix expression atom:
        1. Parenthesized sub-expression `( expr )` (resets `min_bp` to 0).
        2. Prefix unary operator `op expr` (evaluates with `right_bp`).
        3. Named `Ref` operand from `self._ref_values` (evaluated first for maximal munch).
        4. Atomic `Token` operand from `self._token_values` ($O(1)$ lookup).
        """
        parser = analyzer.parser

        if parser.empty() or parser.is_eof():
            if is_after_op:
                analyzer.report_error(
                    errors.ParserError(
                        "ExpressionUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        "Se esperaba un operando para completar la expresión, pero se alcanzó el final del archivo (EOF).",
                        "Complete la operación con un valor, variable o llamada válida.",
                    ),
                    pos=parser.pos,
                )
            else:
                analyzer.report_error(
                    errors.ParserError(
                        "EmptyExpressionStream",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba una expresión ({self.type()}), pero se alcanzó EOF.",
                        "Proporcione una expresión válida.",
                    ),
                    pos=parser.pos,
                )
            return None

        curr = parser.peek()
        if curr is None:
            return None

        # 1. Native strict parentheses grouping: ( expr )
        if curr.token == Token.LPAREN:
            open_tok = parser.consume()
            assert open_tok is not None
            analyzer.discard_staged_failure(min_weight=parser.pos)

            parser.enter_delimiter()
            parser.skip_whitespace()
            try:
                inner_expr = self._parse_expr(analyzer, min_bp=0, is_after_op=True)
                if inner_expr is None:
                    return None

                parser.skip_whitespace()
                close_peek = parser.peek() if not parser.empty() else None
                if close_peek is None or close_peek.token != Token.RPAREN:
                    found_info = (
                        f"'{close_peek.value}' ({close_peek.token.name}) en línea {close_peek.line}, columna {close_peek.col}"
                        if close_peek is not None
                        else "EOF"
                    )
                    analyzer.report_error(
                        errors.ParserError(
                            "UnclosedExpressionParen",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"Se esperaba ')' para cerrar el paréntesis abierto en línea {open_tok.line}, "
                            f"columna {open_tok.col}, pero se encontró {found_info}.",
                            "Asegúrese de balancear todos los paréntesis de la expresión.",
                        ),
                        pos=parser.pos,
                    )
                    return None

                parser.consume()
                analyzer.discard_staged_failure(min_weight=parser.pos)
                return inner_expr
            finally:
                parser.exit_delimiter()

        # 2. Prefix unary operators
        if curr.token in self.unary_ops:
            right_bp = self.unary_ops[curr.token]
            op_tok = parser.consume()
            assert op_tok is not None
            analyzer.discard_staged_failure(min_weight=parser.pos)

            operand = self._parse_expr(analyzer, min_bp=right_bp, is_after_op=True)
            if operand is None:
                return None
            return ASTUnaryOp(op_tok, operand)

        # 3. Named Ref combinators (prioritized before raw Tokens so `call(x)` beats `IDENT`)
        for ref_comb in self._ref_values:
            chk = parser.savepoint("EXPR-RefAtom")
            with analyzer.safe_mode():
                ref_node = analyzer.visitor(ref_comb)

            if ref_node is not None:
                analyzer.discard_staged_failure(min_weight=parser.pos)
                return ref_node  # Guaranteed to be an ASTRef node

            parser.restore(chk)
            # If the named Ref partially consumed tokens (>1 token deep) and failed,
            # preserve its deep staged error and abort atom resolution.
            if analyzer.staged_weight > chk.pos:
                return None

        # 4. Atomic Token values ($O(1)$ set membership)
        if curr.token in self._token_values and curr.token != Token.KEYWORD:
            tok = parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return analyzer.delegate_return_node(tok)

        # 5. Mismatch: current token cannot act as an operand
        role_msg = (
            "después del operador"
            if is_after_op
            else f"al inicio de {self.type()}"
        )
        analyzer.report_error(
            errors.ParserError(
                "InvalidExpressionOperand",
                errors.PARSER_UNEXPECTED_TOKEN,
                f"Operando inválido {role_msg}: se encontró '{curr.value}' ({curr.token.name}) "
                f"en línea {curr.line}, columna {curr.col}.",
                "Verifique que el elemento esté permitido en la lista 'values' de la expresión.",
            ),
            pos=parser.pos,
        )
        return None

    def _parse_expr(
        self,
        analyzer: ASTAnalyzer,
        min_bp: int = 0,
        is_after_op: bool = False,
    ) -> ASTNode | None:
        """
        Core Pratt parsing loop driven by left and right binding powers `(l_bp, r_bp)`.
        """
        parser = analyzer.parser
        lhs = self._parse_atom(analyzer, is_after_op=is_after_op)
        if lhs is None:
            return None

        while not parser.empty() and not parser.is_eof():
            curr = parser.peek()
            if curr is None:
                break

            bp_pair = self.binary_ops.get(curr.token)
            if bp_pair is None:
                break

            l_bp, r_bp = bp_pair
            if l_bp < min_bp:
                break

            op_tok = parser.consume()
            assert op_tok is not None
            analyzer.discard_staged_failure(min_weight=parser.pos)

            rhs = self._parse_expr(analyzer, min_bp=r_bp, is_after_op=True)
            if rhs is None:
                return None

            lhs = ASTBinaryOp(lhs, op_tok, rhs)

        return lhs

    def _validate_root(
        self,
        analyzer: ASTAnalyzer,
        root: ASTNode,
        start_pos: int,
    ) -> bool:
        """Hook for subclasses to enforce structural constraints on the root node."""
        return True

    def parse(self, analyzer: ASTAnalyzer) -> ASTNode | None:
        """
        Parse an expression from the token stream, restoring the initial
        checkpoint and surfacing the deepest syntax error if parsing fails.
        """
        parser = analyzer.parser
        father = parser.node(
            f"Processing{self.type()}",
            f"Procesando expresión {self.type()}",
            set_target=True,
        )
        checkpoint = parser.savepoint(f"{self.type()}-Analysis")

        try:
            with analyzer.safe_mode():
                root = self._parse_expr(analyzer, min_bp=0, is_after_op=False)

            if root is None:
                parser.restore(checkpoint)
                if not analyzer.safe_flag:
                    analyzer.flush_failure()
                return None

            if not self._validate_root(analyzer, root, checkpoint.pos):
                parser.restore(checkpoint)
                if not analyzer.safe_flag:
                    analyzer.flush_failure()
                return None

            father.note(f"{self.type()} completado exitosamente: {root!r}", "success")
            return root
        finally:
            parser.down()

    def __repr__(self) -> str:
        toks = [f"Token.{t.name}" for t in self._token_values]
        refs = [repr(r) for r in self._ref_values]
        items = ", ".join(refs + toks)
        return f"{self.type()}({items})"


# ==============================================================================
# 4. CONCRETE COMBINATORS: ArithmeticExpr, ConditionalExpr, DualExpr
# ==============================================================================

class ArithmeticExpr(BaseExpr):
    """
    Pratt expression combinator restricted to arithmetic and bitwise operators
    (`ARITHMETIC_BINARY_OPS` and `ARITHMETIC_UNARY_OPS`).
    """

    binary_ops = ARITHMETIC_BINARY_OPS
    unary_ops = ARITHMETIC_UNARY_OPS


class ConditionalExpr(BaseExpr):
    """
    Pratt expression combinator restricted to relational comparison and logical
    boolean operators (`CONDITIONAL_BINARY_OPS` and `CONDITIONAL_UNARY_OPS`).

    If `strict=True` (default), requires the resulting expression tree to be a
    comparison/logical operation or a boolean/identifier atom.
    """

    binary_ops = CONDITIONAL_BINARY_OPS
    unary_ops = CONDITIONAL_UNARY_OPS

    def __init__(
        self,
        *values: ValueSpec | Iterable[ValueSpec],
        strict: bool = True,
    ) -> None:
        super().__init__(*values)
        self.strict: bool = strict

    def _validate_root(
        self,
        analyzer: ASTAnalyzer,
        root: ASTNode,
        start_pos: int,
    ) -> bool:
        if not self.strict:
            return True
        if isinstance(root, (ASTBinaryOp, ASTUnaryOp)):
            return True
        tok = getattr(root, "token", None)
        if isinstance(tok, TokenType) and tok.token in (Token.BOOL, Token.IDENT):
            return True

        curr_Info = (
            f" cerca de '{tok.value}' (línea {tok.line}, columna {tok.col})"
            if isinstance(tok, TokenType)
            else ""
        )
        analyzer.report_error(
            errors.GrammarError(
                "InvalidConditionalExpression",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"ConditionalExpr requiere una comparación u operación lógica válida{curr_Info}.",
                "Un valor literal aislado no constituye una condición válida cuando strict=True.",
            ),
            pos=start_pos,
        )
        return False


class DualExpr(BaseExpr):
    """
    Unified Pratt expression combinator combining both arithmetic/bitwise and
    relational/logical operators (`DUAL_BINARY_OPS` and `DUAL_UNARY_OPS`).

    Resolves mixed expressions such as `a + call(x) * 2 >= b - 1 && !flag`
    in a single linear pass according to binding power.

    If `require_condition=True`, allows full arithmetic inside sub-expressions
    while requiring the top-level root node to evaluate to a condition.
    """

    binary_ops = DUAL_BINARY_OPS
    unary_ops = DUAL_UNARY_OPS

    def __init__(
        self,
        *values: ValueSpec | Iterable[ValueSpec],
        require_condition: bool = False,
    ) -> None:
        super().__init__(*values)
        self.require_condition: bool = require_condition

    def _is_condition_tree(self, node: ASTNode) -> bool:
        """Verify that `node` evaluates to a relational or logical result at its top level."""
        if isinstance(node, ASTBinaryOp):
            return node.operator.token in CONDITIONAL_BINARY_OPS
        if isinstance(node, ASTUnaryOp):
            return node.operator.token in CONDITIONAL_UNARY_OPS
        tok = getattr(node, "token", None)
        return isinstance(tok, TokenType) and tok.token in (Token.BOOL, Token.IDENT)

    def _validate_root(
        self,
        analyzer: ASTAnalyzer,
        root: ASTNode,
        start_pos: int,
    ) -> bool:
        if not self.require_condition:
            return True
        if self._is_condition_tree(root):
            return True

        tok = getattr(root, "token", None)
        curr_info = (
            f" en línea {tok.line}, columna {tok.col}"
            if isinstance(tok, TokenType)
            else ""
        )
        analyzer.report_error(
            errors.GrammarError(
                "DualExprConditionRequired",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"DualExpr(require_condition=True) esperaba una condición o comparación en la raíz{curr_info}.",
                "La expresión contiene únicamente operaciones aritméticas sin ningún operador relacional o lógico.",
            ),
            pos=start_pos,
        )
        return False


__all__ = [
    # Public Static Operator Tables & Binding Helpers
    "ARITHMETIC_BINARY_OPS",
    "ARITHMETIC_UNARY_OPS",
    "CONDITIONAL_BINARY_OPS",
    "CONDITIONAL_UNARY_OPS",
    "DUAL_BINARY_OPS",
    "DUAL_UNARY_OPS",
    # Expression AST Nodes
    "ASTBinaryOp",
    "ASTUnaryOp",
    # Expression Combinators
    "ArithmeticExpr",
    "BaseExpr",
    "ConditionalExpr",
    "DualExpr",
    "bind_left",
    "bind_right",
]