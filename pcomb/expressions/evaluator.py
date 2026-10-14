"""
Motor de análisis y evaluación de expresiones para Gram Framework.
===================================================================
Soporta:
- Números enteros y flotantes
- Identificadores / variables con entorno (env)
- Funciones matemáticas integradas en entorno (sqrt, sin, cos, abs, min, max, etc.)
- Operadores unarios: +, -, ~ (con encadenamiento arbitrario: --5, -+3, etc.)
- Operadores binarios:
  * Aritmética: +, -, *, /, //, %, **
  * Bits: &, |, ^, <<, >>
  * Comparación: ==, !=, <, <=, >, >=
  * Asignación: = (asociatividad derecha)
- Asociatividad correcta (+, -, *, / izquierda; **, = derecha)
- Precedencia estándar de operadores
- Paréntesis y anidamiento a profundidad arbitraria
"""
from __future__ import annotations

import math
from typing import Any
from gram.core.lexer.tokens import Token, TokenType
from gram.core.ast.nodes import ASTNode


class ArithmeticSyntaxError(Exception):
    """Error de sintaxis en expresión de expresiones / aritmética."""
    pass


# ============================================================================
# Entorno Matemático Predeterminado
# ============================================================================

DEFAULT_ENV: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "sqrt": math.sqrt,
    "abs": abs,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "min": min,
    "max": max,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "log": math.log,
    "exp": math.exp,
    "pow": math.pow,
    "true": 1,
    "false": 0,
    "True": 1,
    "False": 0,
}


# ============================================================================
# Nodos del Árbol de Sintaxis de Expresiones
# ============================================================================

class ArithmeticNode:
    """Clase base para nodos de la expresión sintáctica."""
    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError

    def to_tokens(self) -> list[TokenType]:
        raise NotImplementedError

    def to_ast_node(self, rule: Any = None, level: int = 0) -> ASTNode:
        return arithmetic_to_ast_node(self, rule=rule, level=level)


class BooleanNode(ArithmeticNode):
    """Nodo para literales booleanos: true, false."""
    def __init__(self, token: TokenType):
        self.token = token
        raw_val = token.value
        if isinstance(raw_val, bool):
            self.value: bool = raw_val
        elif str(raw_val).lower() in ("true", "1"):
            self.value = True
        else:
            self.value = False

    def evaluate(self, env: dict[str, Any] | None = None) -> int:
        return 1 if self.value else 0

    def to_tokens(self) -> list[TokenType]:
        return [self.token]

    def __str__(self) -> str:
        return "true" if self.value else "false"

    def __repr__(self) -> str:
        return f"Bool({self.value})"


def to_arithmetic_node(val: Any) -> ArithmeticNode:
    """Convierte de forma segura cualquier valor (TokenType, número o string) a un ArithmeticNode."""
    if isinstance(val, ArithmeticNode):
        return val
    if isinstance(val, ExpressionASTNode):
        return val.expression
    if isinstance(val, TokenType):
        if val.token == Token.NUMBER or isinstance(val.value, (int, float)):
            return NumberNode(val)
        if val.token == Token.BOOL or isinstance(val.value, bool):
            return BooleanNode(val)
        return VariableNode(val)
    if isinstance(val, bool):
        return BooleanNode(TokenType(token=Token.BOOL, value=val, line=1, col=0))
    if isinstance(val, (int, float)):
        return NumberNode(TokenType(token=Token.NUMBER, value=val, line=1, col=0))
    if isinstance(val, str):
        if val.lower() in ("true", "false"):
            return BooleanNode(TokenType(token=Token.BOOL, value=(val.lower() == "true"), line=1, col=0))
        return VariableNode(TokenType(token=Token.IDENT, value=val, line=1, col=0))
    if isinstance(val, list) and len(val) == 1 and isinstance(val[0], TokenType):
        return to_arithmetic_node(val[0])
    return VariableNode(TokenType(token=Token.IDENT, value=str(val), line=1, col=0))


class NumberNode(ArithmeticNode):
    def __init__(self, token: TokenType):
        self.token = token
        raw_val = token.value
        if isinstance(raw_val, (int, float)):
            self.value: int | float = raw_val
        else:
            str_val = str(raw_val).strip()
            if "." in str_val or "e" in str_val.lower():
                self.value = float(str_val)
            else:
                self.value = int(str_val)

    def evaluate(self, env: dict[str, Any] | None = None) -> int | float:
        return self.value

    def to_tokens(self) -> list[TokenType]:
        return [self.token]

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self.value)


