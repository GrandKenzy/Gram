# Arquitectura del Sistema Gram

El núcleo del **Framework Gram** está diseñado como un compilador modular, desacoplado y de alto rendimiento en Python puro (3.10+), sin dependencias externas. 

La arquitectura sigue una separación estricta de responsabilidades a través de fases de análisis deterministas: desde la ingestión léxica de código fuente hasta la generación de árboles de sintaxis abstracta (AST) listos para interpretación, transformación de código o análisis semántico.

---

## Flujo del Pipeline de Compilación

```
                     ┌─────────────────────────┐
                     │    Código Fuente        │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │      Motor Léxico       │  <-- lexer.md & tokens.md
                     └───────────┬─────────────┘      (Indentación, palabras clave, comentarios)
                                 │ Flujo de Tokens
                                 ▼
                     ┌─────────────────────────┐
                     │   Parser & Combinators  │  <-- parser.md
                     └───────────┬─────────────┘      (Backtracking atómico con savepoint/restore)
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │       ASTAnalyzer       │  <-- ast.md
                     └───────────┬─────────────┘      (Nodos tipados ASTProgram y ASTNode)
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
 │   Plugins    │         │  GLANG DSL   │         │  VSIX / LSP  │
 │  & Sandbox   │         │  Compilador  │         │ para VS Code │
 └──────────────┘         └──────────────┘         └──────────────┘
```

---

## Módulos de esta Sección

Esta sección detalla los cuatro pilares fundamentales del pipeline interno:

| Módulo | Documento | Responsabilidad Principal |
| :--- | :--- | :--- |
| **Motor Léxico** | [lexer.md](lexer.md) | Análisis de caracteres fuente, división en lexemas, indentación sensible al contexto (*off-side rule*), docstrings y maximal munch. |
| **Tokens y Tipos** | [tokens.md](tokens.md) | Catálogo formally tipado de `TokenType`, `Token` inmutable con metadatos de línea/columna y tokens personalizados (`CustomToken`). |
| **Parser y Backtracking** | [parser.md](parser.md) | Coordinación entre el consumo de tokens (`Parser`) y la máquina de estados con puntos de control transaccionales inmutables (`ParseControl`). |
| **Árbol de Sintaxis (AST)** | [ast.md](ast.md) | Estructuración jerárquica de nodos `ASTNode`, agregación del programa completo (`ASTProgram`) y telemetría de análisis vía `Watcher`. |

---

## Principios de Diseño Arquitectónico

1. **Cero Dependencias Externas:** El 100% de la arquitectura opera sobre la biblioteca estándar de Python (`collections`, `re`, `typing`, `enum`, `dataclasses`).
2. **Backtracking Atómico:** Cada intento fallido de parsing en combinadores alternativos revierte el cursor y estado del sistema a través de instantáneas inmutables (`savepoint` / `restore`), evitando fugas de estado o mutaciones intermedias.
3. **Tipado Estricto (Type-Safe):** Todos los componentes utilizan anotaciones de tipos completas compatibles con `mypy` y herramientas de análisis estático en modo estricto.
4. **Desacoplamiento Léxico-Sintáctico:** El parser no analiza texto en crudo, sino que consume un flujo de tokens homogéneo provisto por el Lexer, garantizando independencia entre formato físico y estructura lógica.
