# Changelog

All notable changes to Gram are documented in this file.
Versions follow [PEP 440](https://peps.python.org/pep-0440/) (`2.0.0b1` = 2.0.0 Beta 1).

## [2.0.0b1] - 2026-10-23

### ⚠️ Breaking changes

#### `ERROR_EXIT_ON_ERROR` now defaults to `True`

Previously `gram.config.ERROR_EXIT_ON_ERROR` was `False`. It is now **`True`**,
so any reported error that is not explicitly suppressed makes Gram raise it
and terminate the process (`Error.raise_error()` → `sys.exit`) instead of
being recorded and parsing continuing.

**Who is affected:** code that relies on the default configuration to collect
several diagnostics in one pass (editors, linters, test suites, custom tools).

**How to keep the previous behaviour:**

```python
from gram import config

config.ERROR_EXIT_ON_ERROR = False          # globally

# or temporarily, restoring the previous value afterwards
previous = config.ERROR_EXIT_ON_ERROR
config.ERROR_EXIT_ON_ERROR = False
try:
    ...                                      # lex / parse / analyze
finally:
    config.ERROR_EXIT_ON_ERROR = previous
```

Notes:
- The bundled LSP server (`gram.vsix.lsp`) already disables it while analyzing
  documents, so IDE tooling is unaffected.
- Error hooks can still return `ErrorAction.OMIT` (drop the error) or
  `ErrorAction.SUPPRESS_RAISE` (store it without exiting) regardless of this
  setting.
- `Session.migrate()` / `Session.load()` restore and re-apply this value per
  language session.

#### Removed configuration variables

`DATA_DIR`, `RULE_SET_WORK_INT` and `INFO_FLATTEN_OUTPUT` were removed from
`gram.config` (and from its `__all__`). They were unused inside the framework.
Importing or reading them now raises `AttributeError`.

### Added
- `ASTAnalyzer(..., trace="off" | "basic" | "detailed")`. `detailed` records
  every combinator's cursor span and outcome (`SUCCESS`, `FAILED`, `CONTROL`,
  `ERROR`) via `RayTracing.begin()` / `end()` / `TraceRecord`, and reports
  backtracks through `RayTracing.observe_position()`; use
  `RayTracing.detailed()` for a readable report.
- `ASTAnalyzer.close()` and `RayTracing.close()` detach the parser observer and
  release rollback snapshots while keeping results readable.
- `Parser._restore_from_pos`: cursor position abandoned by the last `restore()`.
- `Diagnostics.failure_scope()`: isolates the failure candidate of speculative
  attempts. `Alt`, `Opt`, `Many`, `Some`, `Sep`, `Until`, `If`, `Not`, `Peek`
  and expression parsing use it so a discarded branch cannot leak diagnostics.
- `config.INFO_INIT` and `config.INFO_GENERATE_LOGFILE_ON_ERROR`; both are
  saved and restored per `Session`.
- New test suites for fuzzing, regressions, checkpoints and trace modes
  (134 tests in total).

### Fixed
- `Seq` only intercepts `SkipFlowSignal`; `Abort`, `Backtrack`, `Break` and
  `Cut` signals now propagate to the combinator that owns them.
- `CutFlowSignal` carries its failure candidate up to `Alt`.
- Parser checkpoints restore tokens replaced more than once.
- `report_error` honours hook decisions and the exit policy consistently.
- Lexer: multi-character comment markers and multiline literals.

## [2.0.0b0]

Initial 2.0.0 beta: Pratt expression engine, `RayTracing` telemetry, `Hookr`
observers, `TokenInfo` snapshots and VNMA compatibility.
