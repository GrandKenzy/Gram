# Pratt Expression Combinators

`gram.core.combinators.expressions` provides a Top-Down Operator Precedence (**Pratt**) parser for prefix unary and infix binary expressions with parenthesized grouping (`Token.LPAREN` ... `Token.RPAREN`).

---

## 1. Operator Precedence & Binding Power Tables

Binding power helpers:
- `bind_left(p: int) -> tuple[int, int]`: returns `(2 * p, 2 * p + 1)` for left-associative binary operators `((a op b) op c)`.
- `bind_right(p: int) -> tuple[int, int]`: returns `(2 * p, 2 * p - 1)` for right-associative binary operators `(a op (b op c))`.

### Prefix Unary Operators (`right_bp`)

| Dictionary | Tokens | Symbols / Lexemes | `right_bp` |
| :--- | :--- | :--- | :---: |
| `ARITHMETIC_UNARY_OPS` | `Token.PLUS`, `Token.MINUS`, `Token.NOT`, `Token.INCREMENT`, `Token.DECREMENT`, `Token.SQRT` | `+`, `-`, `~`, `++`, `--`, `√` | **150** |
| `CONDITIONAL_UNARY_OPS` | `Token.NOT_LOGIC`, `Token.LOGIC_NOT`, `Token.EXCLAMATION` | `not`, `!` | **50** |

### Infix Binary Operators (`(left_bp, right_bp)`)

| Dictionary | Precedence $p$ | `(left_bp, right_bp)` | Associativity | Tokens (`MAP_SYMBOLS`) |
| :--- | :---: | :---: | :---: | :--- |
| `ARITHMETIC_BINARY_OPS` | **80** | `(160, 159)` | Right | `Token.POW` (`**`) |
| `ARITHMETIC_BINARY_OPS` | **70** | `(140, 141)` | Left | `Token.STAR` (`*`), `Token.SLASH` (`/`), `Token.FLOOR_DIV` (`//`), `Token.PERCENT` (`%`) |
| `ARITHMETIC_BINARY_OPS` | **60** | `(120, 121)` | Left | `Token.PLUS` (`+`), `Token.MINUS` (`-`) |
| `ARITHMETIC_BINARY_OPS` | **50** | `(100, 101)` | Left | `Token.SHL` (`<<`), `Token.SHR` (`>>`) |
| `ARITHMETIC_BINARY_OPS` | **45** | `(90, 91)` | Left | `Token.AND` (`&`) |
| `ARITHMETIC_BINARY_OPS` | **40** | `(80, 81)` | Left | `Token.XOR` (`^`) |
| `ARITHMETIC_BINARY_OPS` | **35** | `(70, 71)` | Left | `Token.OR` (`\|`) |
| `CONDITIONAL_BINARY_OPS` | **30** | `(60, 61)` | Left | `Token.EQUAL` (`==`), `Token.NOT_EQUAL` (`!=`), `Token.LESS` (`<`), `Token.LESS_EQUAL` (`<=`), `Token.GREATER` (`>`), `Token.GREATER_EQUAL` (`>=`) |
| `CONDITIONAL_BINARY_OPS` | **20** | `(40, 41)` | Left | `Token.AND_LOGIC` (`&&`), `Token.LOGIC_AND` (`and`) |
| `CONDITIONAL_BINARY_OPS` | **15** | `(30, 31)` | Left | `Token.OR_LOGIC` (`\|\|`), `Token.LOGIC_OR` (`or`) |

`DUAL_BINARY_OPS` and `DUAL_UNARY_OPS` are `ChainMap` views combining the conditional and arithmetic operator dictionaries.

---

## 2. Expression Combinator Classes

All three classes inherit from `BaseExpr` and share the same constructor signature:

```python
ArithmeticExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
ConditionalExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
DualExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
```

- **`ArithmeticExpr`:** Uses `ARITHMETIC_BINARY_OPS` and `ARITHMETIC_UNARY_OPS`.
- **`ConditionalExpr`:** Uses `CONDITIONAL_BINARY_OPS` and `CONDITIONAL_UNARY_OPS`.
- **`DualExpr`:** Uses `DUAL_BINARY_OPS` and `DUAL_UNARY_OPS` so arithmetic and comparison/logical operators can be mixed in a single expression (e.g., `x + 1 >= 10 && !done`).

---

## 3. Allowed Operand Specifications (`*values`)

When `*values` is omitted, `BaseExpr` defaults to `(Token.NUMBER, Token.IDENT)`.

Each item passed in `*values` (or inside an iterable passed to `*values`) is validated at construction time:
1. **`Token` enum member** (or valid `Token` name/symbol `str`, e.g., `"NUMBER"`): Matched as a terminal token atom (note: `Token.KEYWORD` tokens are never matched as token atoms).
2. **`RuleItem` subclass with `nodeable = True`:** Automatically wrapped in `Ref(rule)`.
3. **`Ref` combinator with a non-empty `.name`:** Evaluated speculatively inside `analyzer.failure_scope()` before falling back to token atoms. Passing a `Ref` with `name=None` and `nodeable=False` raises `UnnamedRefInExpr` (`GrammarError`).

Expression references with an exact, non-nullable, side-effect-free static
first-token set use a cached dispatch filter before speculative evaluation.
Declared reference order is preserved, ambiguous references remain in the
fallback path, and references that can begin with `LPAREN` are still tried
before native grouping when `refs_before_grouping=True`. Parser-local logical
token conversions are applied when classifying atoms and operators.

Invalid string names raise `InvalidExprTokenName`; any other type raises `UnsupportedExprOperand`.

### Parenthesized Grouping
Parentheses (`Token.LPAREN` ... `Token.RPAREN`) are handled natively at atom positions:
- Enters bracket-aware whitespace mode (`parser.enter_delimiter()` / `parser.skip_whitespace()`), so `NEWLINE`, `INDENT`, and `DEDENT` inside `(...)` are skipped.
- Empty parentheses `()` fail and report `EmptyParenthesesInExpr`.
- Missing `)` reports `UnclosedExprParenEOF` or `UnclosedExprParenMismatch`.

---

## 4. Return Shapes

- **Single Atom:** Returns the atom's `ASTNode` directly (`LiteralNumber`, `Identifier`, `ASTRef`, etc.).
- **Prefix Unary Operation:** Returns `ASTUnaryOp(operator: TokenType, operand: ASTNode)` (`gram.core.combinators.expressions.ASTUnaryOp`).
- **Infix Binary Operation:** Returns `ASTBinaryOp(left: ASTNode, operator: TokenType, right: ASTNode)` (`gram.core.combinators.expressions.ASTBinaryOp`).

---

## 5. Example

```python
from gram.core.combinators import DualExpr, Enclosed, MatchToken, Ref, RuleItem, Separator, Seq
from gram.core.lexer import Token

class FuncCall(RuleItem):
    nodeable = True
    entrypoint = Seq(
        MatchToken(Token.IDENT),
        Enclosed(
            open=Token.LPAREN,
            content=Separator(values=[Token.IDENT, Token.NUMBER], sep=Token.COMMA),
            close=Token.RPAREN,
        ),
    )

# Evaluates FuncCall first (Ref atoms are tried before bare Token atoms),
# then falls back to IDENT, NUMBER, STRING, or BOOL.
expr = DualExpr(
    Ref(FuncCall),
    Token.IDENT,
    Token.NUMBER,
    Token.STRING,
    Token.BOOL,
)
```
