# Rules, Atoms, and State Storage

These classes and combinators define modular grammar rules (`RuleItem`, `Ref`), atomic token sequences (`Item`), literal value checks (`Literal`), and checkpoint-safe token storage (`Save`, `Load`).

---

## 1. `RuleItem` (Production Rule Class)

Declarative base class (`gram.core.combinators.base.RuleItem`) for grammar rules. Its metaclass (`RuleMeta`) automatically assigns `name` (defaulting to the class name) and allocates a unique numeric `code` via `AutoCode` in `code_manager`.

### Class Attributes
```python
class MyRule(RuleItem):
    entrypoint: Combinator | None = None
    name: str = ""            # Defaults to 'MyRule'
    code: int = 0             # Auto-allocated >= 21 unless SetCode(n) is used
    nodeable: bool = True     # When True, Ref(MyRule) wraps results in ASTRef
    description: str = ""

    # Optional VSIX / LSP metadata maps (keyed by token index or 'this'):
    colors: dict[int | str, str] = {}
    autocomplete: dict[int | str, str] = {}
    suggestions: dict[int | str, Any] = {}
    hints: dict[int | str, str] = {}
    playhints: dict[int | str, str] = {}
```

### Root Entrypoint Requirement
When a `RuleItem` subclass is passed as the root `entrypoint` to `ASTAnalyzer(parser, RootRule)` or `Parser.parse(RootRule)`, `ASTState.is_valid_entrypoint()` enforces that:
1. `RootRule.entrypoint` is an `Alt` combinator (otherwise reports `InvalidEntryPointCombinator`).
2. Every child inside that `Alt` is a `Ref` combinator (otherwise reports `InvalidEntryPointElement`).

---

## 2. `Ref` (Rule Reference)

Delegates parsing to `rule.entrypoint` at evaluation time, enabling mutual recursion and forward references.

### Constructor
```python
Ref(
    rule: type[RuleItem],
    name: str | None = None,
    strict: bool = False,
)
```

- `name`: Label for the resulting `ASTRef` node.
- `strict`:
  - When `False` (default) and `name is None`, if `getattr(rule, "nodeable", False)` is `True` (which is the default on `RuleItem`), `self.name` is automatically set to `rule.name`.
  - When `True` and `name is None`, `self.name` remains `None` even if `rule.nodeable` is `True`.

### Return Shape & Diagnostics
- If `rule.entrypoint` is `None`, reports `EmptyRuleReference` (`GrammarError`) and returns `None`.
- If `self.name` is non-empty: wraps the matched result into `ASTRef(name=self.name, nodes=...)` (`nodes` is always a `list`).
- If `self.name` is `None`: returns the raw result of `rule.entrypoint` directly without wrapping in `ASTRef`.

### Example
```python
from gram.core.combinators import MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer import Token

class Expr(RuleItem):
    nodeable = True
    entrypoint = MatchToken(Token.NUMBER)

class ReturnStmt(RuleItem):
    entrypoint = Seq(
        MatchKeyword("return"),
        Ref(Expr),  # produces ASTRef(name='Expr', nodes=[LiteralNumber])
    )
```

---

## 3. `Item`

Evaluates a fixed sequence of token-producing combinators as an atomic unit and flattens all matched `TokenType` objects into an `ItemNode` (`list[TokenType]` subclass).

### Constructor
```python
Item(*matchs: Combinator)
```

### Execution & Return Shape
- If called with no combinators (`Item()`), returns an empty `ItemNode([])`.
- Evaluates each child inside `analyzer.safe_mode()`.
- If any child returns `None`, restores the initial checkpoint, reports/flushes `IncompleteItemSequence` (`GrammarError`), and returns `None`.
- Extracts `TokenType` objects from each child result (`TokenType`, `ASTTokenNode` via `.token`, `ItemNode`, `LiteralNode`, `list`, `tuple`). If a child returns any other object (such as an `ASTRef`), restores the checkpoint, reports `InvalidItemElementType` (`GrammarError`), and returns `None`.
- **Return Value:** `ItemNode(tokens)` on success, or `None` on failure.

### Example
```python
from gram.core.combinators import Item, MatchToken
from gram.core.lexer import Token

double_colon = Item(
    MatchToken(Token.COLON),
    MatchToken(Token.COLON),
)
```

---

## 4. `Literal`

Validates the primitive `.value` of the current token against `literal` (or accepts any non-keyword token when `literal` is omitted).

### Constructor
```python
Literal(literal: Any = _ANY_LITERAL)
```

- `Token.KEYWORD` tokens are always rejected (reporting `KeywordNotAllowedInLiteral`).
- When `literal` is provided, checks `tok.value == literal` (including numeric equality across `int` and `float`).

