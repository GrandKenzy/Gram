# Structural Combinators

Structural combinators organize tokens and sub-rules into ordered sequences, alternatives, optional segments, and delimited blocks.

---

## 1. `Seq` (Sequence)

Evaluates child combinators in strict linear order. If all children match, returns a list containing all produced AST nodes. If any child fails, the entire sequence fails, triggering an atomic rollback of the cursor to its initial position.

### Constructor
```python
Seq(*combinators: Combinator)
```

### Return Shape
Returns `list[Any]` containing the AST nodes of each child combinator on success, or `None` on failure.

### Errors Raised
- Raises `EmptySequence` if instantiated without child combinators.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Parses variable assignment: 'x = 42'
assignment_grammar = combinators.Seq(
    combinators.MatchToken(Token.IDENT),
    combinators.MatchToken(Token.ASSIGN),
    combinators.MatchToken(Token.NUMBER),
)
```

---

## 2. `Alt` (Alternative)

Evaluates candidate combinator branches in prioritized order until the first matching branch succeeds. If a branch fails, the parser state is automatically restored before evaluating the next alternative.

### Constructor
```python
Alt(*combinators: Combinator, ignore: bool = False)
```

- `ignore`: When `True`, excludes this `Alt` container from `RayTracing` telemetry (useful for the root entrypoint rule).

### Return Shape
Returns the exact result produced by the first matching candidate branch, or `None` if all branches fail.

### Errors Raised
- Raises `EmptyAlternatives` if instantiated without candidate branches.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches an identifier, string, or numeric literal
literal_value = combinators.Alt(
    combinators.MatchToken(Token.NUMBER),
    combinators.MatchToken(Token.STRING),
    combinators.MatchToken(Token.IDENT),
)
```

---

## 3. `Opt` (Optional)

Matches optional syntax ($0..1$ occurrences). Evaluates its child combinator within an isolated transaction:
- If the child matches, consumes the tokens and returns the matched node.
- If the child does not match, rewinds the cursor and returns `[]` so that surrounding `Seq` combinators succeed.

### Constructor
```python
Opt(combinator: Combinator)
```

### Return Shape
Returns the matched child AST node when present, or an empty list `[]` when cleanly omitted.

### Errors Raised
- Raises `InvalidOptionalTarget` if the passed object is not a `Combinator` instance.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Type declaration with optional initialization: 'int x' or 'int x = 10'
var_decl = combinators.Seq(
    combinators.MatchGroup("types"),
    combinators.MatchToken(Token.IDENT),
    combinators.Opt(
        combinators.Seq(
            combinators.MatchToken(Token.ASSIGN),
            combinators.MatchToken(Token.NUMBER),
        )
    ),
)
```

---

## 4. `Enclosed`

Evaluates inner content enclosed between arbitrary opening and closing `Token` delimiters. Automatically manages the parser's bracket depth stack and can optionally skip intra-bracket whitespace (`NEWLINE`, `INDENT`, `DEDENT`).

### Constructor
```python
Enclosed(
    open: Token,
    content: Combinator,
    close: Token,
    skip_whitespace: bool = True,
    allow_empty: bool = True,
)
```

### Return Shape
Returns the AST node or list produced by `content`, or an empty list `[]` if the delimiters are empty and `allow_empty=True`.

### Errors Raised
- Raises `InvalidDelimiterType` if `open` or `close` are not instances of `Token`.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches parenthesized parameters: '(a, b, c)'
parenthesized_params = combinators.Enclosed(
    open=Token.LPAREN,
    content=combinators.Separator(values=[Token.IDENT], sep=Token.COMMA),
    close=Token.RPAREN,
)
```