class VariableNode(ArithmeticNode):
    def __init__(self, token: TokenType):
        self.token = token
        self.name: str = str(token.value)

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        active_env = {**DEFAULT_ENV, **(env or {})}
        if self.name in active_env:
            val = active_env[self.name]
            if isinstance(val, (int, float)):
                return val
            try:
                return float(val) if "." in str(val) else int(val)
            except (ValueError, TypeError):
                return val
        raise NameError(f"Variable '{self.name}' no definida en el entorno aritmético.")

    def to_tokens(self) -> list[TokenType]:
        return [self.token]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


class UnaryOpNode(ArithmeticNode):
    def __init__(self, op_token: TokenType, operand: ArithmeticNode):
        self.op_token = op_token
        self.op: str = str(op_token.value) if op_token.value is not None else ("+" if op_token.token == Token.PLUS else "-")
        self.operand = to_arithmetic_node(operand)

    @property
    def op1(self) -> ArithmeticNode:
        return self.operand

    @property
    def op2(self) -> None:
        return None

    @property
    def operator(self) -> TokenType:
        return self.op_token

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        val = self.operand.evaluate(env)
        if self.op_token.token in (Token.NOT_LOGIC, Token.LOGIC_NOT, Token.EXCLAMATION) or self.op in ("!", "not"):
            return 1 if not val else 0
        if self.op_token.token == Token.MINUS or self.op == "-":
            return -val
        if self.op_token.token == Token.NOT or self.op == "~":
            return ~int(val)
        return +val

    def to_tokens(self) -> list[TokenType]:
        return [self.op_token] + self.operand.to_tokens()

    def __str__(self) -> str:
        return f"{self.op}{self.operand}"

    def __repr__(self) -> str:
        return f"Unary({self.op}, {self.operand!r})"


class BinaryOpNode(ArithmeticNode):
    def __init__(self, op_token: Any, left: Any, right: Any):
        if isinstance(op_token, TokenType):
            self.op_token = op_token
            self.op = str(op_token.value) if op_token.value is not None else op_token.token.name
        else:
            self.op = str(getattr(op_token, "value", op_token))
            self.op_token = TokenType(token=Token.IDENT, value=self.op, line=1, col=0)

        self.left = to_arithmetic_node(left)
        self.right = to_arithmetic_node(right)

    @property
    def op1(self) -> ArithmeticNode:
        return self.left

    @property
    def op2(self) -> ArithmeticNode:
        return self.right

    @property
    def operator(self) -> TokenType:
        return self.op_token

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        active_env = env if env is not None else {}
        left_val = self.left.evaluate(active_env) if self.op != "=" else None
        right_val = self.right.evaluate(active_env)
        tok = self.op_token.token
        op = self.op

        # Asignación (a = b)
        if tok == Token.ASSIGN or op == "=":
            if isinstance(self.left, VariableNode):
                active_env[self.left.name] = right_val
            return right_val

        # Aritmética
        if tok == Token.PLUS or op == "+":
            return left_val + right_val
        elif tok == Token.MINUS or op == "-":
            return left_val - right_val
        elif tok == Token.STAR or op == "*":
            return left_val * right_val
        elif tok == Token.SLASH or op == "/":
            if right_val == 0:
                raise ZeroDivisionError("División por cero en expresión aritmética.")
            return left_val / right_val
        elif tok == Token.FLOOR_DIV or op == "//":
            if right_val == 0:
                raise ZeroDivisionError("División entera por cero en expresión aritmética.")
            return left_val // right_val
        elif tok == Token.PERCENT or op == "%":
            if right_val == 0:
                raise ZeroDivisionError("Módulo por cero en expresión aritmética.")
            return left_val % right_val
        elif tok == Token.POW or op in ("**", "^"):
            return left_val ** right_val

        # Comparaciones relacionales
        elif tok == Token.EQUAL or op == "==":
            return 1 if left_val == right_val else 0
        elif tok == Token.NOT_EQUAL or op == "!=":
            return 1 if left_val != right_val else 0
        elif tok == Token.LESS or op == "<":
            return 1 if left_val < right_val else 0
        elif tok == Token.LESS_EQUAL or op == "<=":
            return 1 if left_val <= right_val else 0
        elif tok == Token.GREATER or op == ">":
            return 1 if left_val > right_val else 0
        elif tok == Token.GREATER_EQUAL or op == ">=":
            return 1 if left_val >= right_val else 0

        # Operaciones lógicas
        elif tok in (Token.LOGIC_AND, Token.AND_LOGIC) or op in ("&&", "and"):
            return 1 if (bool(left_val) and bool(right_val)) else 0
        elif tok in (Token.LOGIC_OR, Token.OR_LOGIC) or op in ("||", "or"):
            return 1 if (bool(left_val) or bool(right_val)) else 0

        # Operaciones a nivel de bits
        elif tok == Token.AND or op == "&":
            return int(left_val) & int(right_val)
        elif tok == Token.OR or op == "|":
            return int(left_val) | int(right_val)
        elif tok == Token.XOR or op == "^":
            return int(left_val) ^ int(right_val)
        elif tok == Token.SHL or op == "<<":
            return int(left_val) << int(right_val)
        elif tok == Token.SHR or op == ">>":
            return int(left_val) >> int(right_val)
        else:
            raise ArithmeticSyntaxError(f"Operador binario desconocido '{self.op}'.")

    def to_tokens(self) -> list[TokenType]:
        return self.left.to_tokens() + [self.op_token] + self.right.to_tokens()

    def __str__(self) -> str:
        return f"({self.left} {self.op} {self.right})"

    def __repr__(self) -> str:
        return f"({self.left} {self.op} {self.right})"