### Return Shape & Diagnostics
- **Match:** Consumes the token and returns `LiteralNode([tok])` (a `list[TokenType]` subclass).
- **Mismatch / EOF:** Reports `LiteralUnexpectedEOF`, `KeywordNotAllowedInLiteral`, or `LiteralValueMismatch` (`ParserError`) and returns `None`.

### Example
```python
from gram.core.combinators import Literal

match_zero = Literal(0)
match_any_non_keyword = Literal()
```

---

## 5. `Save`

Stores the `TokenType` currently at `parser.pos` into the checkpoint-safe
dictionary `parser.storage[name]` or into an optional caller-owned mapping.

### Constructor
```python
Save(
    name: str,
    matcher: Combinator | None = None,
    *,
    consume: bool = True,
    storage: MutableMapping[str, TokenType] | None = None,
)
```

When `storage` is omitted, `Save` uses `parser.storage`. When a mapping is
provided, the token is stored there and that mapping is included in parser
checkpoint tracking.

### Consumption Modes
1. **`matcher=None` (zero-width capture):** Stores `parser.peek()` in the selected storage without advancing `parser.pos` and returns the stored `TokenType`.
2. **`matcher` provided, `consume=True` (default):** Evaluates `matcher` (advancing `parser.pos`), stores the original token in the selected storage, and returns `matcher`'s AST result. If `matcher` fails, restores the checkpoint, reports `SaveMatcherFailed`, and returns `None`.
3. **`matcher` provided, `consume=False` (validated lookahead capture):** Evaluates `matcher`, then restores the checkpoint so `parser.pos` does not advance, stores the token in the selected storage, and returns the `TokenType`.

### Example
```python
from gram.core.combinators import Load, MatchToken, Save
from gram.core.lexer import Token

save_open_tag = Save("open_tag", MatchToken(Token.IDENT), consume=True)

typedef_storage = {}
save_typedef = Save(
    "current_type",
    MatchToken(Token.IDENT),
    storage=typedef_storage,
)
load_typedef = Load(
    "current_type",
    mode="get",
    storage=typedef_storage,
)
```

---

## 6. `Load`

Reads, compares, or swaps a `TokenType` previously saved in
`parser.storage[name]` or in an explicitly supplied external mapping.

### Constructor
```python
Load(
    name: str,
    mode: Literal["get", "match", "unmatch", "replace", "change"] = "get",
    matcher: Combinator | None = None,
    *,
    storage: Mapping[str, TokenType] | None = None,
)
```

Pass the same mapping to `Save` and `Load` to share typedefs or dynamic types
without placing them in the parser's default storage.

### Modes & Token Consumption
> **Important:** In modes `"match"`, `"unmatch"`, `"replace"`, and `"change"`, `Load` only advances `parser.pos` if a `matcher` combinator is passed. When `matcher=None`, those modes operate at `parser.pos` without consuming the token.

| Mode | Behavior | Return Value (`matcher=None`) | Return Value (`matcher` provided) |
| :--- | :--- | :--- | :--- |
| `"get"` | Returns the saved token from the selected storage without inspecting or moving the cursor. | Stored `TokenType` | Stored `TokenType` (`matcher` ignored) |
| `"match"` | Requires `current.token == saved.token` and `current.value == saved.value` (else reports `LoadMatchFailed`). | `current` (`TokenType`), cursor unchanged | Result of `matcher` (consumes token) |
| `"unmatch"` | Requires `current` to differ in type or value from `saved` (else reports `LoadUnmatchFailed`). | `current` (`TokenType`), cursor unchanged | Result of `matcher` (consumes token) |
| `"replace"` | Replaces `parser.tokens[parser.pos]` in-place with `saved` (tracked for checkpoint rollback). | `saved` (`TokenType`), cursor unchanged | Result of `matcher` on the replaced token |
| `"change"` | Swaps `parser.tokens[parser.pos]` and the token saved in the selected storage. | `saved` (`TokenType`), cursor unchanged | Result of `matcher` on the swapped-in token |

### Diagnostics
- `StorageKeyNotFound` (`GrammarError`) if `name` is not in the selected storage.
- `LoadUnexpectedEOF` (`ParserError`) if `mode != "get"` and the stream is empty.
- `LoadMatcherFailed` (`GrammarError`) if `matcher` fails (restoring the checkpoint, including any `"replace"` or `"change"` mutation).

### Example
```python
from gram.core.combinators import Load, MatchToken, Save, Seq
from gram.core.lexer import Token

# Match an opening identifier and require the next identifier to have the same token & value:
paired_ident = Seq(
    Save("tag", MatchToken(Token.IDENT)),
    Load("tag", mode="match", matcher=MatchToken(Token.IDENT)),
)
```
