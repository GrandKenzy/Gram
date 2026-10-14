# Repetition and Delimited Combinators

Repetition combinators handle loops, iterative patterns, and delimited lists across the token stream.

---

## 1. `Many` (Zero-or-More)

Represents the Kleene star ($0..n$) repetition. Repeatedly evaluates its child combinator while matches succeed and tokens advance.

### Constructor
```python
Many(combinator: Combinator)
```

### Return Shape
Returns `list[Any]` containing the AST nodes of all matched iterations. If zero matches occur, returns an empty list `[]` without error.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches any number of consecutive variable declarations
statements = combinators.Many(
    combinators.Seq(
        combinators.MatchGroup("types"),
        combinators.MatchToken(Token.IDENT),
    )
)
```

---

## 2. `Some` (One-or-More)

Represents the non-empty Kleene plus ($1..n$) repetition. Requires at least one mandatory match to succeed; otherwise restores the initial checkpoint and fails.

### Constructor
```python
Some(combinator: Combinator)
```

### Return Shape
Returns `list[Any]` containing at least one matched node on success, or `None` if zero matches occur.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Requires at least one argument, accumulating any additional arguments
arguments = combinators.Some(combinators.MatchToken(Token.IDENT))
```

---

## 3. `Until`

Consumes tokens sequentially one by one until a target stopping combinator matches on the stream.

### Constructor
```python
Until(
    target: Combinator,
    *,
    consume_target: bool = False,
    max_tokens: int | None = None,
)
```

- `consume_target`: If `False` (default), stops immediately before `target`, leaving target tokens in the stream. If `True`, consumes `target` and appends its result to the output list.
- `max_tokens`: Optional maximum cap of tokens consumed before reaching `target`.

### Return Shape
Returns `list[Any]` containing all tokens/nodes consumed prior to reaching `target`.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Consumes everything up to a semicolon without consuming the semicolon itself
statement_body = combinators.Until(
    combinators.MatchToken(Token.SEMICOLON),
    consume_target=False,
)
```

---

## 4. `Separator` / `Sep`

Parses elements separated by a delimiter token (such as comma-separated function arguments or semicolon-separated statements). Supports minimum/maximum count bounds and optional trailing delimiters.

### Constructor
```python
Separator(
    values: Sequence[RuleItem | Ref | MatchToken | Token | str],
    sep: Token | MatchToken | str,
    *,
    min: int = 0,
    max: int | None = None,
    allow_trailing: bool = False,
)
```
*(Also exported under the alias `Sep`)*

### Return Shape
Returns a [`SeparatorResult`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/combinators/separator.py#L25) instance, which subclasses `list[Any]` and provides:
- `.trailing_separator`: Boolean flag indicating if a trailing separator was consumed.
- `.to_list()`: Recursively converts the result into plain Python lists.
- `.items`: Returns a shallow list copy of the elements.

### Errors Raised
- Raises `UnsupportedSeparatorValue` if an invalid specification is passed in `values`.
- Raises `UnnamedRefInSeparator` if a `Ref` without a name and with `nodeable=False` is passed.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches comma-separated identifiers: 'a, b, c' (optional trailing comma)
arg_list = combinators.Separator(
    values=[Token.IDENT],
    sep=Token.COMMA,
    allow_trailing=True,
)
```
