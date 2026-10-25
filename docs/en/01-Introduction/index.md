# 01. Introduction

> **Current Version:** `2.0.0b2` (Beta)

This section introduces the **Gram Framework**, explaining what problems it solves, how its pipeline is structured, how to install and vendor it into your Python projects, and what its current Beta status entails.

---

## Section Overview

| Guide | Summary |
| :--- | :--- |
| **[01. What is Gram?](./01-what-is-gram.md)** | Explains Gram's purpose as a pure-Python syntactic frontend, its strict decoupling from semantic analysis, and its core capabilities. |
| **[02. Installation](./02-installation.md)** | Step-by-step instructions for installing Gram with **VNMA** (`vnma.toml` from GitHub, release tags, or local editable paths) or directly via Git. |
| **[03. Beta Status](./03-beta-status.md)** | Details the `v2.0.0b2` Beta lifecycle, component stability breakdown, and known experimental areas. |

---

## Quick Summary

1. **What Gram Is:** A zero-dependency Python framework that converts raw source text into a stream of `TokenType` instances (`Lexer`) and evaluates declarative `RuleItem` grammars (`Parser` + `ASTAnalyzer`) to emit a typed Abstract Syntax Tree (`ASTNode` / `ASTRef`).
2. **How It Is Installed:** Gram is designed to be vendored into host projects using **[VNMA](https://github.com/GrandKenzy/vnma)** (via Git branches, release tags such as `v2.0.0b2`, or live editable links) or imported directly from a Git clone via `PYTHONPATH`.
3. **Beta Notice:** Both Gram (`v2.0.0b2`) and its integrated `gram.vsix` editor tooling are currently in **Beta**. Core lexing, parsing, checkpointing, sessions, and diagnostics are covered by 179 automated regression tests, while `gram.vsix` and high-level CLI helpers continue to evolve.
