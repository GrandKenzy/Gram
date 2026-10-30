# 01. Introduction

> **Current Version:** `2.1.0` (Stable)

This section introduces the **Gram Framework**, explaining what problems it solves, how its pipeline is structured, how to install it into your Python projects, and what is included in the current stable release.

---

## Section Overview

| Guide | Summary |
| :--- | :--- |
| **[01. What is Gram?](./01-what-is-gram.md)** | Explains Gram's purpose as a pure-Python syntactic frontend, its strict decoupling from semantic analysis, and its core capabilities. |
| **[02. Installation](./02-installation.md)** | Step-by-step instructions for installing Gram with **VNMA** (`vnma.toml` from GitHub, release tags, or local editable paths) or directly via Git. |
| **[03. Historical Beta Status](./03-beta-status.md)** | Archived notes from the pre-`2.1.0` Beta lifecycle and component maturity review. |

---

## Quick Summary

1. **What Gram Is:** A zero-dependency Python framework that converts raw source text into a stream of `TokenType` instances (`Lexer`) and evaluates declarative `RuleItem` grammars (`Parser` + `ASTAnalyzer`) to emit a typed Abstract Syntax Tree (`ASTNode` / `ASTRef`).
2. **How It Is Installed:** Gram can be used directly from a Git checkout or through `PYTHONPATH`; optional vendor tooling may be used by host projects that already depend on it.
3. **Stable Release:** Gram `2.1.0` is the current stable release. The historical Beta pages remain available for release archaeology, not as the current project status.
