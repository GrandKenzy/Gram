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

## 4. `UntilIndent`

Sequentially consumes tokens until encountering an indentation transition that matches a target indentation level or relative direction (`"back"` / `"front"`).

### Constructor
```python
UntilIndent(
    target: int | Literal["back", "front"] | str,
    *,
    consume_target: bool = False,
    allow_eof: bool = False,
    max_tokens: int | None = None,
)
```

- `target`: Target indentation condition:
  - `int` (e.g. `0`, `4`): Consumes until finding an indentation level matching `target` (e.g. `0` reaches base level).
  - `"back"`: Consumes until finding any indentation lower than the active level at start (dedentation / `DEDENT`).
  - `"front"`: Consumes until finding any indentation higher than the active level at start (indentation / `INDENT`).
- `consume_target`: If `False` (default), stops immediately before the target `INDENT`/`DEDENT` token, leaving it in the stream for parent rules (such as block dedents). If `True`, consumes the target token.
- `allow_eof`: If `True`, reaching EOF without matching target is considered a valid end-of-block.
- `max_tokens`: Optional maximum cap of tokens consumed.

### Return Shape
Returns `list[Any]` containing all tokens/nodes consumed prior to reaching the indentation target.

### Example
```python
from gram import combinators as cmb

# 1. Consumes tokens until dedenting (leaving DEDENT for the enclosing block)
return_stmt = cmb.Seq(
    cmb.MatchKeyword("return"),
    cmb.Opt(cmb.Ref(VALUE)),
    cmb.UntilIndent("back", consume_target=False),
)

# 2. Consumes all tokens inside a block until returning to root level 0
root_block = cmb.UntilIndent(0)

# 3. Consumes header tokens until entering an indented block ('front')
block_header = cmb.UntilIndent("front", consume_target=False)
```

---

## 5. `Separator`

Parses elements separated by a delimiter token (such as comma-separated function arguments or semicolon-separated statements). Supports minimum/maximum count bounds and optional trailing delimiters, returning an `ArrayNode`.

### Constructor
```python
Separator(
    values: Sequence[RuleItem | Ref | MatchToken | Token | str] | Combinator | Token | str,
    sep: Token | MatchToken | Combinator | str = Token.COMMA,
    min: int = 0,
    max: int | None = None,
    allow_trailing: bool = True,
)
```

### Return Shape
Returns an [`ArrayNode`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/ast/nodes.py) AST node instance, providing:
- `.items`: `tuple[Any, ...]`: The parsed child AST elements.
- `.trailing`: `bool`: Boolean flag indicating if a trailing separator was consumed.
- Full sequence protocol support (`len(node)`, `iter(node)`, `node[idx]`, `bool(node)`).

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
