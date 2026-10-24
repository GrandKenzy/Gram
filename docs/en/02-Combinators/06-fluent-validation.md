# Fluent Validation Combinator (`Req`)

`Req` (`gram.core.combinators.req.Req`) validates that the token at `parser.pos` matches a target token type and runs a chain of validation and transformation functions on a shallow copy (`copy.copy`) of the token before delegating it to `analyzer.delegate_return_node(cloned_token)`.

---

## 1. Constructor

```python
Req(target_token: Token | CustomToken | str)
```

- `target_token`: Expected `Token` enum member, `CustomToken`, or token name string (`Token.IDENT`, `"IDENT"`, etc.).
- Each chained validation or transformation method appends an operation to `self._operations` and returns `self`.

---

## 2. Validation Methods

If any validation fails, `Req` leaves `parser.pos` unchanged, reports `ReqConstraintFailed` (`GrammarError`), and returns `None`.

### Case & Naming Format Checks
- `.is_lower()`: Requires `str(t.value).islower()` to be `True`.
- `.is_upper()`: Requires `str(t.value).isupper()` to be `True`.
- `.is_snake_case()`: Requires `val == val.lower()` and `" " not in val` (where `val = str(t.value)`).
- `.is_camel_case()`: Requires `val` to be non-empty, `val[0].isalpha()`, `"_" not in val`, and `" " not in val`.

### Prefix, Suffix & Substring Checks
- `.startswith(prefix: str)`: Requires `str(t.value).startswith(prefix)`.
- `.endswith(suffix: str)`: Requires `str(t.value).endswith(suffix)`.
- `.contains(*items: str)`: Requires every substring in `items` to appear in `str(t.value)`.
- `.excludes(*items: str)`: Requires none of the substrings in `items` to appear in `str(t.value)`.

### Length, Numeric Bounds & Equality
- `.length(n: int)`: Requires `len(str(t.value)) == n`.
- `.min(n: int | float)`:
  - If `isinstance(t.value, (int, float))`: requires `t.value >= n`.
  - Otherwise: requires `len(str(t.value)) >= n`.
- `.max(n: int | float)`:
  - If `isinstance(t.value, (int, float))`: requires `t.value <= n`.
  - Otherwise: requires `len(str(t.value)) <= n`.
- `.mindig(n: int)`: Requires at least `n` characters in `str(t.value)` to satisfy `char.isdigit()`.
- `.maxdig(n: int)`: Requires at most `n` characters in `str(t.value)` to satisfy `char.isdigit()`.
- `.equal(expected: Any)`: Requires `str(t.value) == str(expected)`.
- `.unequal(not_expected: Any)`: Requires `str(t.value) != str(not_expected)`.

---

## 3. Transformation Methods

Transformations mutate `cloned_token.value` in-place (without mutating the original token in `parser.tokens` if a subsequent step fails):

- `.apply_lower()`: Sets `t.value = str(t.value).lower()`.
- `.apply_upper()`: Sets `t.value = str(t.value).upper()`.
- `.apply_camel()`: Splits `str(t.value).replace("_", " ")` on whitespace and joins as `parts[0].lower() + "".join(x.title() for x in parts[1:])`.
- `.apply_zfill(width: int)`: Sets `t.value = str(t.value).zfill(width)`.
- `.replace(old: str, new: str)`: Sets `t.value = str(t.value).replace(old, new)`.
- `.change(new_val: Any)`: Sets `t.value = new_val`.
- `.addl(prefix: str)`: Sets `t.value = prefix + str(t.value)`.
- `.addr(suffix: str)`: Sets `t.value = str(t.value) + suffix`.
- `.transform(target_fn: Callable[[Any], Any])`: Sets `t.value = target_fn(t.value)`. If `target_fn` raises an exception, `Req` catches it and reports `ReqConstraintFailed`.

---

## 4. Return Shape & Diagnostics

- **Success:** Consumes the token from `parser` and returns `analyzer.delegate_return_node(cloned_token)` (`Identifier`, `LiteralNumber`, `LiteralString`, `ASTKeyword`, or `LiteralSymbol`), where `node.token.value` holds the transformed value.
- **Diagnostics on Failure:**
  - `ReqUnexpectedEOF` (`ParserError`) if `parser.empty()` is `True`.
  - `ReqTokenMismatch` (`ParserError`) if the current token's type name does not match `target_token`.
  - `ReqConstraintFailed` (`GrammarError`) if any validation or `.transform()` step fails.

---

## 5. Example

```python
from gram.core.combinators import Req
from gram.core.lexer import Token

# Lowercase snake_case identifier of at least 3 chars, normalized to UPPERCASE
const_name = (
    Req(Token.IDENT)
    .is_snake_case()
    .min(3)
    .apply_upper()
)

# Number between 10 and 100 inclusive
port_number = Req(Token.NUMBER).min(10).max(100)
```
