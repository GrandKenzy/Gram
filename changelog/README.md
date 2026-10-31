# Gram · Changelog

<p align="center">
  <strong>Versioned release notes for the Gram framework</strong><br>
  Lexer, parser combinators, sessions, diagnostics, and language tooling.
</p>

---

## Current release

### [`3.0.0`](changelog_3.0.0.md) · Stable

The current stable release is `3.0.0`. Its release notes are kept in one file
and are extended as changes are made during the release cycle.

> [!IMPORTANT]
> Earlier `2.0.0b*` files are historical beta release notes. They are not the
> current project status.

## Release timeline

| Version | Date | Main focus | Notes |
| --- | --- | --- | --- |
| [`3.0.0`](changelog_3.0.0.md) | 2026-10-31 | C AOT compiler, GIR 1.0 IR format, CaptureRaw, and multi-backend engine | Current |
| [`2.0.0b3`](changelog_2.0.0b3.md) | 2026-10-26 | Parser performance and telemetry | Historical |
| [`2.0.0b2`](changelog_2.0.0b2.md) | 2026-10-25 | Configurable lexer and preprocessing | Historical Beta 2 |
| [`2.0.0b1`](changelog_2.0.0b1.md) | 2026-10-23 | Diagnostics, sessions, and checkpoints | Historical Beta 1 |
| [`2.0.0b0`](changelog_2.0.0b0.md) | — | Parser foundations and tooling | Historical initial beta |

## How to read these notes

Each release has exactly one `changelog_*.md` file. Append all notes for that
version to the same file; do not create a new changelog for every individual
change. Entries are grouped by impact:

- **Breaking changes:** behavior or API changes that may require migration.
- **Added:** new public capabilities and configuration.
- **Changed:** modifications to existing behavior.
- **Fixed:** corrected bugs and regressions.
- **Documentation:** synchronized guides, examples, and release references.

## Repository conventions

Central detects release notes from files matching `changelog_*.md` inside this
folder. Keep the version in the filename, the heading, package metadata and
public documentation synchronized when preparing a release.
