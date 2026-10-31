# Language Sessions (`gram.sessions.Session`)

> **Module:** `gram.sessions`  
> **Status:** Stable (Version `2.1.0`)  
> **Runtime:** Pure Python 3.12+ (Zero external runtime dependencies)

In multi-language compiler frontends, embedded DSLs, or parallel test suites, sharing global state is an anti-pattern. Global keyword dictionaries, mutable symbol tables, and configuration singletons introduce race conditions, test cross-talk, and unintended syntactic collisions.

`Session` (`gram.sessions.Session`) provides **complete process-wide isolation** for language frontends. Each `Session` encapsulates its own lexicon (`Keyword`), semantic word groups (`WordGroup`), custom symbol mappings (`MAP_SYMBOLS`), configuration flags, predictive parsing revisions, and dedicated engine instances for both `Lexer` and `Parser`.

---

## 1. Architecture & Memory Model

```
                          Python Process Space
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Global Legacy Compatibility State (words.MAP_KEYWORDS, config, etc.)   │
 └───────────────────▲────────────────────────────────▲───────────────────┘
                     │                                │
        session1.init() / migrate()      session2.init() / migrate()
                     │                                │
 ┌───────────────────▼──────────────┐ ┌───────────────▼──────────────────┐
 │      Session: "C-Dialect"        │ │     Session: "SQL-Dialect"       │
 │                                  │ │                                  │
 │ - keywords: {"int", "return"...} │ │ - keywords: {"select", "from"...}│
 │ - groups:   {"types", "storage"} │ │ - groups:   {"verbs", "clauses"} │
 │ - symbols:  {"->", "++", "/*"...}│ │ - symbols:  {"<>", "--", ";"...} │
 │ - config:   {LEXER_COMMENT: "//"}│ │ - config:   {LEXER_COMMENT: "--"}│
 │ - mode:     "Many"               │ │ - mode:     "Some"               │
 │ - entrypoint: CTranslationUnit   │ │ - entrypoint: SQLStatement       │
 │ - lexer:    Lexer (session=self) │ │ - lexer:    Lexer (session=self) │
 │ - parser:   Parser(session=self) │ │ - parser:   Parser(session=self) │
 │ - revision: int (predictive)     │ │ - revision: int (predictive)     │
 └──────────────────────────────────┘ └──────────────────────────────────┘
```

### Process Isolation Invariants

1. **Zero Global Bleed:** Creating, configuring, or mutating a session does not modify global state outside of the temporary `init()` $\to$ `migrate()` setup window.
2. **Independent Tokenization:** Calling `session.tokenize()` runs directly against the session's internal catalogs without needing `session.load()`.
3. **Propagated Parser & AST Context:** `session.parse()` forwards the session context through `Parser` to `ASTAnalyzer`, allowing combinators like `MatchGroup` and `MatchKeyword` to resolve group catalogs dynamically from the calling session.
4. **Predictive Cache Invalidation:** Any mutation to a session's keywords or groups automatically bumps `predictive_revision`, invalidating cached predictive lookahead tables in `Alt` combinators.

---

## 2. Constructor & Properties

### Constructor Signature

```python
Session(
    name: str,
    mode: Literal["Many", "Some"],
    entrypoint: type[RuleItem] | None = None,
)
```

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Logical identifier for the language frontend (used in diagnostic loggers and parser instances). |
| `mode` | `Literal["Many", "Some"]` | Parsing cardinality policy. `"Many"` parses repeated entrypoint statements until `Token.EOF`. `"Some"` evaluates the entrypoint production once. Must be either `"Many"` or `"Some"`, otherwise raises `ValueError`. |
| `entrypoint` | `type[RuleItem] \| None` | Default root grammar rule evaluated during `session.parse()`. Can be overridden per `parse()` call. |

