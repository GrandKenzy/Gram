# Fluent Validation Combinator (`Req`)

The `Req` combinator provides a fluent API for validating, constraining, and transforming the token currently under the parser cursor before delegating it to the AST.

---

## 1. Overview and Constructor

```python
Req(target_token: Token | CustomToken | str)
```

- `target_token`: Expected token type (e.g., `Token.IDENT`, `Token.NUMBER`).

On execution, `Req` first validates that the current token matches `target_token`, applies each chained constraint in order, and then delegates the final (potentially transformed) token to the AST via `analyzer.delegate_return_node(token)`.

---

## 2. Validation Methods

All validation methods return `self` (`Req`) to allow method chaining.

### Casing & String Constraints
- `.is_lower()`: Requires the token string value to be completely lowercase.
- `.is_upper()`: Requires the token string value to be completely uppercase.
- `.is_snake_case()`: Requires snake_case formatting (`^[a-z0-9]+(_[a-z0-9]+)*$`).
- `.is_camel_case()`: Requires camelCase or PascalCase formatting.
- `.startswith(prefix: str)`: Requires the token value to begin with `prefix`.
- `.endswith(suffix: str)`: Requires the token value to end with `suffix`.
- `.contains(*items: str)`: Requires the token value to contain all specified substrings.
- `.excludes(*items: str)`: Requires the token value to contain none of the specified substrings.

### Length & Numeric Bounds
- `.length(n: int)`: Requires exact length of `n` characters.
- `.min(n: int | float)`: Enforces minimum numeric value or minimum string length.
- `.max(n: int | float)`: Enforces maximum numeric value or maximum string length.
- `.mindig(n: int)`: Requires at least `n` digit characters.
- `.maxdig(n: int)`: Requires at most `n` digit characters.
- `.equal(expected: Any)`: Requires strict equality with `expected`.
- `.unequal(not_expected: Any)`: Requires inequality with `not_expected`.

---

## 3. Transformation Methods

Transformations modify the cloned token's value before generating its AST node:

- `.apply_lower()`: Converts the token value to lowercase.
- `.apply_upper()`: Converts the token value to uppercase.
- `.apply_camel()`: Converts snake_case strings to CamelCase.
- `.apply_zfill(width: int)`: Left-pads numeric strings with zeros to `width`.
- `.replace(old: str, new: str)`: Replaces occurrences of `old` with `new`.
- `.change(new_val: Any)`: Overwrites the token value with `new_val`.
- `.addl(prefix: str)`: Prepends `prefix` to the token value.
- `.addr(suffix: str)`: Appends `suffix` to the token value.
- `.transform(fn: Callable[[Any], Any])`: Applies an arbitrary Python function to the token value.

---

## 4. Return Shape & Errors

### Return Shape
Returns the terminal AST node corresponding to `target_token` (e.g., `Identifier`, `LiteralNumber`, `LiteralString`).

### Errors Reported
- Reports `ReqTokenMismatch` if the active token type does not match `target_token`.
- Reports `ReqConstraintFailed` if any chained constraint method fails.
- Reports `ReqUnexpectedEOF` if the token stream ends prematurely.

---

## 5. Usage Example

```python
from gram import combinators
from gram.core.lexer import Token

# Requires a snake_case identifier with minimum 3 characters, converted to uppercase
constant_ident = (
    combinators.Req(Token.IDENT)
    .is_snake_case()
    .min(3)
    .apply_upper()
)

# Requires an integer between 10 and 100
bounded_number = (
    combinators.Req(Token.NUMBER)
    .min(10)
    .max(100)
)
```
