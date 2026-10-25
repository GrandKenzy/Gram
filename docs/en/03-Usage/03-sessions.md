# Language Sessions (`gram.sessions.Session`)

In **Gram**, lexical catalogs (`lexer.words.MAP_KEYWORDS`, `lexer.words.groups`, `lexer.tokens.MAP_SYMBOLS`) and runtime settings (`gram.config`) are global registries.

When a compiler or tool needs to parse multiple languages or file formats within the same Python process—for example, a toolchain that parses a configuration DSL (`;` comments, docstrings enabled), `.c` source files (`//` comments, C keywords), and `.h` header contracts—**`gram.sessions.Session`** isolates each language's state and switches between them in place.

---

## 1. How `Session` Works

`Session` (`gram.sessions.Session`) captures and restores four global registries:
1. **`words.MAP_KEYWORDS`**: All registered `Keyword` instances.
2. **`words.groups._groups`**: All registered `WordGroup` instances.
3. **`tokens.MAP_SYMBOLS`**: The symbol-to-`Token` lookup dictionary.
4. **`gram.config`**: All uppercase configuration flags (`config.save()` / `config.load()`).

Snapshots are stored inside the `Session` instance as compact tuples, and `session.load()` mutates the global dictionaries in place so existing module references remain valid.

### Constructor Signature

```python
from gram import sessions

session = sessions.Session(
    name: str,
    mode: Literal["Many", "Some"],
    entrypoint: type[RuleItem] | None = None,
)
```

- **`name`**: Descriptive identifier for the session (e.g., `"Session From C"`).
- **`mode`**: Top-level parser mode (`"Many"` for $0..n$ statements or `"Some"` for $1..n$ statements). Passing any other value raises `ValueError`.
- **`entrypoint`**: Optional default root `RuleItem` class used by `session.parse()` when `entrypoint` is not passed at call time.

---

## 2. Session Lifecycle

Defining a language session follows a strict 4-step initialization pattern, followed by `load()` / `tokenize()` / `parse()` at runtime:

| Method | Phase | Action |
| :--- | :--- | :--- |
| `session.clear_global()` | Setup (Step 1) | Calls `words.clear_all()`, clearing `MAP_KEYWORDS` and `words.groups` so previous language keywords do not leak into this session. |
| `session.init()` | Setup (Step 2) | Snapshots the global `gram.config` and `tokens.MAP_SYMBOLS` that were active before configuring this session. |
| *(Configure language)* | Setup (Step 3) | Set `gram.config` flags, register `words.add_group()` / `words.add_keyword()`, register custom symbols, and define/import `RuleItem` classes. |
| `session.migrate()` | Setup (Step 4) | Saves the session's `MAP_KEYWORDS`, `WordGroup`s, `config`, and `MAP_SYMBOLS` into `self`, and restores the pre-session `config` and `MAP_SYMBOLS` snapshot captured by `init()`. |
| `session.load()` | Runtime | Applies this session's saved keywords, word groups, symbols, and `config` to the global registries. (`migrate()` must have been called first, or `RuntimeError` is raised.) |
| `session.tokenize(source, name)` | Runtime | Runs `Lexer(source, name).process()` under the active session state and returns `list[TokenType]`. |
| `session.parse(tokens, name, entrypoint=None, conversion_state=None)` | Runtime | Runs `Parser(tokens, name).parse(entry, self.mode)` using `entrypoint` or `self.entrypoint`; the optional state explicitly shares conversions between files. |

---

## 3. Multi-Language Frontend Example

The following complete, runnable example demonstrates two isolated language sessions—a C-style frontend (`//` comments, `int` keyword) and a Script DSL frontend (`;` comments, `fn` keyword)—coexisting in the same process:

```python
from gram import combinators as cmb
from gram import config, lexer, sessions

# ==============================================================================
# 1. DEFINE SESSION A: C-Style Frontend ("//" comments)
# ==============================================================================
C_SESSION = sessions.Session("C Frontend", "Many")
C_SESSION.clear_global()
C_SESSION.init()

config.LEXER_COMMENT_TOKEN = "//"
config.LEXER_SUPPORT_DOCSTRINGS = False
config.LEXER_IGNORE_EMPTY_LINES = True

lexer.words.add_group("types", color_group="#3B82F6", allow_override=True)
lexer.words.add_keyword("int", group="types", allow_override=True)

class CVarDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.SEMICOLON),
    )

class CProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(CVarDecl))

C_SESSION.entrypoint = CProgram
C_SESSION.migrate()


# ==============================================================================
# 2. DEFINE SESSION B: Script DSL Frontend (";" comments)
# ==============================================================================
SCRIPT_SESSION = sessions.Session("Script Frontend", "Many")
SCRIPT_SESSION.clear_global()
SCRIPT_SESSION.init()

config.LEXER_COMMENT_TOKEN = ";"
config.LEXER_SUPPORT_DOCSTRINGS = True
config.LEXER_IGNORE_EMPTY_LINES = True

lexer.words.add_keyword("fn", hex_color="#FF79C6", allow_override=True)

class ScriptFuncDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("fn"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.Enclosed(
            open=lexer.Token.LPAREN,
            close=lexer.Token.RPAREN,
            content=cmb.MatchToken(lexer.Token.IDENT),
            allow_empty=True,
        ),
    )

class ScriptProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(ScriptFuncDecl))

SCRIPT_SESSION.entrypoint = ScriptProgram
SCRIPT_SESSION.migrate()


# ==============================================================================
# 3. SWITCH SESSIONS AT RUNTIME
# ==============================================================================

# Parse C code using C_SESSION
C_SESSION.load()
c_tokens = C_SESSION.tokenize("int counter; // C comment", "sample.c")
c_ast = C_SESSION.parse(c_tokens, "sample.c")
print("C AST:", c_ast)

# Switch to SCRIPT_SESSION and parse Script DSL code
SCRIPT_SESSION.load()
script_tokens = SCRIPT_SESSION.tokenize("fn main() ; Script comment", "sample.dsl")
script_ast = SCRIPT_SESSION.parse(script_tokens, "sample.dsl")
print("Script AST:", script_ast)
```

Output:

```text
C AST: [AstRef(nodes=3, name=CVarDecl)]
Script AST: [AstRef(nodes=2, name=ScriptFuncDecl)]
```

Notice how in `C_SESSION`, `;` is tokenized as `Token.SEMICOLON` while `// C comment` is stripped as a comment; as soon as `SCRIPT_SESSION.load()` is called, `; Script comment` becomes the comment delimiter and `fn` is recognized as a `Token.KEYWORD`.

### Sharing conversions between files

Each `session.parse()` call starts with isolated conversions when no state is
provided. To preserve additions from one file and use them in another, create
an explicit state:

```python
state = C_SESSION.new_conversion_state()
C_SESSION.parse(header_tokens, "header.h", conversion_state=state)
C_SESSION.parse(source_tokens, "main.c", conversion_state=state)
```

The state can be copied with `state.clone()` or cleared with `state.clear()`.
The external state is updated only when parsing succeeds.

### Multiline delimiter registry

The `MULTLINE` registry (`add_multline()` / `remove_multline()`) is global and
is not included in `Session` snapshots. Register delimiters before creating a
file's `Lexer`, and remove or restore them explicitly when another language
must not see them. Each `Lexer` copies the registry when it is created.