class FunctionCallNode(ArithmeticNode):
    """Nodo para llamadas a funciones matemáticas en expresiones: sqrt(16), max(1, 2)."""
    def __init__(
        self,
        func_token: TokenType,
        args: list[ArithmeticNode],
        lparen: TokenType | None = None,
        commas: list[TokenType] | None = None,
        rparen: TokenType | None = None,
    ):
        self.func_token = func_token
        self.name: str = str(func_token.value)
        self.args: list[ArithmeticNode] = [to_arithmetic_node(a) for a in args]
        self.lparen = lparen
        self.commas = commas or []
        self.rparen = rparen

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        active_env = {**DEFAULT_ENV, **(env or {})}
        if self.name not in active_env:
            raise NameError(f"Función matemática '{self.name}' no encontrada en el entorno.")
        func = active_env[self.name]
        evaluated_args = [arg.evaluate(active_env) for arg in self.args]
        return func(*evaluated_args)

    def to_tokens(self) -> list[TokenType]:
        lparen = self.lparen or TokenType(
            token=Token.LPAREN, value="(", line=self.func_token.line, col=self.func_token.col + len(self.name)
        )
        rparen = self.rparen or TokenType(
            token=Token.RPAREN, value=")", line=lparen.line, col=lparen.col + 1
        )
        toks = [self.func_token, lparen]
        for index, arg in enumerate(self.args):
            if index > 0:
                comma = (
                    self.commas[index - 1]
                    if index - 1 < len(self.commas)
                    else TokenType(token=Token.COMMA, value=",", line=lparen.line, col=lparen.col + index)
                )
                toks.append(comma)
            toks.extend(arg.to_tokens())
        toks.append(rparen)
        return toks

    def __str__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        return f"{self.name}({args_str})"

    def __repr__(self) -> str:
        return str(self)


class GroupNode(ArithmeticNode):
    def __init__(self, lparen: TokenType, expr: ArithmeticNode, rparen: TokenType):
        self.lparen = lparen
        self.expr = to_arithmetic_node(expr)
        self.rparen = rparen

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        return self.expr.evaluate(env)

    def to_tokens(self) -> list[TokenType]:
        return [self.lparen] + self.expr.to_tokens() + [self.rparen]

    def __str__(self) -> str:
        return f"({self.expr})"

    def __repr__(self) -> str:
        return f"({self.expr})"


class ExpressionASTNode(ASTNode):
    """AST node projected from a typed expression node."""

    def __init__(
        self,
        name: str,
        expression: ArithmeticNode,
        level: int = 0,
        tokens: list[TokenType] | None = None,
        attributes: dict[str, Any] | None = None,
        children: list[ExpressionASTNode] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            level=level,
            tokens=tokens or [],
            attributes=attributes or {},
            no_simplify=True,
        )
        self.expression = expression
        for child in children or []:
            self.add_child(child)

    def evaluate(self, env: dict[str, Any] | None = None) -> Any:
        return self.expression.evaluate(env)


