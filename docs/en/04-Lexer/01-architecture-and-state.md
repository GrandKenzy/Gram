# Architecture & State Management

The core lexical engine in `gram.core.lexer` is built on a clean two-class architecture:

1. **`LexerState` (`gram.core.lexer.control`):** The foundational state manager. Inherits from `Diagnostics` and tracks source lines, physical cursor coordinates (`line` and `col`), the semantic indentation stack (`indents`), the comment collector (`comments`), and dynamic configuration resolution.
2. **`Lexer` (`gram.core.lexer.core`):** The high-level facade. Inherits from `LexerState` and implements the primary `process()` scanning loop, keyword precondition validation (`check_state()`), and factory methods (`tokenize()`, `stream()`).

---

## 1. Source Code Ingestion (`_load_source`)

`Lexer` accepts source code in three distinct formats:

```python
from pathlib import Path
from gram.core.lexer import Lexer, words

# Always ensure at least one keyword is registered before lexing
words.add_keyword("fn", allow_override=True)

# 1. From a plain string
lexer_str = Lexer("fn main() { return 0; }")

# 2. From a sequence of line strings
lexer_lines = Lexer(["fn calculate(x) {", "    return x * 2;", "}"])

# 3. From a pathlib.Path on disk
source_path = Path("examples/script.gram")
lexer_file = Lexer(source_path)
```

### Loading Semantics

| Ingestion Type | Processing Details | Error Handling |
| :--- | :--- | :--- |
| `str` | Split into individual line strings using Python's native `.splitlines()`. | None. Empty strings produce an empty line list resulting in a single `Token.EOF`. |
| `Sequence[str]` | Each string element has trailing `\r` and `\n` characters stripped via `.rstrip('\r\n')`. | Preserves leading whitespace and empty lines for indentation calculations. |
| `Path` | Validated for file existence. Reads the file using UTF-8 encoding and splits into lines. Also sets `Format.FileTar` for diagnostic stack traces. | If the file does not exist, logs an error to diagnostics and raises `LexerError` (`LEXER_FILE_NOT_FOUND`). |

---

## 2. Cursor Coordinates & Navigation Primitives

`LexerState` maintains fine-grained character and line pointers:

- **`self.line` (`int`):** Current line index (0-based internally). When emitted in a `TokenType` or reported in an error, it is converted to **1-based** (`self.line + 1`).
- **`self.col` (`int`):** Current column character offset on the active line (0-based raw index).
- **`self.source` (`list[str]`):** The loaded list of physical line strings.

### Navigation API

| Method / Property | Return Type | Description |
| :--- | :--- | :--- |
| `lexer.currline` | `str` | Returns `self.source[self.line]` if `self.line` is in bounds; otherwise returns `""`. |
| `lexer.has_lines()` | `bool` | Returns `True` if `self.line < len(self.source)`. |
| `lexer.is_empty()` | `bool` | Returns `True` if `self.currline.strip() == ""`. |
| `lexer.peek(offset=0)` | `str` | Inspects the character at `self.col + offset` on the current line without advancing the cursor. Returns `""` if the target column is out of range. |
| `lexer.advance(steps=1)` | `str` | Returns the character at the current cursor (`peek()`) and increments `self.col` by `steps`. |

```python
# Example: manual inspection during custom scanning
lexer = Lexer("alpha := 10")
print(lexer.currline)      # "alpha := 10"
print(lexer.peek())          # "a"
print(lexer.peek(1))         # "l"
char = lexer.advance(5)      # Consumes "alpha", returns "a"
print(lexer.col)             # 5
print(lexer.peek())          # " "
```

---

## 3. Dynamic Configuration & Catalog Bridging

`LexerState` instances may run either in standalone mode (reading from `gram.config` and the global `words.MAP_KEYWORDS`) or within an isolated `Session`. `LexerState` abstracts this duality through uniform accessor methods:

```python
# Internal resolution pattern in LexerState
def get_config(self, name: str, default=None):
    if self.session is not None:
        return self.session.config.get(name, getattr(config, name, default))
    return getattr(config, name, default)

def get_keyword(self, name: str):
    if self.session is not None:
        return self.session.get_keyword(name)
    from gram.core.lexer import words
    return words.get_keyword(name)

def get_symbols(self):
    if self.session is not None:
        return self.session.symbols
    return tokens.MAP_SYMBOLS
```

This guarantees that a lexer configured inside a session will never leak keywords, symbols, or configuration flags into global state or other threads.

---

## 4. Precondition Validation: `check_state()`

Before the lexical scanning loop executes, Gram calls `check_state(self.session)`.

```python
def check_state(session=None) -> int:
    count = session.keyword_count() if session is not None else words.count_keywords()
    if count == 0:
        errors.LexerError(
            "EmptyKeywords",
            errors.LEXER_EMPTY_KEYWORDS,
            "No se encontró ninguna palabra clave registrada.",
            "Registre al menos una palabra clave mediante words.add_keyword() antes de ejecutar el Lexer.",
        ).raise_error()
    return count
```

