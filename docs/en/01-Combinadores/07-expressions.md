# Pratt Expression Combinators

Gram includes a single-pass Top-Down Operator Precedence (**Pratt parsing**) engine capable of handling arithmetic, bitwise, relational, and logical expressions with native operator precedence and associativity.

---

## 1. Core Concepts & Precedence Table

The Pratt engine uses static binding power tables where higher numbers bind more tightly:

| Precedence ($p$) | Operators | Associativity | Category |
| :---: | :---: | :---: | :---: |
| **150** | `+`, `-`, `~`, `++`, `--`, `sqrt` | Prefix Unary | Arithmetic / Bitwise |
| **80** | `**` (`Token.POW`) | Right-associative | Exponentiation |
| **70** | `*`, `/`, `//`, `%` | Left-associative | Multiplicative |
| **60** | `+`, `-` | Left-associative | Additive |
| **50** | `<<`, `>>` | Left-associative | Bitwise Shifts |
| **45** | `&` | Left-associative | Bitwise AND |
| **40** | `^` | Left-associative | Bitwise XOR |
| **35** | `\|` | Left-associative | Bitwise OR |
| **30** | `==`, `!=`, `<`, `<=`, `>`, `>=` | Left-associative | Relational / Equality |
| **20** | `&&`, `and` | Left-associative | Logical AND |
| **15** | `\|\|`, `or` | Left-associative | Logical OR |

Parentheses `(...)` automatically override operator binding powers.

---

## 2. Combinator Types

### A. `ArithmeticExpr`
Parses mathematical, unary, and bitwise expressions:
```python
ArithmeticExpr(*values: Token | str | Ref | type[RuleItem])
```

### B. `ConditionalExpr`
Parses boolean, relational, and logical expressions:
```python
ConditionalExpr(*values: Token | str | Ref | type[RuleItem])
```

### C. `DualExpr`
Unifies both arithmetic and conditional operators into a single combined Pratt grammar (e.g., `x + 5 >= 10 && !flag`):
```python
DualExpr(*values: Token | str | Ref | type[RuleItem])
```

---

## 3. Allowed Operand Values (`values`)

The `values` parameter specifies what operands can appear as atoms:
1. `Token` members: e.g., `Token.NUMBER`, `Token.IDENT`, `Token.STRING`, `Token.BOOL`.
2. `Ref` combinators: e.g., `combinators.Ref(CALL_DECL, name="Call")`.
3. `RuleItem` classes with `nodeable = True`.

---

## 4. Return Shapes

- **Single Atom**: If an expression consists of a single operand without operators, returns the terminal AST node directly (e.g., `LiteralNumber`, `Identifier`).
- **Binary Operation**: Returns an [`ASTBinaryOp`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/combinators/expressions.py#L137) node:
  - `.left`: Left operand AST node.
  - `.operator`: Binary operator `TokenType`.
  - `.right`: Right operand AST node.
- **Unary Operation**: Returns an [`ASTUnaryOp`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/combinators/expressions.py#L118) node:
  - `.operator`: Unary operator `TokenType`.
  - `.operand`: Target operand AST node.

---

## 5. Usage Example

```python
from gram import combinators
from gram.core.lexer import Token

class FUNCTION_CALL(combinators.RuleItem):
    nodeable = True
    # Function call syntax...

# Expression combining literals, identifiers, and function call rules
full_expr = combinators.DualExpr(
    Token.NUMBER,
    Token.IDENT,
    Token.STRING,
    Token.BOOL,
    combinators.Ref(FUNCTION_CALL),
)
```

### Parsing Execution
Given the input: `10 + 20 * 30`:
- Evaluates `20 * 30` first due to higher binding power (`p=70` vs `p=60`).
- Produces `ASTBinaryOp(left=10, op='+', right=ASTBinaryOp(left=20, op='*', right=30))`.

Given parenthesized input: `(10 + 20) * 30`:
- Enclosed parentheses force `10 + 20` to be evaluated first as the left operand.