class OpNode(ExpressionASTNode):
    """Processable AST operation exposing operands and its source operator token."""

    def __init__(
        self,
        expression: BinaryOpNode | UnaryOpNode,
        level: int,
        op1: ExpressionASTNode,
        op2: ExpressionASTNode | None,
    ) -> None:
        super().__init__(
            name="Op",
            expression=expression,
            level=level,
            tokens=[expression.op_token],
            attributes={
                "operator": expression.op,
                "operator_type": expression.op_token.token.name,
                "arity": 2 if op2 is not None else 1,
            },
            children=[op1] if op2 is None else [op1, op2],
        )

    @property
    def op1(self) -> ExpressionASTNode:
        return self.children[0]

    @property
    def op2(self) -> ExpressionASTNode | None:
        return self.children[1] if len(self.children) > 1 else None

    @property
    def operator(self) -> TokenType:
        return self.tokens[0]


def arithmetic_to_ast_node(
    expression: ArithmeticNode,
    rule: Any = None,
    level: int = 0,
) -> ExpressionASTNode:
    """Convert the typed evaluator tree to a recursively structured AST."""
    if isinstance(expression, BinaryOpNode):
        return OpNode(
            expression,
            level,
            arithmetic_to_ast_node(expression.left, level=level + 1),
            arithmetic_to_ast_node(expression.right, level=level + 1),
        )
    if isinstance(expression, UnaryOpNode):
        return OpNode(
            expression,
            level,
            arithmetic_to_ast_node(expression.operand, level=level + 1),
            None,
        )
    if isinstance(expression, FunctionCallNode):
        syntax_tokens = expression.to_tokens()
        punctuation = [
            token
            for token in syntax_tokens
            if token.token in (Token.LPAREN, Token.COMMA, Token.RPAREN)
        ]
        return ExpressionASTNode(
            name="Call",
            expression=expression,
            level=level,
            tokens=[expression.func_token, *punctuation],
            attributes={"function": expression.name, "argument_count": len(expression.args)},
            children=[
                arithmetic_to_ast_node(arg, level=level + 1)
                for arg in expression.args
            ],
        )
    if isinstance(expression, GroupNode):
        return ExpressionASTNode(
            name="Group",
            expression=expression,
            level=level,
            tokens=[expression.lparen, expression.rparen],
            children=[
                arithmetic_to_ast_node(expression.expr, level=level + 1)
            ],
        )
    if isinstance(expression, NumberNode):
        return ExpressionASTNode(
            name="Number",
            expression=expression,
            level=level,
            tokens=[expression.token],
            attributes={"value": expression.value},
        )
    if isinstance(expression, BooleanNode):
        return ExpressionASTNode(
            name="Boolean",
            expression=expression,
            level=level,
            tokens=[expression.token],
            attributes={"value": expression.value},
        )
    if isinstance(expression, VariableNode):
        return ExpressionASTNode(
            name="Identifier",
            expression=expression,
            level=level,
            tokens=[expression.token],
            attributes={"identifier": expression.name},
        )
    raise TypeError(f"Tipo de nodo aritmético no soportado: {type(expression).__name__}")


# ============================================================================
# Precedencias de Operadores
# ============================================================================

BINARY_PRECEDENCE: dict[Token, int] = {
    Token.LOGIC_OR: 3,
    Token.OR_LOGIC: 3,
    Token.LOGIC_AND: 4,
    Token.AND_LOGIC: 4,
    Token.ASSIGN: 5,
    Token.OR: 6,
    Token.XOR: 6,
    Token.AND: 6,
    Token.EQUAL: 7,
    Token.NOT_EQUAL: 7,
    Token.LESS: 8,
    Token.LESS_EQUAL: 8,
    Token.GREATER: 8,
    Token.GREATER_EQUAL: 8,
    Token.SHL: 9,
    Token.SHR: 9,
    Token.PLUS: 10,
    Token.MINUS: 10,
    Token.STAR: 20,
    Token.SLASH: 20,
    Token.FLOOR_DIV: 20,
    Token.PERCENT: 20,
    Token.POW: 30,
}

