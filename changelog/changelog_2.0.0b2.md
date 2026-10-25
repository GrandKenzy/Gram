# Gram `2.0.0b2`

**Release date:** 2026-10-25

This release remains **Beta** and expands the lexer/parser foundations for
language frontends, especially C-style preprocessing and multi-file parsing.

> **Beta 2** · Configurable lexer, preprocessing combinators, and isolated state

## Added

- Configurable recognition for prefixed strings (`L"..."`, `u"..."`,
  `U"..."`, `u8"..."`) and leading-dot numbers (`.5`).
- `TokenType.flags` with `SIMPLE_QUOTE` and `CHAR` in
  `gram.core.lexer.flags`; quoted character literals now remain
  `Token.STRING` instead of using a special `Token.CHAR` member.
- Extensible multiline delimiter registry through `MULTLINE`,
  `add_multline()`, `remove_multline()`, and `list_multline()`.
- Configurable boolean/null spellings through `TOKEN_BOOL_TRUE`,
  `TOKEN_BOOL_FALSE`, and `TOKEN_NULL`.
- `SUPPORT_INDENT` for disabling `INDENT`/`DEDENT` emission.
- `Preprocess`, `Convert`, and `Expected` combinators, including parser-local
  conversion checkpoints and explicit conversion sharing through sessions.
- Optional isolated storage mappings for `Save` and `Load`, useful for typedefs
  and dynamic type state.
- Exhaustive regression coverage for C `define`-style conversions, conversion
  isolation, multiline scanning, lexer flags, and configurable literals.

## Changed

- Triple-quoted literals and configured block comments now use the shared
  multiline scanner while preserving string escape decoding.
- Logical token matching consults active conversions without rewriting the
  physical token stream.
- Removed historical public API aliases; canonical names such as `Seq`,
  `MatchSeqSymbol`, `TokenInfo`, `advance`, `ran`, `branches`, and
  `not_exists`, plus `in_failure_context` for speculative state, are now the
  only supported names.

## Documentation

- Synchronized Spanish and English guides, indexes, installation references,
  beta status pages, sessions, storage, and preprocessing documentation.
- Documented `Preprocess` as an experimental, high-responsibility extension
  point with guidance for checkpoints, rollback, sessions, conversions,
  isolated storage, expectations, and tracing.
