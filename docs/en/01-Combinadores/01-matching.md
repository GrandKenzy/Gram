# Lexical Matching Combinators

Matching combinators inspect the token under the active parser cursor. On match, they consume the token, advance the stream, and produce a terminal AST node via `analyzer.delegate_return_node(token)`.

---

## 1. `MatchToken`

Validates that the current token belongs to a specific `Token` enum type, `CustomToken`, or string token name.

> **Note**: `MatchToken` explicitly rejects `Token.KEYWORD` tokens. Keywords must be matched using `MatchKeyword` or `MatchGroup`.

### Constructor
```python
MatchToken(token: Token | CustomToken | str)
```

### Return Shape
Returns a concrete terminal [`ASTNode`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/ast/nodes.py#L16) subclass wrapping the consumed token:
- `Token.IDENT` $\to$ `Identifier`
- `Token.NUMBER` $\to$ `LiteralNumber`
- `Token.STRING` $\to$ `LiteralString`
- Symbol tokens $\to$ `LiteralSymbol`

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches an identifier such as 'my_variable'
match_ident = combinators.MatchToken(Token.IDENT)

# Alternatively, pass the token name as string
match_number = combinators.MatchToken("NUMBER")
```

---

## 2. `MatchKeyword`

Validates that the current token is a registered `Token.KEYWORD` matching an exact keyword string.

### Constructor
```python
MatchKeyword(keyword: str | Keyword)
```

### Return Shape
Returns an `ASTKeyword` node wrapping the matched token, or `None` on mismatch.

### Example
```python
from gram import combinators

# Matches the exact keyword 'return'
match_return = combinators.MatchKeyword("return")
```

---

## 3. `MatchGroup`

Validates that the current token is a keyword registered within a specific semantic `WordGroup` (e.g., `'types'`, `'control'`).

### Constructor
```python
MatchGroup(
    group: str | WordGroup,
    values: Iterable[str] | None = None,
    behavior_values: Literal["allow", "deny", "none"] = "none",
)
```

### Filter Modes
- `"none"`: Accepts any keyword belonging to the group.
- `"allow"`: Accepts only group members present in `values`.
- `"deny"`: Accepts group members except those present in `values`.

### Return Shape
Returns an `ASTKeyword` node on match, or `None` on mismatch. If the group does not exist in the registry, reports a `WordGroupNotFound` diagnostic.

### Example
```python
from gram import combinators

# Matches any registered type keyword ('int', 'str', 'bool')
match_any_type = combinators.MatchGroup("types")

# Matches only 'int' and 'float' from 'types'
match_numeric_types = combinators.MatchGroup("types", values=["int", "float"], behavior_values="allow")
```

---

## 4. `MatchSymbol` / `MatchSeqSymbol`

Validates character sequences, operators, or textual patterns against the current token using regular expressions. Supports relabeling the matched token with a `CustomToken`.

### Constructor
```python
MatchSymbol(
    pattern: str | None = None,
    symbols: list[str] | None = None,
    regex: str | None = None,
    custom_token_name: str | None = None,
    is_pattern: bool = True,
    case_sensitive: bool = False,
)
```

### Return Shape
Returns a `LiteralSymbol` node wrapping the consumed token (or a `CustomToken` if `custom_token_name` was provided).

### Example
```python
from gram import combinators

# Matches exact symbol ':'
match_colon = combinators.MatchSymbol(pattern=r":")

# Matches any comparison operator and relabels it
match_comp = combinators.MatchSeqSymbol(
    symbols=["==", "!=", "<=", ">="],
    custom_token_name="COMPARISON_OP",
)
```

---

## 5. `generador_expr`

A helper function to assemble regular expressions from string fragments and character or numeric range bounds `[start, end]`.

```python
from gram.core.combinators.match import MatchSymbol, generador_expr

# Generates pattern: r"\#[A-Fa-f0-9]"
hex_pattern = generador_expr("#", ["A", "F"], ["a", "f"], [0, 9])
hex_matcher = MatchSymbol(pattern=hex_pattern)
```
