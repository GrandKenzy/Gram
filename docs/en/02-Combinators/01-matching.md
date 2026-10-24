# Lexical Matching Combinators

Matching combinators (`gram.core.combinators.match`) inspect the token at `parser.pos`. On match, they consume the token (`parser.consume()`), discard stale staged failures behind the new cursor position, and return the terminal `ASTNode` created by `analyzer.delegate_return_node(token)`.

### Token-to-AST Node Delegation (`analyzer.delegate_return_node`)

Every matching combinator delegates its consumed `TokenType` through `ASTState.delegate_return_node(current)`, which maps `current.token` as follows:

| `current.token` | Returned `ASTNode` Subclass |
| :--- | :--- |
| `Token.IDENT` | `Identifier` |
| `Token.NUMBER` | `LiteralNumber` |
| `Token.STRING` | `LiteralString` |
| `Token.DOCSTRING` (when `config.LEXER_SUPPORT_DOCSTRINGS` is `True`) | `LiteralString` |
| `Token.KEYWORD` | `ASTKeyword` |
| Any other `Token` or `CustomToken` | `LiteralSymbol` |

All terminal node classes inherit from `ASTTokenNode` (`gram.core.ast.nodes.ASTTokenNode`), exposing the consumed `TokenType` via `node.token`.

---

## 1. `MatchToken`

Validates that the current token matches a specific `Token` enum member, `CustomToken`, or canonical `Token` name string.

> **Important:** `MatchToken` explicitly rejects `Token.KEYWORD` tokens (reporting `UnexpectedKeywordToken`). Keywords must be matched with `MatchKeyword` or `MatchGroup`.

### Constructor
```python
MatchToken(token: Token | CustomToken | str)
```

- Passing a `str` resolves it via `Token.from_string(token)`. If the string does not match any `Token` member, `InvalidTokenReference` (`GrammarError`) is raised immediately at construction time.

### Return Value & Diagnostics
- **Match:** Consumes the token and returns the delegated `ASTTokenNode` (`Identifier`, `LiteralNumber`, `LiteralString`, or `LiteralSymbol`).
- **Mismatch / EOF:** Leaves `parser.pos` unchanged, reports `EmptyTokenStream`, `EOFReached`, `UnexpectedKeywordToken`, or `TokenMismatch` (`ParserError`), and returns `None`.

### Example
```python
from gram.core.combinators import MatchToken
from gram.core.lexer import Token

match_ident = MatchToken(Token.IDENT)
match_number = MatchToken("NUMBER")
```

---

## 2. `MatchKeyword`

Validates that the current token has `current.token == Token.KEYWORD` and `current.value == keyword`.

### Constructor
```python
MatchKeyword(keyword: str | Keyword)
```

### Return Value & Diagnostics
- **Match:** Consumes the token and returns an `ASTKeyword` node wrapping the token.
- **Mismatch / EOF:** Reports `EmptyTokenStream`, `KeywordTypeMismatch`, or `KeywordValueMismatch` (`ParserError`) and returns `None`.

### Example
```python
from gram.core.combinators import MatchKeyword
from gram.core.lexer import words

words.add_keyword("return")
match_return = MatchKeyword("return")
```

---

## 3. `MatchGroup`

Validates that the current token's value belongs to a registered `WordGroup` in `gram.core.lexer.words` (`words.exists_in_group(current.value, group)`), with optional allow/deny filtering.

### Constructor
```python
MatchGroup(
    group: str | WordGroup,
    values: Iterable[str] | None = None,
    behavior_values: Literal["allow", "deny", "none"] = "none",
)
```

### Filter Modes (`behavior_values`)
- `"none"`: Accepts any keyword registered in `group`.
- `"allow"`: Accepts only members of `group` whose lexeme is in `values` (otherwise reports `GroupValueNotAllowed`).
- `"deny"`: Accepts members of `group` whose lexeme is **not** in `values` (otherwise reports `GroupValueDenied`).

### Return Value & Diagnostics
- **Match:** Consumes the token and returns an `ASTKeyword` node.
- **Mismatch / Missing Group:**
  - If `group` does not exist in `words`, reports `WordGroupNotFound` (`LexerError`) and returns `None`.
  - If the token does not belong to `group`, reports `GroupMismatch` (`ParserError`) and returns `None`.

### Example
```python
from gram.core.combinators import MatchGroup
from gram.core.lexer import add_group, add_keyword

add_group("types")
add_keyword("int", group="types")
add_keyword("str", group="types")
add_keyword("bool", group="types")

match_any_type = MatchGroup("types")
match_numeric_only = MatchGroup("types", values=["int"], behavior_values="allow")
```

---

## 4. `MatchSeqSymbol` / `MatchSymbol`

`MatchSymbol` is an alias for `MatchSeqSymbol` (`MatchSymbol = MatchSeqSymbol`). It validates `str(tok.value)` against a compiled regular expression (`fullmatch`) and optionally relabels the token's `.token` attribute with a `CustomToken` before delegating to the AST.

### Constructor
```python
MatchSeqSymbol(
    pattern: str | None = None,
    symbols: list[str] | None = None,
    regex: str | None = None,
    custom_token_name: str | None = None,
    is_pattern: bool = True,
    case_sensitive: bool = False,
    raw: bool = False,
)
```

- **Pattern resolution priority:**
  1. `regex`: Used as-is (`is_pattern` is forced to `True`).
  2. `symbols`: Escapes each string in `symbols` and joins them with `|` (`is_pattern` is forced to `True`).
  3. `pattern`: Used as a regex if `is_pattern=True`, or escaped via `re.escape(pattern)` if `is_pattern=False`.
- `case_sensitive`: Defaults to `False` (`re.IGNORECASE`). Set to `True` for case-sensitive matching.
- `custom_token_name`: When provided, replaces `tok.token` in-place with `CustomToken(custom_token_name, val_str)` before delegating to `analyzer.delegate_return_node(tok)`.

### Return Value & Diagnostics
- **Match:** Consumes the token and returns the delegated `ASTTokenNode` (a `LiteralSymbol` when `custom_token_name` is set, with `node.token.token` holding the `CustomToken`).
- **Mismatch / EOF:** Reports `SymbolUnexpectedEOF` or `SymbolMismatch` (`ParserError`) and returns `None`.

### Example
```python
from gram.core.combinators import MatchSeqSymbol, MatchSymbol

match_colon = MatchSymbol(pattern=":", is_pattern=False)

match_comparison = MatchSeqSymbol(
    symbols=["==", "!=", "<=", ">="],
    custom_token_name="COMPARISON_OP",
)
```

---

## 5. `generador_expr`

Helper function in `gram.core.combinators.match` that builds a regular expression string from literal strings and 2-element character or integer ranges `[start, end]`.

```python
generador_expr(*parts: str | list[str | int] | tuple[str | int, str | int]) -> str
```

- Literal `str` parts are escaped with `re.escape`.
- Consecutive 2-element `[start, end]` pairs of `str` or `int` are merged into a single character class `[...]`.
- Any other argument type raises `InvalidRegexGeneratorPart` (`GrammarError`).

### Example
```python
from gram.core.combinators import MatchSymbol, generador_expr

# Produces '#[A-Fa-f0-9]'
hex_digit = generador_expr("#", ["A", "F"], ["a", "f"], [0, 9])
hex_matcher = MatchSymbol(pattern=hex_digit, case_sensitive=True)
```