> [!IMPORTANT]
> Gram requires at least one registered keyword before executing lexical analysis. If `Lexer(source).process()` is invoked on an empty catalog, it immediately raises `LexerError` with code `LEXER_EMPTY_KEYWORDS`.
> If your DSL has no reserved keywords yet, register a dummy or sentinel keyword:
> ```python
> words.add_keyword("dummy", allow_override=True)
> ```

---

## 5. The Main Scanning Loop (`process()`)

Calling `Lexer.process()` runs the single-pass scanning pipeline:

```python
def process(self) -> list[TokenType]:
```

### Execution Flowchart

```
                 process() Called
                        │
                        ▼
            check_state(self.session)
                        │
                        ▼
         Initialize tokens_list: list[TokenType]
                        │
         ┌──────────────┴──────────────┐
         ▼                             │
  while self.has_lines():              │
         │                             │
    Is line empty? ───► YES ───► Emit NEWLINE (if not ignored)
         │                       Advance line, reset col = 0
         ▼ NO                          │
    Comment-only line? ──► YES ──► Save comment (if enabled)
         │                         Advance line, reset col = 0
         ▼ NO                      (Does NOT alter indents stack)
    1. process_indent() ──► Append INDENT / DEDENT tokens
         │
    2. while self.col < len(currline):
         │
         ├─► char in " \r\t" ──► advance()
         ├─► multiline_match() ──► process_multiline()
         ├─► is_comment_start() ──► process_comment()
         └─► visitors.visit(self, char) ──► tokens_list.append(token)
         │
    3. Emit NEWLINE (if LEXER_IGNORE_NEWLINES is False)
       Advance line, reset col = 0
         │
         └──────────────┬──────────────┘
                        │
         (All lines processed)
                        ▼
    4. Unwind remaining indentation:
       while len(self.indents) > 1:
           emit Token.DEDENT
                        │
                        ▼
    5. Append terminal Token.EOF
                        │
                        ▼
             return tokens_list
```

### Step-by-Step Breakdown

1. **Pre-flight Assertion:** Runs `check_state()`. If no keywords are found, analysis halts immediately.
2. **Diagnostic Framing:** If `LEXER_ADD_INFO` is enabled, pushes a `"LexingProcess"` diagnostic node into the `Diagnostics` stack.
3. **Empty Line Check:** If `self.currline.strip() == ""`:
   - If `LEXER_IGNORE_EMPTY_LINES=False` and `LEXER_IGNORE_NEWLINES=False`, appends `TokenType(Token.NEWLINE, None, line, 0)`.
   - Advances to the next line (`self.line += 1`, `self.col = 0`) without altering indentation.
4. **Pure Comment Lines:** If a line contains only whitespace followed by a single-line comment, the comment is scanned, optionally saved to `self.comments`, and the line advances immediately. Crucially, **pure comment lines never change the indentation stack**.
5. **Indentation Tracking:** Calls `self.process_indent()`. Leading spaces or tabs are converted into a visual column width. If the indentation level increases, `Token.INDENT` is pushed; if it decreases, one or more `Token.DEDENT` tokens are emitted.
6. **Character Scanning:** Inner loop scans left-to-right across `self.currline`:
   - Inline whitespace (`' '`, `'\t'`, `'\r'`) is advanced and skipped.
   - Multiline literals (`"""`, `'''`, or custom delimiters from `add_multline`) take precedence and can consume characters across multiple physical lines.
   - Comments (`#`, `//`, or block comments `/*`) consume the rest of the line (or block) and break or continue the line scan.
   - Non-comment characters are delegated to `visitors.visit(self, char)`.
7. **Line Termination:** If `LEXER_IGNORE_NEWLINES=False`, appends `TokenType(Token.NEWLINE, None, line, col)` before moving to the next line.
8. **Indentation Unwinding at EOF:** When all source lines are exhausted, any open indentation blocks (`len(self.indents) > 1`) are popped, emitting corresponding `Token.DEDENT` tokens.
9. **EOF Sentinel:** Emits `TokenType(Token.EOF, None, line, col)` as the guaranteed final token in the list.

---

## 6. Helper & Factory Methods

Beyond `process()`, `Lexer` provides two ergonomic methods:

### `tokenize(source, logfile=None) -> list[TokenType]`
Creates a new `Lexer` instance sharing the current session and configuration, tokenizing `source` without mutating the state of the current lexer object:

```python
lexer = Lexer("fn first()", session=my_session)
tokens1 = lexer.process()

# Re-tokenize alternative source using the same session configuration:
tokens2 = lexer.tokenize("fn second()")
```

### `stream() -> TokenStream`
Runs `process()` and wraps the resulting token list directly into a `TokenStream` instance for cursor-based navigation:

```python
from gram.core.lexer import Lexer, TokenStream

stream: TokenStream = Lexer("let x = 42;").stream()
print(stream.current())  # TokenType(token=Token.KEYWORD, value='let', line=1, col=0)
```
