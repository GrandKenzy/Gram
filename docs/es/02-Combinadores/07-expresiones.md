# Combinadores de Expresiones Pratt

`gram.core.combinators.expressions` proporciona un parser de precedencia de operadores descendente (**Pratt**) para expresiones unarias prefijas y binarias infijas con agrupación entre paréntesis (`Token.LPAREN` ... `Token.RPAREN`).

---

## 1. Tablas de Precedencia y Poder de Enlace (*Binding Power*)

Funciones auxiliares de poder de enlace:
- `bind_left(p: int) -> tuple[int, int]`: retorna `(2 * p, 2 * p + 1)` para operadores binarios asociativos por la izquierda `((a op b) op c)`.
- `bind_right(p: int) -> tuple[int, int]`: retorna `(2 * p, 2 * p - 1)` para operadores binarios asociativos por la derecha `(a op (b op c))`.

### Operadores Unarios Prefijos (`right_bp`)

| Diccionario | Tokens | Símbolos / Lexemas | `right_bp` |
| :--- | :--- | :--- | :---: |
| `ARITHMETIC_UNARY_OPS` | `Token.PLUS`, `Token.MINUS`, `Token.NOT`, `Token.INCREMENT`, `Token.DECREMENT`, `Token.SQRT` | `+`, `-`, `~`, `++`, `--`, `√` | **150** |
| `CONDITIONAL_UNARY_OPS` | `Token.NOT_LOGIC`, `Token.LOGIC_NOT`, `Token.EXCLAMATION` | `not`, `!` | **50** |

### Operadores Binarios Infijos (`(left_bp, right_bp)`)

| Diccionario | Precedencia $p$ | `(left_bp, right_bp)` | Asociatividad | Tokens (`MAP_SYMBOLS`) |
| :--- | :---: | :---: | :---: | :--- |
| `ARITHMETIC_BINARY_OPS` | **80** | `(160, 159)` | Derecha | `Token.POW` (`**`) |
| `ARITHMETIC_BINARY_OPS` | **70** | `(140, 141)` | Izquierda | `Token.STAR` (`*`), `Token.SLASH` (`/`), `Token.FLOOR_DIV` (`//`), `Token.PERCENT` (`%`) |
| `ARITHMETIC_BINARY_OPS` | **60** | `(120, 121)` | Izquierda | `Token.PLUS` (`+`), `Token.MINUS` (`-`) |
| `ARITHMETIC_BINARY_OPS` | **50** | `(100, 101)` | Izquierda | `Token.SHL` (`<<`), `Token.SHR` (`>>`) |
| `ARITHMETIC_BINARY_OPS` | **45** | `(90, 91)` | Izquierda | `Token.AND` (`&`) |
| `ARITHMETIC_BINARY_OPS` | **40** | `(80, 81)` | Izquierda | `Token.XOR` (`^`) |
| `ARITHMETIC_BINARY_OPS` | **35** | `(70, 71)` | Izquierda | `Token.OR` (`\|`) |
| `CONDITIONAL_BINARY_OPS` | **30** | `(60, 61)` | Izquierda | `Token.EQUAL` (`==`), `Token.NOT_EQUAL` (`!=`), `Token.LESS` (`<`), `Token.LESS_EQUAL` (`<=`), `Token.GREATER` (`>`), `Token.GREATER_EQUAL` (`>=`) |
| `CONDITIONAL_BINARY_OPS` | **20** | `(40, 41)` | Izquierda | `Token.AND_LOGIC` (`&&`), `Token.LOGIC_AND` (`and`) |
| `CONDITIONAL_BINARY_OPS` | **15** | `(30, 31)` | Izquierda | `Token.OR_LOGIC` (`\|\|`), `Token.LOGIC_OR` (`or`) |

`DUAL_BINARY_OPS` y `DUAL_UNARY_OPS` son vistas `ChainMap` que combinan los diccionarios de operadores condicionales y aritméticos.

---

## 2. Clases de Combinadores de Expresión

Las tres clases heredan de `BaseExpr` y comparten la misma firma de constructor:

```python
ArithmeticExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
ConditionalExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
DualExpr(*values: Token | str | Ref | type[RuleItem] | Iterable[...])
```

- **`ArithmeticExpr`:** Utiliza `ARITHMETIC_BINARY_OPS` y `ARITHMETIC_UNARY_OPS`.
- **`ConditionalExpr`:** Utiliza `CONDITIONAL_BINARY_OPS` y `CONDITIONAL_UNARY_OPS`.
- **`DualExpr`:** Utiliza `DUAL_BINARY_OPS` y `DUAL_UNARY_OPS`, lo que permite mezclar operadores aritméticos, comparativos y lógicos en una sola expresión (por ejemplo, `x + 1 >= 10 && !done`).

---

## 3. Especificaciones de Operandos Permitidos (`*values`)

Cuando se omite `*values`, `BaseExpr` toma por defecto `(Token.NUMBER, Token.IDENT)`.

Cada elemento pasado en `*values` (o dentro de un iterable pasado a `*values`) se valida en tiempo de construcción:
1. **Miembro del enum `Token`** (o cadena válida con nombre/símbolo de `Token`, ej.: `"NUMBER"`): Coincide como un átomo de token terminal (nota: los tokens `Token.KEYWORD` nunca coinciden como átomos de token).
2. **Subclase de `RuleItem` con `nodeable = True`:** Envuelto automáticamente en `Ref(rule)`.
3. **Combinador `Ref` con `.name` no vacío:** Evaluado especulativamente dentro de `analyzer.failure_scope()` antes de retroceder a átomos de token. Pasar un `Ref` con `name=None` y `nodeable=False` lanza `UnnamedRefInExpr` (`GrammarError`).

Nombres de cadena no válidos lanzan `InvalidExprTokenName`; cualquier otro tipo lanza `UnsupportedExprOperand`.

### Agrupación Entre Paréntesis
Los paréntesis (`Token.LPAREN` ... `Token.RPAREN`) se gestionan de forma nativa en posiciones de átomo:
- Entra en modo de espacios en blanco conscientes de delimitadores (`parser.enter_delimiter()` / `parser.skip_whitespace()`), de modo que `NEWLINE`, `INDENT` y `DEDENT` dentro de `(...)` se omiten.
- Paréntesis vacíos `()` fallan y reportan `EmptyParenthesesInExpr`.
- La ausencia de `)` reporta `UnclosedExprParenEOF` o `UnclosedExprParenMismatch`.

---

## 4. Formas de Retorno

- **Átomo Individual:** Retorna el nodo `ASTNode` del átomo directamente (`LiteralNumber`, `Identifier`, `ASTRef`, etc.).
- **Operación Unaria Prefija:** Retorna `ASTUnaryOp(operator: TokenType, operand: ASTNode)` (`gram.core.combinators.expressions.ASTUnaryOp`).
- **Operación Binaria Infija:** Retorna `ASTBinaryOp(left: ASTNode, operator: TokenType, right: ASTNode)` (`gram.core.combinators.expressions.ASTBinaryOp`).

---

## 5. Ejemplo

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

# Evalúa FuncCall primero (los átomos Ref se prueban antes que los átomos Token desnudos),
# y luego retrocede a IDENT, NUMBER, STRING o BOOL.
expr = DualExpr(
    Ref(FuncCall),
    Token.IDENT,
    Token.NUMBER,
    Token.STRING,
    Token.BOOL,
)
```