### Instance Attributes (`__slots__`)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `session.name` | `str` | Language session name. |
| `session.mode` | `str` | Parsing mode (`"Many"` or `"Some"`). |
| `session.entrypoint` | `type[RuleItem] \| None` | Root production rule for AST analysis. |
| `session.keywords` | `dict[str, Keyword]` | Isolated catalog of registered language keywords. |
| `session.groups` | `dict[str, WordGroup]` | Isolated catalog of semantic keyword groups. |
| `session.symbols` | `_MapSymbolsDict` | Isolated bidirectional table of symbols and operators. |
| `session.symbol_order` | `list[str]` | Length-sorted symbol list for maximal-munch tokenization. |
| `session.config` | `dict[str, Any]` | Filtered dictionary containing all lexer, parser, AST, error, and log flags owned by this session. |
| `session.lexer` | `Lexer` | Pre-created lexer instance bound to `session=self`. |
| `session.parser` | `Parser` | Reusable parser instance bound to `session=self`. |
| `session.predictive_revision` | `int` | Monotonically increasing revision counter for predictive cache invalidation. |

### Scoped Configuration Keys (`_SESSION_CONFIG_KEYS`)

`Session.config` captures only configuration flags belonging to syntactic, semantic, and diagnostic pipelines:
- Any setting starting with `LEXER_`, `PARSER_`, `AST_`, `ERROR_`, or `INFO_`.
- Core syntactic toggles: `SUPPORT_TRIPLE_DOT`, `SUPPORT_INDENT`, `TOKEN_BOOL_TRUE`, `TOKEN_BOOL_FALSE`, `TOKEN_NULL`, and `LOG_HIDE_CONSOLE`.
- Environment-level settings (such as plugin registries or VSIX generator configurations) remain global and are intentionally excluded from session snapshots.

---

## 3. The Lifecycle State Machine

Gram provides a robust lifecycle for defining, isolating, and activating language sessions:

```
                  ┌────────────────────────┐
                  │ Session Instantiation  │
                  │   Session(name, mode)  │
                  └───────────┬────────────┘
                              │
                              ▼
                      session.init()
          (Snapshots global state, binds words API)
                              │
                              ▼
           ┌──────────────────────────────────────┐
           │     Lexicon & Symbol Registration    │
           │  session.add_keyword() / add_group() │
           │  config / session.config mutations   │
           └──────────────────┬───────────────────┘
                              │
                              ▼
                     session.migrate()
         (Freezes session, unbinds API, restores globals)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       session.tokenize()             session.load()
        session.parse()            (Legacy global export)
  (Fully isolated execution)
```

### Phase 1: `init()`
Prepares isolated storage and routes process-wide registrations to this session:
1. Snapshots the active global state: `words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS`, `tokens.MAP_SYMBOLS`, and `config.save()`.
2. Clones the global symbols into `session.symbols` and re-indexes them.
3. Filters and copies configuration into `session.config`.
4. Invokes `words.bind_session(self)`: All loose registration functions (`words.add_keyword()`, `words.add_group()`) are redirected to populate this session instead of global dictionaries.

### Phase 2: Registration
While inside the `init()` $\to$ `migrate()` window, register keywords, groups, and settings:

```python
from gram import config
from gram.sessions import Session

session = Session("C-Subset", "Many")
session.init()

# 1. Register groups and keywords directly or via words
session.add_group("types", color_group="#3B82F6")
session.add_keyword("int", group="types")
session.add_keyword("return", hex_color="#FF79C6")

# 2. Configure session-scoped lexer settings
config.LEXER_COMMENT_TOKEN = "//"
config.LEXER_BLOCK_COMMENT_TOKEN = "/*"
config.SUPPORT_INDENT = False
```

### Phase 3: `migrate()`
Freezes the session's configuration and restores the global process state:
1. Packages `session.keywords`, `session.groups`, `session.symbols`, and `session.config` into frozen session attributes (`session.words`, `session.group`, etc.).
2. Unbinds the session via `words.unbind_session(self)`.
3. Restores the global dictionaries (`words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS`, `tokens.MAP_SYMBOLS`) and loads the saved configuration snapshot back into `gram.config`.
4. Bumps `_predictive_revision`.

