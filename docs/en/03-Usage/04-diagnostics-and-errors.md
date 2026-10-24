# Diagnostics & Error System

Gram includes a hierarchical diagnostic telemetry engine (`gram.utilities.Diagnostics`, `gram.utilities.info`) and a formal 5-dimension error catalog (`gram.errors`, `gram.utilities.error`).

Both `ParseState` (`Parser`) and `ASTState` (`ASTAnalyzer`) subclass `Diagnostics`, and you can also subclass `Diagnostics` directly in your own compiler stages (such as semantic analyzers or code generators).

---

## 1. Using `Diagnostics` for Hierarchical Telemetry

`Diagnostics` (`gram.utilities.Diagnostics`) manages a tree of telemetry `Node` objects backed by `StackInfo` (`gram.utilities.info.StackInfo`).

### Subclassing or Instantiating `Diagnostics`

```python
from gram.utilities import Diagnostics

class CompilerState(Diagnostics):
    def __init__(self) -> None:
        super().__init__(
            file="compiler-log",         # Log file name under ./log/
            name="COMPILER",             # Root telemetry node title
            description="Semantic pass", # Root node description
            expose_nodes=True,           # Render child nodes when stringifying
            generate_log_file=False,     # Set True to register ./log/compiler-log.log immediately
            generate_on_error=False,     # Set True to flush log file at process exit (atexit)
        )
```

### Emitting Notes and Building Telemetry Subtrees

- **Logging methods on `Diagnostics`:**
  - `diag.debug(msg)` $\rightarrow$ emits a `'normal'` note on the active node.
  - `diag.warn(msg)` $\rightarrow$ emits a `'warn'` note.
  - `diag.advice(msg)` $\rightarrow$ emits an `'advice'` note.
  - `diag.success(msg)` $\rightarrow$ emits a `'success'` note.
  - `diag.error(msg)` $\rightarrow$ emits an `'error'` note.
- **Scoping child nodes (`node` and `down`):**
  - `diag.node(name, description="", set_target=True)` creates a child telemetry `Node` under the current target and pushes it onto `self._targets` when `set_target=True`.
  - `diag.down()` pops the active node from `self._targets`, returning focus to its parent node.

```python
from gram.utilities import Diagnostics

diag = Diagnostics(
    file="semantic",
    name="SEMANTIC",
    description="Type checking pipeline",
    expose_nodes=True,
)

diag.debug("Starting module resolution")
diag_node = diag.node("CheckFunction", "Validating fn 'main'", set_target=True)
try:
    diag.advice("Return type inferred as 'int'")
    diag.success("Function 'main' validated")
finally:
    diag.down()

# Render the hierarchical telemetry tree as text (or print via diag.stack.console()):
print(diag.stack.stringify(ansi=False))
```

### Persisting Telemetry Logs to Disk

- Calling `diag.stack.write()` writes the formatted tree to `./log/<file>.log` via `gram.utilities.info.Log`.
- Calling `gram.utilities.info.StackInfo.show_all()` flushes all registered `StackInfo` instances.
- For built-in Gram phases (`LexerState`, `Parser`, `ASTAnalyzer`), telemetry verbosity and automatic log file creation are controlled by `gram.config`:
  - `config.LEXER_ADD_INFO`, `config.PARSER_ADD_INFO`, `config.AST_ADD_INFO` (default `False`).
  - `config.INFO_GENERATE_LOGFILE` (default `False`) and `config.INFO_GENERATE_LOGFILE_ON_ERROR` (default `False`).

---

## 2. Structured OSGDC Errors (`gram.errors`)

All formal exceptions in Gram inherit from `gram.utilities.error.Error` and carry a 5-character **OSGDC** code (`CodeError`) defined in `gram.errors`.

### The 5 OSGDC Dimensions

Every `CodeError` formats as `<Type>-<O><S><G><D><C> · <Name>` (for example, `S-12411 · Gram.Parser.UnexpectedToken`), where `S` indicates a standard in-bounds code:

| Position | Dimension | Values in `gram.errors` |
| :--- | :--- | :--- |
| **`O`** | **Origin** | `0`: Unknown (`CODE_UNKNOWN_ORIGIN`), `1`: Native (`CODE_NATIVE_ERROR`), `2`: Plugin (`CODE_PLUGIN_ERROR`) |
| **`S`** | **Scope** | `0`: Unknown, `1`: Lexer, `2`: Parser, `3`: Grammar/AST, `4`: Semantic, `5`: Compilation/DSL |
| **`G`** | **Gravity** | `0`: Minor, `1`: Implementation Error, `2`: Obsolete, `3`: Internal, `4`: Fatal |
| **`D`** | **Documentation** | `0`: Documented, `1`: Documented & Traceable, `2`: Not Documented |
| **`C`** | **Condition** | `0`: Usable, `1`: Requires Repair, `2`: Should Repair |

### Domain Error Classes

