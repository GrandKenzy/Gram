# Gram `2.0.0b3`

**Release date:** 2026-10-26

This maintenance beta improves parser performance while preserving the public
grammar and diagnostic behavior of the previous release.

## Added

- `Parser.parse()` and `Session.parse()` now accept `trace="off"`,
  `trace="basic"`, or `trace="detailed"`. The default remains `basic` for
  compatibility.
- Generic parser-scaling benchmark and regression coverage for trace modes,
  session forwarding, checkpoints, and error-origin caching.

## Changed

- Raytracing checkpoints retain compact references and lengths, postponing
  list copies until a rollback is actually performed.
- Error-origin path resolution is cached by filename and working directory to
  reduce repeated filesystem work during speculative diagnostics.

## Verification

- Full Gram test suite: 185 tests passed.
- EasyC compatibility check: `vnma run main.py examples/modern_example`
  completed successfully and generated the example executable.
