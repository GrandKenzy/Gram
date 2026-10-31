# Token Stream Navigation (`TokenStream`)

While `Lexer.process()` returns a raw Python `list[TokenType]`, Gram provides `TokenStream` (`gram.core.lexer.items.TokenStream`) as a cursor-managed, inspectable, and filterable stream wrapper.

---

## 1. Instantiating a `TokenStream`

You can obtain a `TokenStream` directly from `Lexer.stream()` or by wrapping an existing sequence of tokens:

```python
from gram.core.lexer import Lexer, TokenStream, words
words.add_keyword("let", allow_override=True)

# 1. Directly from Lexer
stream = Lexer("let x = 10;").stream()

# 2. By wrapping an existing token list
tokens = Lexer("let y = 20;").process()
stream = TokenStream(tokens)
```

The underlying token sequence is stored as an immutable `tuple[TokenType, ...]`, ensuring the tokens cannot be accidentally mutated during stream navigation.

---

## 2. Cursor Inspection & Status

`TokenStream` tracks an internal integer cursor `_pos` that advances as tokens are consumed.

### Status Properties & Methods

| Member | Return Type | Description |
| :--- | :--- | :--- |
| `stream.position` | `int` | Current cursor index ($0 \le \text{pos} \le \text{len}$). Can be read or assigned directly. |
| `stream.tokens` | `tuple[TokenType, ...]` | Immutable tuple containing all tokens in the stream. |
| `stream.has_next()` | `bool` | Returns `True` if unconsumed non-`EOF` tokens remain in the stream. |
| `stream.is_eof()` | `bool` | Returns `True` if the cursor has reached `Token.EOF` or the stream end. |
| `stream.current()` | `TokenType \| None` | Returns the token under the current cursor without advancing. Returns `None` if out of bounds. |
| `stream.peek(offset=0)` | `TokenType \| None` | Inspects a token at `position + offset` without advancing. Returns `None` if out of bounds. |

```python
stream = Lexer("let a = 10;").stream()

print(stream.position)        # 0
print(stream.current().token) # Token.KEYWORD ("let")
print(stream.peek(1).token)   # Token.IDENT ("a")
print(stream.peek(2).token)   # Token.ASSIGN ("=")
print(stream.has_next())      # True
```

---

## 3. Consumption & Pattern Matching API

`TokenStream` provides three complementary methods for consuming tokens: `advance()`, `check()`, `match()`, and `consume()`.

### `advance() -> TokenType`
Consumes the current token and advances the cursor by 1. If called when the cursor has reached the end, it returns a synthetic `TokenType(Token.EOF, None, line, col)`:

```python
tok1 = stream.advance()  # Consumes 'let'
tok2 = stream.advance()  # Consumes 'a'
```

### `check(*expected: Token | TokenType | str) -> bool`
Returns `True` if the token under the current cursor matches **any** of the criteria in `expected` without moving the cursor:
- Passing a `Token` checks `curr.token == exp`.
- Passing a `TokenType` checks structural equality `curr == exp`.
- Passing a `str` checks `curr.value == exp` or `curr.token.name == exp`.

```python
if stream.check(Token.IDENT, "let"):
    print("Matches identifier or 'let'")
```

### `match(*expected: Token | TokenType | str) -> bool`
Conditional consumption: calls `check(*expected)`. If it matches, consumes the token with `advance()` and returns `True`; otherwise leaves the cursor unchanged and returns `False`:

```python
# Consume '=' only if present:
if stream.match(Token.ASSIGN, "="):
    print("Assignment operator consumed!")
```

### `consume(expected=None, message="") -> TokenType`
Mandatory consumption. Verifies that the current token matches `expected` before advancing. If the condition fails, it raises a structured `errors.ParserError`:
- If the stream reached EOF prematurely, raises `PARSER_EARLY_EOF`.
- If the token does not match, raises `PARSER_UNEXPECTED_TOKEN` with coordinates and details.

```python
# Strict consumption:
token_let = stream.consume(Token.KEYWORD, "Expected 'let' keyword")
token_name = stream.consume(Token.IDENT, "Expected variable name")
stream.consume("=", "Expected '=' after variable name")
```

---

## 4. Cursor Movement: `rewind()` & `reset()`

`TokenStream` allows transactional rollback and cursor resets:

```python
stream = Lexer("let x = 42;").stream()

stream.advance()  # Consumes 'let' (pos = 1)
stream.advance()  # Consumes 'x'   (pos = 2)

# Rewind 1 position:
stream.rewind(1)
print(stream.current().value)  # 'x' (pos = 1)

# Reset cursor back to the start:
stream.reset()
print(stream.current().value)  # 'let' (pos = 0)
```

---

## 5. Slicing & Token Filtering

### `slice(start: int, end: int | None = None) -> list[TokenType]`
Extracts a sub-list of tokens between `start` and `end`:

```python
stream = Lexer("let x = 10;").stream()
sub_tokens = stream.slice(0, 3)
print([t.value for t in sub_tokens])
# ['let', 'x', '=']
```

### `filter_tokens(*exclude: Token) -> TokenStream`
Returns a **new `TokenStream`** excluding all tokens whose type matches any member in `exclude`:

```python
from gram.core.lexer import Lexer, Token, words
from gram import config
config.LEXER_IGNORE_NEWLINES = False
words.add_keyword("dummy", allow_override=True)

# Generate a stream containing NEWLINE tokens:
stream = Lexer("a = 1\nb = 2").stream()

# Filter out NEWLINE tokens:
clean_stream = stream.filter_tokens(Token.NEWLINE)
print([t.token for t in clean_stream])
# [Token.IDENT, Token.ASSIGN, Token.NUMBER,
#  Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.EOF]
```

---

## 6. Python Sequence Protocol Integration

`TokenStream` implements the standard Python sequence protocols:

```python
stream = Lexer("let x = 10;").stream()

# 1. Total token count
total = len(stream)

# 2. Direct indexing and slicing
first = stream[0]
middle = stream[1:3]

# 3. Iteration
for token in stream:
    if token.token == Token.EOF:
        break
    print(token)
```
