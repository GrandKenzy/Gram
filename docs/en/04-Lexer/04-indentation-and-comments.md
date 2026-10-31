# Indentation, Comments, & Delimiters

Gram incorporates a flexible, non-invasive system for tracking block indentation and handling comments without polluting the primary syntactic token stream.

---

## 1. Semantic Indentation Engine

Gram natively supports semantic indentation (off-side rule languages like Python, YAML, or Nim) via `LexerState.process_indent()`.

### The Indentation Stack (`self.indents`)

The lexer maintains an internal integer stack initialized to `[0]`:
- **Push (`Token.INDENT`):** When the leading visual width of the current line exceeds `self.indents[-1]`, the new width is pushed onto the stack, and a `Token.INDENT` token is emitted.
- **Pop (`Token.DEDENT`):** When the leading visual width decreases, the lexer pops indentation levels until matching an existing outer block, emitting one `Token.DEDENT` token for each unnested level.
- **Mismatch Error:** If the decreased indentation does not align with any level on the stack, the lexer reports `LEXER_INDENTATION_MISMATCH`.
- **EOF Unwinding:** At the end of the source file, any remaining indentation levels (`len(self.indents) > 1`) are automatically unwound, emitting trailing `Token.DEDENT` tokens before `Token.EOF`.

```python
from gram import config
from gram.core.lexer import Lexer, Token, words

words.clear_all()
words.add_keyword("def")
words.add_keyword("pass")

source = """def outer():
    pass
pass"""

tokens = Lexer(source).process()
print([t.token for t in tokens])
# [Token.KEYWORD, Token.IDENT, Token.LPAREN, Token.RPAREN, Token.COLON,
#  Token.INDENT, Token.KEYWORD,
#  Token.DEDENT, Token.KEYWORD, Token.EOF]
```

### Indentation Policies (`LEXER_INDENT_STYLE` & `LEXER_TAB_WIDTH`)

Visual indentation width is computed by `LexerState.indentation_width(prefix)`:

| Style (`LEXER_INDENT_STYLE`) | Width Formula | Description |
| :--- | :--- | :--- |
| `"spaces"` *(default)* | `prefix.count(" ")` | Legacy behavior. Only ASCII spaces count toward indentation width; tab characters count as 0. |
| `"tabs"` | `prefix.count("\t") * tab_width` | Only tab characters count toward indentation width; spaces are ignored. |
| `"mixed"` | Advances to next tab stop | Visual column expansion: each space adds 1, and each tab advances to the next multiple of `LEXER_TAB_WIDTH` (`width += tab_width - (width % tab_width)`). |

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

# Configure mixed tab/space expansion with 8-character tab stops:
config.LEXER_INDENT_STYLE = "mixed"
config.LEXER_TAB_WIDTH = 8
```

### Disabling Indentation Tracking (`SUPPORT_INDENT`)

For free-form or brace-delimited languages (C, Java, Rust, JavaScript), disable indentation tracking globally or per session:

```python
config.SUPPORT_INDENT = False
```

When `SUPPORT_INDENT=False`, `process_indent()` advances leading whitespace without modifying `self.indents` and emits neither `Token.INDENT` nor `Token.DEDENT`.

---

## 2. Line Comments

Line comments discard source text from a configured prefix up to the end of the physical line outside quoted strings.

### Configuration (`LEXER_COMMENT_TOKEN`)

The line comment marker is set via `config.LEXER_COMMENT_TOKEN` (default `'#'`). It accepts three types of values:

1. **String marker:** Single- or multi-character prefixes (e.g., `'#'`, `'//'`, `'--'`, `';'`, `'<->'`).
2. **`Token` Enum:** Mapped symbol token (e.g., `Token.FLOOR_DIV` for `'//'`).
3. **Tuple / List of markers:** Multiple valid prefixes simultaneously (e.g., `(Token.FLOOR_DIV, '#', ';')`).

```python
from gram import config
from gram.core.lexer import Lexer, Token, words
words.add_keyword("dummy", allow_override=True)

# 1. C++ style single-line comments:
config.LEXER_COMMENT_TOKEN = "//"

# 2. SQL / Lua style single-line comments:
config.LEXER_COMMENT_TOKEN = "--"

# 3. Multiple comment prefixes:
config.LEXER_COMMENT_TOKEN = ("//", "#", ";")
```

### Preserving Comments (`LEXER_SAVE_COMMENTS`)

By default, `config.LEXER_SAVE_COMMENTS = True`. Scanned comments are extracted into `lexer.comments` as `TokenType(Token.COMMENT, content, line, col)`:

```python
config.LEXER_COMMENT_TOKEN = "//"
lexer = Lexer("int x = 10; // initialize counter\nint y = 20;")
tokens = lexer.process()

# Main token stream does NOT contain Token.COMMENT:
print([t.token for t in tokens])
# [Token.KEYWORD, Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.SEMICOLON, ...]

# Preserved comments are accessible via lexer.comments:
print(lexer.comments)
# [TokenType(token=Token.COMMENT, value=' initialize counter', line=1, col=12)]
```

> [!TIP]
> Keeping comments in `lexer.comments` rather than in the primary token stream means your grammar combinators (`Seq`, `Alt`, `RuleItem`) do not need to account for comments appearing between arbitrary tokens.

---

## 3. Block Comments (C-Style)

Gram supports multi-line block comments (`/* ... */`):

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

config.LEXER_BLOCK_COMMENT_TOKEN = "/*"
config.LEXER_SUPPORT_BLOCK_COMMENTS = True

code = """
x = 1; /* inline block comment */ y = 2;
/* multi-line
   block comment */
z = 3;
"""

lexer = Lexer(code)
tokens = lexer.process()

print([t.value for t in tokens if t.value is not None])
# ['x', '=', 1, ';', 'y', '=', 2, ';', 'z', '=', 3, ';']

print(len(lexer.comments))
# 2 block comments captured
```

### Invariants for Block Comments:
1. Block comments always close with `"*/"`.
2. Block comments on the same line as code preserve all following tokens.
3. Block comments can span multiple physical lines without triggering spurious `Token.NEWLINE` or corrupting indentation.
4. Setting `LEXER_SUPPORT_BLOCK_COMMENTS = False` disables block comments, causing `"/*"` to be tokenized as `Token.SLASH` followed by `Token.STAR`.

---

## 4. Blank & Comment-Only Lines

Gram handles blank lines and comment-only lines seamlessly:

- **`config.LEXER_IGNORE_EMPTY_LINES` (`bool`, default `True`):** When `True`, completely blank lines do not emit redundant `Token.NEWLINE` tokens and do not trigger indentation changes.
- **`config.LEXER_IGNORE_NEWLINES` (`bool`, default `True`):** When `True`, statement-terminating `Token.NEWLINE` tokens are omitted entirely. Set to `False` for languages where newlines are significant statement separators (like Python or Go).
- **Pure Comment Lines:** A line containing only whitespace and a comment is scanned before indentation calculations run. It never pushes or pops indentation levels, ensuring that inserting a comment inside an indented block will not trigger an indentation mismatch error.