> [!IMPORTANT]
> Once `migrate()` finishes, the session is completely self-contained. It can tokenize and parse inputs independently without modifying or reading from global dictionaries.

### Phase 4: `load()` (Legacy Compatibility)
Activates the session's state into the global process-wide dictionaries:
- Overwrites `words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS`, and `tokens.MAP_SYMBOLS` with this session's catalogs.
- Loads `session.config` into `gram.config`.
- Sets `session._loaded = True`. Subsequent direct registrations via `session.add_keyword()` or `session.add_group()` immediately synchronize into the global dictionaries via `_sync_legacy_catalog()`.
- Raises `RuntimeError` if called before `migrate()`.

### Phase 5: `clear_global()`
Clears the session's internal `keywords` and `groups` dictionaries. If called prior to `init()` (before any restore snapshot is taken), it also clears the global `words.MAP_KEYWORDS` and `words._GLOBAL_GROUPS` dictionaries.

---

## 4. Execution Pipeline (`tokenize` & `parse`)

### Tokenization: `session.tokenize()`

```python
def tokenize(self, source: list[str] | str, name: str) -> list[TokenType]:
```

Tokenizes `source` using `session.lexer`. Because `session.lexer` holds a reference to `self`, all keyword lookups, word groups, custom symbols, and configuration flags are resolved directly from `session.keywords`, `session.symbols`, and `session.config`.

```python
tokens = session.tokenize("int counter = 42; // initialize", "main.c")
```

### Parsing: `session.parse()`

```python
def parse(
    self,
    tokens: list[TokenType],
    name: str,
    entrypoint: type[RuleItem] | None = None,
    *,
    conversion_state: ConversionState | MutableMapping[str, ConversionTarget] | None = None,
    trace: Literal["off", "basic", "detailed"] = "basic",
) -> list[ASTNode]:
```

Executes syntax analysis and AST generation:
1. Resolves the root rule: uses `entrypoint` if provided, falling back to `self.entrypoint`. If neither is defined, raises `RuntimeError("No se especificó una entrada")`.
2. Resets the reusable `session.parser` instance with `tokens`, compilation unit `name`, and optional conversions.
3. Propagates `session=self` to `Parser` and `ASTAnalyzer`. Combinators such as `MatchGroup` resolve group membership against `session.groups`.
4. Evaluates the grammar in accordance with `session.mode` (`"Many"` or `"Some"`).
5. If parsing succeeds and `conversion_state` is provided, exports any newly registered token conversions back to `conversion_state`.
6. Returns the resulting `list[ASTNode]`.

---

## 5. Multi-Unit State Transfer: `ConversionState`

In languages with modular compilation units (such as C `#include` headers, DSL import statements, or macro type declarations), type definitions or aliases discovered in one file must often transfer to subsequent files without leaking into unrelated sessions.

Gram manages this explicitly and safely through `ConversionState` (`gram.core.parser.ConversionState`):

```python
from gram.core.parser import ConversionState

# 1. Initialize a conversion state for the compilation project
conv_state = session.new_conversion_state()

# 2. Parse header file (registers typedefs/conversions via Convert(..., scope=True))
session.parse(header_tokens, "types.h", conversion_state=conv_state)

# 3. Parse main source file inheriting conversions from the header
session.parse(source_tokens, "main.c", conversion_state=conv_state)
```

### Transactional Guarantees

If a file fails to parse due to a syntax error or conflict, **`conversion_state` is not updated**. The external state remains rolled back to its pre-parse state, preventing malformed source files from corrupting shared compilation context.

### `ConversionState` API

| Method | Return Type | Description |
| :--- | :--- | :--- |
| `state.export()` | `dict[str, ConversionTarget]` | Returns a detached copy of all registered conversions. |
| `state.replace(source)` | `None` | Replaces all conversions with a validated copy of `source`. |
| `state.register(name, target, *, replace=False)` | `None` | Registers an identifier $\to$ `Token` conversion. Raises `ValueError` on conflicts unless `replace=True`. |
| `state.clear()` | `None` | Clears all registered conversions. |
| `state.clone()` | `ConversionState` | Returns an independent duplicate instance. |