`gram.errors` provides 8 domain-specific subclasses of `Error`:
- `errors.LexerError` (e.g., `LEXER_UNEXPECTED_CHARACTER`, `LEXER_UNCLOSED_STRING`, `LEXER_INDENTATION_MISMATCH`)
- `errors.ParserError` (e.g., `PARSER_UNEXPECTED_TOKEN`, `PARSER_EARLY_EOF`, `PARSER_SYNTAX_ERROR`)
- `errors.GrammarError` (e.g., `GRAMMAR_COMBINATOR_FAILED`, `GRAMMAR_RULE_NOT_FOUND`, `GRAMMAR_COMBINATOR_UNSUPPORTED`)
- `errors.ASTError` (e.g., `AST_PROGRAM_RULE_NOT_FOUND`, `AST_PROGRAM_INVALID_COMBINATOR`, `AST_DECLARATOR_INVALID_ELEMENT`)
- `errors.SemanticError` (e.g., `SEMANTIC_TYPE_MISMATCH`, `SEMANTIC_UNDEFINED_SYMBOL`, `SEMANTIC_DUPLICATE_SYMBOL`, `SEMANTIC_SCOPE_VIOLATION`)
- `errors.CompilationError`
- `errors.PluginError`
- `errors.SystemError`

### Creating and Raising a Structured Error

```python
from gram import config, errors

err = errors.SemanticError(
    "TypeMismatch",
    errors.SEMANTIC_TYPE_MISMATCH,
    "Cannot assign value of type 'str' to variable 'count' of type 'int' at line 4, column 10.",
    "Convert the expression to 'int' or change the variable type declaration.",
)

# Format without raising:
print(err.stringify(ansi=False))
```

Output:

```text
|---------------- ERROR -----------------|
Name: TypeMismatch, Type: SemanticError.

CAUTION: Cannot assign value of type 'str' to variable 'count' of type 'int' at line 4, column 10.

Convert the expression to 'int' or change the variable type declaration.

INF:
    FILE: unknown
    ORIGIN: ...
    CODE: S-14411 · Gram.Semantic.TypeMismatch

|------------- END OF ERROR -------------|
```

### Exit Policy (`config.ERROR_EXIT_ON_ERROR`) & `StackError`

When `err.raise_error()` (or `parser.report_error(err)` / `analyzer.report_error(err)` outside `safe_mode()`) is called:
1. Unless `config.ERROR_HIDE_CONSOLE` is `True`, the error box is printed to stdout.
2. If `config.ERROR_EXIT_ON_ERROR` is `True` (**the default in `2.0.0b1`**), Gram calls `sys.exit(1)`.
3. If `config.ERROR_EXIT_ON_ERROR` is `False`, Gram raises `err` as a Python exception.

To track errors in the global `StackError` registry (`gram.utilities.error.StackError`) and dump them to `./log/error.log`:
- `StackError.add(err)` appends an error.
- `StackError.all()`, `StackError.last()`, `StackError.count()`, `StackError.clear()` inspect or reset the stack.
- `StackError.write()` writes all accumulated errors in plain text to `log/error.log`.

---

## 3. Non-Invasive Error Interception (`Diagnostics.hook_errors`)

When building an IDE Language Server (`LSPState`), a multi-error linter, or a test suite, you often want to run the lexer and parser **without** `sys.exit(1)` terminating the process or raising an unhandled exception, while still collecting every `Error` object.

`Diagnostics` provides instance-level hooks (`diag.add_hook(fn)`) and a global context manager (`Diagnostics.hook_errors(fn)`). Each hook receives `(sender, err)` and returns an `ErrorAction` directive (`gram.utilities.ErrorAction`):

| Directive | Constant | Effect |
| :--- | :--- | :--- |
| `"store"` | `ErrorAction.STORE` | Default behavior: appends `err` to `sender._errors` and respects `config.ERROR_EXIT_ON_ERROR`. |
| `"suppress"` | `ErrorAction.SUPPRESS_RAISE` | Appends `err` to `sender._errors`, sets `err._suppress_raise = True`, and **prevents** printing, raising, or calling `sys.exit(1)`. |
| `"omit"` | `ErrorAction.OMIT` | Completely ignores `err`: does **not** store it in `sender._errors` and does **not** raise or exit. |
| `"raise"` | `ErrorAction.RAISE` | Appends `err` to `sender._errors` and immediately invokes `err.raise_error()`. |

### Example: Collecting Syntax Errors Without Exiting

```python
from gram import combinators as cmb
from gram import lexer, parser
from gram.utilities import Diagnostics, ErrorAction, error

class Stmt(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.ASSIGN),
        cmb.MatchToken(lexer.Token.NUMBER),
    )

class Program(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(Stmt))

captured: list[error.Error] = []

def intercept_errors(sender: object, err: error.Error) -> str:
    captured.append(err)
    return ErrorAction.SUPPRESS_RAISE

# Parse malformed input ("x = ;" instead of "x = 1") without exiting or printing to console
with Diagnostics.hook_errors(intercept_errors):
    tokens = lexer.Lexer("x = ;").process()
    ast_nodes = parser.Parser(tokens).parse(Program)

print("Captured errors:", len(captured))
print("Deepest error name:", captured[0].name)
print("Error code:", captured[0].code.stringify())
```

Output:

```text
Captured errors: 2
Deepest error name: TokenMismatch
Error code: S-12411 · Gram.Parser.UnexpectedToken
```