UNARY_PRECEDENCE = 25


def is_binary_op(tok: Token) -> bool:
    return tok in BINARY_PRECEDENCE


def is_right_associative(tok: Token) -> bool:
    return tok in (Token.POW, Token.ASSIGN)


# ============================================================================
# Parser de Expresiones Aritméticas (Pratt Parsing)
# ============================================================================

class ArithmeticParser:
    """
    Parser descendente recursivo con algoritmo de precedencia de operadores
    (Pratt Parser) para consumir expresiones aritméticas desde una lista de tokens.
    """

    def __init__(
        self,
        tokens: list[TokenType],
        pos: int = 0,
        allow_logical: bool = True,
        allow_ident: bool = True,
    ):
        self.tokens = tokens
        self.pos = pos
        self.allow_logical = allow_logical
        self.allow_ident = allow_ident

    def peek(self) -> TokenType | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self) -> TokenType:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse_expression(self, min_prec: int = 0) -> ArithmeticNode:
        left = self.parse_prefix()

        while True:
            current = self.peek()
            if current is None:
                break

            tok_type = current.token
            if not is_binary_op(tok_type):
                break
            if not self.allow_logical and tok_type in (
                Token.LOGIC_AND,
                Token.AND_LOGIC,
                Token.LOGIC_OR,
                Token.OR_LOGIC,
            ):
                break

            prec = BINARY_PRECEDENCE[tok_type]
            if prec < min_prec:
                break

            op_tok = self.consume()
            next_prec = prec if is_right_associative(tok_type) else prec + 1
            right = self.parse_expression(next_prec)
            left = BinaryOpNode(op_tok, left, right)

        return left

    def parse_prefix(self) -> ArithmeticNode:
        current = self.peek()
        if current is None:
            raise ArithmeticSyntaxError("Fin inesperado de entrada en expresión aritmética.")

        tok_type = current.token

        if tok_type in (Token.PLUS, Token.MINUS, Token.NOT, Token.NOT_LOGIC, Token.LOGIC_NOT, Token.EXCLAMATION):
            op_tok = self.consume()
            operand = self.parse_expression(UNARY_PRECEDENCE)
            return UnaryOpNode(op_tok, operand)

        if tok_type == Token.BOOL or isinstance(current.value, bool):
            bool_tok = self.consume()
            return BooleanNode(bool_tok)

        if tok_type == Token.DECREMENT:
            dec_tok = self.consume()
            minus1 = TokenType(token=Token.MINUS, value="-", line=dec_tok.line - 1, col=dec_tok.col)
            minus2 = TokenType(token=Token.MINUS, value="-", line=dec_tok.line - 1, col=dec_tok.col + 1)
            operand = self.parse_expression(UNARY_PRECEDENCE)
            return UnaryOpNode(minus1, UnaryOpNode(minus2, operand))

        if tok_type == Token.INCREMENT:
            inc_tok = self.consume()
            plus1 = TokenType(token=Token.PLUS, value="+", line=inc_tok.line - 1, col=inc_tok.col)
            plus2 = TokenType(token=Token.PLUS, value="+", line=inc_tok.line - 1, col=inc_tok.col + 1)
            operand = self.parse_expression(UNARY_PRECEDENCE)
            return UnaryOpNode(plus1, UnaryOpNode(plus2, operand))

        if tok_type == Token.LPAREN:
            lparen = self.consume()
            expr = self.parse_expression(0)
            closing = self.peek()
            if closing is None or closing.token != Token.RPAREN:
                col = closing.col if closing else "EOF"
                line = closing.line if closing else "EOF"
                raise ArithmeticSyntaxError(
                    f"Se esperaba ')' para cerrar paréntesis abierto en lín {lparen.line}, col {lparen.col}. "
                    f"Encontrado: {closing.token.name if closing else 'EOF'} en lín {line}, col {col}."
                )
            rparen = self.consume()
            return GroupNode(lparen, expr, rparen)

        if tok_type == Token.NUMBER or isinstance(current.value, (int, float)):
            num_tok = self.consume()
            return NumberNode(num_tok)

        if tok_type == Token.IDENT:
            if not self.allow_ident:
                raise ArithmeticSyntaxError(
                    f"Identificadores no permitidos: {current.value!r}."
                )
            var_tok = self.consume()
            if self.peek() and self.peek().token == Token.LPAREN:
                lparen = self.consume()
                args: list[ArithmeticNode] = []
                commas: list[TokenType] = []
                if self.peek() and self.peek().token != Token.RPAREN:
                    args.append(self.parse_expression(0))
                    while self.peek() and self.peek().token == Token.COMMA:
                        commas.append(self.consume())
                        args.append(self.parse_expression(0))
                if not self.peek() or self.peek().token != Token.RPAREN:
                    raise ArithmeticSyntaxError(f"Se esperaba ')' tras argumentos de '{var_tok.value}'.")
                rparen = self.consume()
                return FunctionCallNode(var_tok, args, lparen, commas, rparen)
            return VariableNode(var_tok)

        raise ArithmeticSyntaxError(
            f"Token inesperado '{current.value}' ({tok_type.name}) al inicio de término aritmético en lín {current.line}, col {current.col}."
        )


