# Lookahead, Control, and Telemetry Combinators

These combinators evaluate lookahead conditions without consuming tokens, trigger flow-control signals, attach semantic metadata, fuse composite tokens, and inspect recorded errors.

---

## 1. `Peek` (Positive Lookahead)

Asserts that its child combinator matches at the current cursor position, then immediately restores the parser checkpoint without consuming any tokens ($O(1)$ lookahead assertion).

### Constructor
```python
Peek(combinator: Combinator)
```

### Return Shape
Returns an empty list `[]` on match (allowing enclosing sequences to succeed), or `None` on mismatch. The cursor position remains unchanged.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Checks if the next token is an identifier without consuming it
peek_ident = combinators.Peek(combinators.MatchToken(Token.IDENT))
```

---

## 2. `Not` (Negative Lookahead)

Asserts that its child combinator does **not** match at the current cursor position. Restores the parser checkpoint after evaluation.

### Constructor
```python
Not(combinator: Combinator)
```

### Return Shape
- Succeeds (returns `[]`) if the child combinator fails to match.
- Fails (returns `None`) if the child combinator matches.
- Never advances the cursor.

### Example
```python
from gram import combinators

# Ensures the current token is NOT the keyword 'return'
not_return = combinators.Not(combinators.MatchKeyword("return"))
```

---

## 3. `If` (Conditional Branching)

Evaluates one or more `conditions` and branches into either `ok` (if conditions match) or `fail` (if any condition fails).

### Constructor
```python
If(
    conditions: Sequence[Combinator] | Combinator,
    ok: Sequence[Combinator] | Combinator | None = None,
    fail: Sequence[Combinator] | Combinator | None = None,
    *,
    restore: bool = False,
)
```

- `restore`: If `True`, restores the cursor to the initial checkpoint after evaluating `conditions` before running `ok` (lookahead mode). If `False`, keeps condition tokens consumed and evaluates `ok`.

### Return Shape
- If `restore=False` and `ok` succeeds: Returns `[*condition_results, ok_result]`.
- If `restore=True`: Returns the `ok` branch result directly.
- If condition fails and `fail` is defined: Returns the `fail` branch result.

### Errors Raised
- Raises `EmptyIfConditions` if instantiated with an empty condition list.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# If keyword 'let' matches, parse IDENT; otherwise parse literal number
conditional_binding = combinators.If(
    conditions=combinators.MatchKeyword("let"),
    ok=combinators.MatchToken(Token.IDENT),
    fail=combinators.MatchToken(Token.NUMBER),
)
```

---

## 4. `Skip` (Flow Control Signal)

Raises a specified `ControlFlowSignal` (such as `SkipFlowSignal` or `BreakFlowSignal`) to cleanly interrupt an enclosing sequence (`Seq`) or repetition loop (`Many`, `Some`).

### Constructor
```python
Skip(signal: type[ControlFlowSignal])
```

### Example
```python
from gram import combinators
from gram.core.combinators.signals import SkipFlowSignal

skip_step = combinators.Skip(SkipFlowSignal)
```

---

## 5. `Tag` [Beta]

Attaches, removes, or queries semantic tags on the current token position inside the checkpoint-safe `parser.tk_tags` dictionary without creating extra AST nodes or advancing the cursor.

### Constructor and Builders
```python
Tag(tag: str, mode: Literal["add", "remove", "exists", "not_exists"] = "add")

# Fluent constructors:
Tag.add("tag_name")
Tag.remove("tag_name")
Tag.exists("tag_name")
Tag.not_exists("tag_name")
```

### Errors Raised
- Reports `RequiredTagMissing` if `Tag.exists()` fails.
- Reports `ForbiddenTagPresent` if `Tag.not_exists()` fails.

### Example
```python
from gram import combinators

# Mark current statement as exported
mark_exported = combinators.Tag.add("exported")

# Assert that current statement has the 'exported' tag
check_exported = combinators.Tag.exists("exported")
```

---

## 6. `Tokenize`

Evaluates an ordered sequence of child combinators and fuses all matched tokens into a single composite `TokenType` backed by a synthesized `CustomToken`. Prevents composite lexical sub-rules from expanding into unnecessary child branches in the AST.

### Constructor
```python
Tokenize(
    *combinators: Combinator,
    token_name: str = "CustomToken",
    name: str | None = None,
    join_char: str = "",
)
```

### Return Shape
Returns a single `TokenType` whose `.token` is a `CustomToken` and whose `.value` is the joined lexeme.

### Errors Raised
- Raises `EmptyTokenizeCombinators` if instantiated without child combinators.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Combines '@' and an identifier into a single DECORATOR token (e.g., '@property')
decorator = combinators.Tokenize(
    combinators.MatchToken(Token.AT),
    combinators.MatchToken(Token.IDENT),
    name="DECORATOR",
    join_char="",
)
```

---

## 7. `ErrorCombinator`

Inspects, captures, and clears recorded errors from the active diagnostic registries (`analyzer._errors`, `parser._errors`, or `StackError`). Useful for error-recovery rules.

### Constructor
```python
ErrorCombinator(length: int = 1)
```

- `length=0`: Captures and clears all recorded errors.
- `length=N`: Captures and removes up to the `N` most recent errors.

### Return Shape
Returns `list[errors.Error]` containing the captured error instances. If no errors are present, reports `NoErrorsToCatch`.

### Example
```python
from gram import combinators

# Recovers from previous syntax errors by capturing all diagnostic records
catch_all_errors = combinators.ErrorCombinator(length=0)
```
