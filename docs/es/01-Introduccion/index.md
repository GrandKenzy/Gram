# 01. Introducción

> **Versión Actual:** `2.0.0b2` (Beta)

Esta sección introduce el **Framework Gram**, explicando qué problemas resuelve, cómo se organiza su pipeline de ejecución, cómo instalarlo y aislarlo en proyectos de Python mediante VNMA o Git, y qué implica su estado actual en fase Beta.

---

## Contenido de la Sección

| Guía | Resumen |
| :--- | :--- |
| **[01. ¿Qué es Gram?](./01-que-es-gram.md)** | Explica el propósito de Gram como frontend sintáctico en Python puro, la separación estricta entre análisis sintáctico y semántico, y sus capacidades principales. |
| **[02. Instalación](./02-instalacion.md)** | Instrucciones detalladas para instalar Gram con **VNMA** (`vnma.toml` desde GitHub, tags de lanzamiento o rutas locales editables) o directamente mediante Git y `PYTHONPATH`. |
| **[03. Estado Beta](./03-estado-beta.md)** | Detalles del ciclo Beta de la versión `v2.0.0b2`, tabla de madurez de componentes y subsistemas experimentales. |

---

## Resumen Rápido

1. **Qué es Gram:** Un framework de Python puro sin dependencias externas que convierte código fuente en un flujo de tokens (`TokenType`) mediante el `Lexer`, y evalúa gramáticas declarativas (`RuleItem`) mediante el `Parser` y `ASTAnalyzer` para emitir un Árbol de Sintaxis Abstracta estructurado y fuertemente tipado (`ASTNode` / `ASTRef`).
2. **Cómo se instala:** Gram está diseñado para ser integrado directamente en proyectos mediante **[VNMA](https://github.com/GrandKenzy/vnma)** (utilizando ramas de Git, tags como `v2.0.0b2`, o enlaces editables en tiempo real) o importado desde un clon de Git mediante `PYTHONPATH`.
3. **Aviso de fase Beta:** Tanto Gram (`v2.0.0b2`) como sus herramientas para editores `gram.vsix` se encuentran en estado **Beta**. El núcleo de lexer, parser, checkpoints, sesiones y diagnósticos está cubierto por 179 pruebas automatizadas, mientras que `gram.vsix` y helpers de alto nivel continúan evolucionando.
