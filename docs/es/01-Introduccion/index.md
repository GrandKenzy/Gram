# 01. Introducción

> **Versión Actual:** `2.1.0` (Estable)

Esta sección introduce el **Framework Gram**, explicando qué problemas resuelve, cómo se organiza su pipeline de ejecución, cómo instalarlo en proyectos de Python y qué incluye la versión estable actual.

---

## Contenido de la Sección

| Guía | Resumen |
| :--- | :--- |
| **[01. ¿Qué es Gram?](./01-que-es-gram.md)** | Explica el propósito de Gram como frontend sintáctico en Python puro, la separación estricta entre análisis sintáctico y semántico, y sus capacidades principales. |
| **[02. Instalación](./02-instalacion.md)** | Instrucciones detalladas para instalar Gram con **VNMA** (`vnma.toml` desde GitHub, tags de lanzamiento o rutas locales editables) o directamente mediante Git y `PYTHONPATH`. |
| **[03. Estado Beta Histórico](./03-estado-beta.md)** | Notas archivadas del ciclo Beta anterior a `2.1.0` y revisión histórica de madurez de componentes. |

---

## Resumen Rápido

1. **Qué es Gram:** Un framework de Python puro sin dependencias externas que convierte código fuente en un flujo de tokens (`TokenType`) mediante el `Lexer`, y evalúa gramáticas declarativas (`RuleItem`) mediante el `Parser` y `ASTAnalyzer` para emitir un Árbol de Sintaxis Abstracta estructurado y fuertemente tipado (`ASTNode` / `ASTRef`).
2. **Cómo se instala:** Gram puede usarse directamente desde un checkout de Git o mediante `PYTHONPATH`; las herramientas de vendor son opcionales para proyectos que ya dependan de ellas.
3. **Versión estable:** Gram `2.1.0` es la versión estable actual. Las páginas del ciclo Beta se conservan como historial, no como descripción del estado presente.
