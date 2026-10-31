# 01. Introducción

> **Versión Actual:** `3.0.0` (Estable)

Esta sección presenta el **Framework Gram**, explicando qué problemas resuelve, cómo está estructurado su flujo de trabajo, cómo instalarlo en sus proyectos de Python y qué incluye la versión estable actual.

---

## Estructura de la Sección

| Guía | Resumen |
| :--- | :--- |
| **[01. ¿Qué es Gram?](./01-que-es-gram.md)** | Explica el propósito de Gram como frontend sintáctico en Python puro, su desacoplamiento estricto del análisis semántico y sus capacidades centrales. |
| **[02. Instalación](./02-instalacion.md)** | Instrucciones paso a paso para instalar Gram mediante **VNMA** (`vnma.toml` desde GitHub, etiquetas de versión o rutas editables locales) o directamente vía Git. |
| **[03. Estado de la Versión y Estabilidad](./03-estado-beta.md)** | Revisión de madurez de componentes, suite de 300 pruebas automatizadas y contratos de estabilidad en `3.0.0`. |

---

## Resumen Rápido

1. **Qué es Gram:** Un framework sin dependencias externas que convierte texto fuente en un flujo de instancias `TokenType` (`Lexer`) y evalúa gramáticas declarativas `RuleItem` (`Parser` + `ASTAnalyzer`) para emitir un Árbol de Sintaxis Abstracta tipado (`ASTNode` / `ASTRef`), con soporte para compilación AOT a C11.
2. **Cómo se instala:** Gram puede utilizarse directamente desde un clon de Git o mediante `PYTHONPATH`; también se integra con herramientas de empaquetado opcionales si el proyecto anfitrión las requiere.
3. **Versión Estable:** Gram `3.0.0` es la versión estable para producción.
