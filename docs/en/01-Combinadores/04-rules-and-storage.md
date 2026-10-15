# Rules, Atoms, and State Storage

These combinators link modular grammar rules, group atomic token sequences, validate literal primitives, and manipulate checkpoint-safe parser storage.

---

## 1. `Ref` (Rule Reference)

Enables modular grammar composition by referencing a `RuleItem` class. Solves recursion and forward references by resolving `rule.entrypoint` dynamically at parse time.

### Constructor
```python
Ref(rule: type[RuleItem] | str, name: str | None = None, strict: bool = False)
```

- `name`: Identifier assigned to the generated `ASTRef` node. If omitted and `rule.nodeable = True`, defaults to the rule's class name.

### Return Shape
- If `name` is provided or `rule.nodeable = True`: Returns an [`ASTRef`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/ast/nodes.py#L63) instance wrapping the matched child nodes.
- If anonymous (`name = None` and `rule.nodeable = False`): Returns the raw visitor result directly.

### Errors Raised
- Reports `EmptyRuleReference` if the referenced rule does not have an `entrypoint` attribute defined.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

class EXPR(combinators.RuleItem):
    nodeable = True
    entrypoint = combinators.MatchToken(Token.NUMBER)

class STATEMENT(combinators.RuleItem):
    entrypoint = combinators.Seq(
        combinators.MatchKeyword("return"),
        combinators.Ref(EXPR),  # produces ASTRef('EXPR', [LiteralNumber])
    )
```

---

## 2. `Item`

Groups child match combinators into an atomic sequential unit. If any element in the sequence fails to match, the parser state is completely restored to the initial checkpoint while preserving the deepest failure candidate.

### Constructor
```python
Item(*matchs: Combinator)
```

### Return Shape
Returns an [`ItemNode`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/combinators/item.py#L22) (subclass of `list[TokenType]`) containing all matched tokens on success, or `None` on failure.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Matches an atomic key-value pair separator sequence
key_separator = combinators.Item(
    combinators.MatchToken(Token.COLON),
    combinators.MatchToken(Token.ASSIGN),
)
```

---

## 3. `Literal`

Matches the primitive value of the current token against an expected literal value (or any non-keyword literal if omitted). Reserved keywords (`Token.KEYWORD`) never match `Literal`.

### Constructor
```python
Literal(literal: Any = _ANY_LITERAL)
```

### Return Shape
Returns a [`LiteralNode`](file:///c:/Users/Kentucky/Desktop/Gram/gram/core/combinators/item.py#L32) (subclass of `list[TokenType]`) containing the matched token, or `None` on mismatch.

### Example
```python
from gram import combinators

# Matches any literal token holding the exact value 'true'
match_true = combinators.Literal("true")
```

---

## 4. `Save` [Beta]

Captures and stores the token currently under the parser cursor into `parser.storage[name]`. When a `matcher` combinator is provided, delegates token consumption to the matcher.

### Constructor
```python
Save(name: str, matcher: Combinator | None = None, *, consume: bool = True)
```

- If `matcher` is `None`: Zero-width; records current `TokenType` without consuming tokens.
- If `matcher` is provided and `consume=True`: Evaluates `matcher`, stores the token, and returns the matcher's AST node.

### Return Shape
Returns the stored `TokenType` (if zero-width) or the AST node produced by `matcher`.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Captures the opening tag identifier: '<div ...>'
save_tag = combinators.Save("tag_name", combinators.MatchToken(Token.IDENT))
```

---

## 5. `Load` [Beta]

Interacts with a `TokenType` previously stored in `parser.storage[name]` using one of five operational modes:

### Constructor
```python
Load(
    name: str,
    mode: Literal["get", "match", "unmatch", "replace", "change"] = "get",
    matcher: Combinator | None = None,
)
```

### Operational Modes
| Mode | Action | Token Stream Impact |
| :--- | :--- | :--- |
| `'get'` | Returns the stored `TokenType` directly. | No cursor movement. |
| `'match'` | Requires the current token to equal the stored token. | Validates equality. |
| `'unmatch'` | Requires the current token to differ from the stored token. | Validates inequality. |
| `'replace'` | Replaces the token at the cursor with the stored token in-place. | In-place modification. |
| `'change'` | Swaps the token at the cursor with the token in storage. | In-place swap. |

### Errors Raised
- Reports `StorageKeyNotFound` if `name` does not exist in `parser.storage`.

### Example
```python
from gram import combinators
from gram.core.lexer import Token

# Enforces that closing tag matches the opening tag stored by Save('tag_name')
assert_closing_tag = combinators.Load("tag_name", mode="match")
```
