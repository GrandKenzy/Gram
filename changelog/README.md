# Gram · Changelog

<p align="center">
  <strong>Versioned release notes for the Gram framework</strong><br>
  Lexer, parser combinators, sessions, diagnostics, and language tooling.
</p>

---

## Current release

### [`2.0.0b2`](changelog_2.0.0b2.md) · Beta 2

The current beta focuses on configurable lexical behavior, C-style
preprocessing, parser-local conversions, multiline delimiters, and isolated
state for multi-language sessions.

> [!IMPORTANT]
> Gram is still in beta. Minor API and behavioral changes may occur before the
> stable `2.0.0` release.

## Release timeline

| Version | Date | Main focus | Notes |
| --- | --- | --- | --- |
| [`2.0.0b2`](changelog_2.0.0b2.md) | 2026-10-25 | Configurable lexer and preprocessing | Current |
| [`2.0.0b1`](changelog_2.0.0b1.md) | 2026-10-23 | Diagnostics, sessions, and checkpoints | Beta 1 |
| [`2.0.0b0`](changelog_2.0.0b0.md) | — | Parser foundations and tooling | Initial beta |

## How to read these notes

Each release has its own `changelog_*.md` file. Entries are grouped by
impact:

- **Breaking changes:** behavior or API changes that may require migration.
- **Added:** new public capabilities and configuration.
- **Changed:** modifications to existing behavior.
- **Fixed:** corrected bugs and regressions.
- **Documentation:** synchronized guides, examples, and release references.

## Repository conventions

Central detects release notes from files matching `changelog_*.md` inside this
folder. Keep the version in the filename, the heading, `vnma_config.toml`, and
the package metadata synchronized when preparing a release.