def parse_tokens(tokens: list[TokenType], start_pos: int = 0) -> tuple[ArithmeticNode, int]:
    """
    Parsea una expresión aritmética desde una lista de tokens a partir de start_pos.
    Retorna (nodo_ast, nueva_posicion).
    """
    clean_tokens: list[TokenType] = []
    idx = start_pos
    while idx < len(tokens):
        t = tokens[idx]
        if t.token in (Token.EOF, Token.NEWLINE, Token.EMPTY_LINE):
            break
        clean_tokens.append(t)
        idx += 1

    parser = ArithmeticParser(clean_tokens, 0)
    ast = parser.parse_expression(0)
    return ast, start_pos + parser.pos


def evaluate(
    expr: str | ASTNode | ArithmeticNode | list[TokenType],
    env: dict[str, Any] | None = None,
) -> Any:
    """
    Evalúa una expresión aritmética en texto, tokens o ASTNode, retornando el valor numérico.
    """
    active_env = {**DEFAULT_ENV, **(env or {})}

    if isinstance(expr, ExpressionASTNode):
        return expr.evaluate(active_env)

    if isinstance(expr, ArithmeticNode):
        return expr.evaluate(active_env)

    if isinstance(expr, str):
        from gram.core.lexer import Lexer, word
        if word.count_keywords() == 0:
            word.add_keyword("math_expr_kw", "#ffffff")
        lines = expr.splitlines() or [expr]
        lexer = Lexer(lines)
        tokens = lexer.process()
        usable_tokens = [t for t in tokens if t.token not in (Token.EOF, Token.NEWLINE, Token.EMPTY_LINE)]
        if not usable_tokens:
            raise ArithmeticSyntaxError("La expresión aritmética está vacía.")
        parser = ArithmeticParser(usable_tokens)
        node = parser.parse_expression(0)
        if parser.pos < len(usable_tokens):
            remaining = usable_tokens[parser.pos]
            raise ArithmeticSyntaxError(f"Tokens no consumidos tras expresión: {remaining.token.name} ({remaining.value})")
        return node.evaluate(active_env)

    if isinstance(expr, list) and all(isinstance(t, TokenType) for t in expr):
        usable_tokens = [t for t in expr if t.token not in (Token.EOF, Token.NEWLINE, Token.EMPTY_LINE)]
        parser = ArithmeticParser(usable_tokens)
        node = parser.parse_expression(0)
        return node.evaluate(active_env)

    if isinstance(expr, ASTNode):
        tokens = list(expr.tokens)
        if not tokens:
            for child in expr.walk():
                if child is not expr and child.tokens:
                    tokens.extend(child.tokens)
        if tokens:
            return evaluate(tokens, active_env)
        raise ArithmeticSyntaxError(f"ASTNode '{expr.name}' no contiene tokens para evaluar.")

    raise TypeError(f"Tipo no soportado para evaluación aritmética: {type(expr)}")


__all__ = [
    "ArithmeticNode",
    "BooleanNode",
    "NumberNode",
    "VariableNode",
    "UnaryOpNode",
    "BinaryOpNode",
    "FunctionCallNode",
    "GroupNode",
    "ArithmeticParser",
    "ArithmeticSyntaxError",
    "DEFAULT_ENV",
    "evaluate",
    "parse_tokens",
    "to_arithmetic_node",
]