---

## 6. Predictive Grammar Invalidation (`predictive_revision`)

Gram's combinator library features predictive alternatives (`Alt`), which analyze token lookahead and cache branch decisions for $O(1)$ dispatch.

When a session's lexicon or symbols change dynamically:
1. `session._touch_predictive_revision()` increments `session._predictive_revision`.
2. Automatically triggers `_touch_predictive_epoch()` in `gram.core.combinators.base`.
3. All predictive combinators inspect the revision epoch, invalidating stale lookup tables on-the-fly without requiring manual cache busting.

---

## 7. Catalog Inspection Methods

`Session` provides safe query methods that inspect its internal catalogs without mutating global state:

```python
# 1. Retrieve a Keyword instance or None
kw = session.get_keyword("int")

# 2. Retrieve a WordGroup instance or None
group = session.get_group("types")

# 3. Check group existence
exists = session.group_exists("types")

# 4. Check membership in O(1) time
is_member = session.exists_in_group("int", "types")

# 5. Total registered keywords in this session
count = session.keyword_count()
```

---

## 8. Complete Multi-Language Integration Example

Below is a production-grade pattern demonstrating two completely distinct frontends (a C-like language and an SQL-like query language) running concurrently in the same process:

```python
from gram import combinators as cmb
from gram.core.lexer import Token
from gram.sessions import Session

# ---------------------------------------------------------------------------
# 1. Grammar Productions
# ---------------------------------------------------------------------------
class VarDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(Token.IDENT),
        cmb.MatchToken(Token.ASSIGN),
        cmb.MatchToken(Token.NUMBER),
        cmb.MatchToken(Token.SEMICOLON),
    )

class CProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(VarDecl))

class SelectQuery(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("select"),
        cmb.MatchToken(Token.IDENT),
        cmb.MatchKeyword("from"),
        cmb.MatchToken(Token.IDENT),
    )

class SQLProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(SelectQuery))

# ---------------------------------------------------------------------------
# 2. Setup Session 1: C Frontend
# ---------------------------------------------------------------------------
c_session = Session("C-Frontend", "Many", entrypoint=CProgram)
c_session.init()
c_session.add_group("types")
c_session.add_keyword("int", group="types")
c_session.add_keyword("float", group="types")
c_session.config["LEXER_COMMENT_TOKEN"] = "//"
c_session.config["SUPPORT_INDENT"] = False
c_session.migrate()

# ---------------------------------------------------------------------------
# 3. Setup Session 2: SQL Frontend
# ---------------------------------------------------------------------------
sql_session = Session("SQL-Frontend", "Some", entrypoint=SQLProgram)
sql_session.init()
sql_session.add_keyword("select")
sql_session.add_keyword("from")
sql_session.config["LEXER_COMMENT_TOKEN"] = "--"
sql_session.migrate()

# ---------------------------------------------------------------------------
# 4. Independent Tokenization and Parsing
# ---------------------------------------------------------------------------
c_source = "int score = 100; // C comment\nfloat ratio = 2;"
c_tokens = c_session.tokenize(c_source, "game.c")
c_ast = c_session.parse(c_tokens, "game.c", trace="off")

sql_source = "select username from users -- SQL comment"
sql_tokens = sql_session.tokenize(sql_source, "query.sql")
sql_ast = sql_session.parse(sql_tokens, "query.sql", trace="off")

print(f"C AST Nodes generated: {len(c_ast)}")      # 2 VarDecl nodes
print(f"SQL AST Nodes generated: {len(sql_ast)}")  # 1 SelectQuery node

# Notice: 'int' is NOT recognized as a keyword in the SQL session
mixed_test = sql_session.tokenize("int score", "test.sql")
print(mixed_test[0].token)  # Token.IDENT (not Token.KEYWORD!)
```
