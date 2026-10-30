# Documentación del Framework Gram

> **Versión:** `2.1.0` (Estable)
> **Entorno:** Python puro 3.12+ (Cero dependencias externas en runtime)

Bienvenido a la documentación oficial en español de **Gram**, un framework puro de Python para análisis léxico, combinadores de análisis sintáctico y generación de Árboles de Sintaxis Abstracta (`AST`), concebido para diseñar lenguajes de dominio específico (DSLs), transpiladores, procesadores de contratos y frontends de compiladores.

---

## Índice de Documentación

### [01. Introducción](./01-Introduccion/index.md)
Visión general del framework, objetivos de diseño, instrucciones de instalación y estado de la versión estable actual.
- **[01. ¿Qué es Gram?](./01-Introduccion/01-que-es-gram.md)** — Arquitectura central, separación estricta entre fases sintácticas y semánticas, y objetivos de diseño.
- **[02. Instalación](./01-Introduccion/02-instalacion.md)** — Cómo instalar y gestionar Gram mediante **VNMA** (`vnma.toml`, ramas de Git, tags y enlaces editables) o directamente mediante Git y `PYTHONPATH`.
- **[03. Estado Beta Histórico](./01-Introduccion/03-estado-beta.md)** — Matriz archivada del ciclo Beta anterior a `2.1.0`.

### [02. Combinadores](./02-Combinadores/index.md)
Guía de referencia para los combinadores sintácticos disponibles en `gram.core.combinators`, contratos de ejecución y motores de expresiones Pratt.
- **[01. Combinadores de Coincidencia](./02-Combinadores/01-matching.md)** — `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol` y `generador_expr`.
- **[02. Combinadores Estructurales](./02-Combinadores/02-estructurales.md)** — `Seq` (`+`), `Alt` (`|`), `Opt` y `Enclosed`.
- **[03. Combinadores de Repetición](./02-Combinadores/03-repeticion.md)** — `Many`, `Some`, `Until`, `UntilIndent` y `Separator`.
- **[04. Reglas y Almacenamiento](./02-Combinadores/04-reglas-y-almacenamiento.md)** — `RuleItem`, `Ref`, `Item`, `Literal`, `Save` y `Load`.
- **[05. Lookahead y Control](./02-Combinadores/05-lookahead-y-control.md)** — `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize` y `ErrorCombinator`.
- **[06. Validación Fluida](./02-Combinadores/06-validacion-fluida.md)** — Validación encadenada y transformaciones en el token mediante `Req`.
- **[08. Preprocesamiento y Expectativas](./02-Combinadores/08-preprocesamiento-y-expectativas.md)** — `Preprocess`, `Convert` y `Expected` para validaciones, conversiones lógicas y aserciones estrictas.
- **[07. Expresiones Pratt](./02-Combinadores/07-expresiones.md)** — `ArithmeticExpr`, `ConditionalExpr`, `DualExpr`, `bind_left` y `bind_right`.

### [03. Guía de Uso](./03-Uso/index.md)
Guías prácticas para estructurar frontends de lenguajes, gestionar sesiones aisladas, telemetría y diagnósticos, y tooling para editores.
- **[01. Configuración de Keywords y Léxico](./03-Uso/01-keywords-y-lexico.md)** — Registro de palabras clave (`words.add_keyword`), grupos semánticos (`words.add_group`), símbolos de operadores y banderas del lexer.
- **[02. RuleItem y `nodeable`](./03-Uso/02-ruleitem-y-nodeable.md)** — Definición de reglas gramaticales con `RuleItem`, gestión de códigos (`AutoCode`, `SetCode`), validación de entrypoints y explicación profunda de cómo `nodeable` controla el empaquetado `ASTRef` vs. inlining.
- **[03. Sesiones de Lenguaje](./03-Uso/03-sesiones.md)** — Aislamiento y alternancia entre múltiples frontends en el mismo proceso con `gram.sessions.Session`.
- **[04. Sistema de Diagnósticos y Errores](./03-Uso/04-diagnosticos-y-errores.md)** — Telemetría jerárquica con `Diagnostics`, catálogo formal OSGDC, `StackError` e interceptores de error (`ErrorAction`).
- **[05. VSIX y Tooling para Editores](./03-Uso/05-vsix-y-herramientas-editor.md)** — Mapas declarativos en `RuleItem`, previsualización ANSI TrueColor, generación de extensiones VS Code y servidor LSP por stdio.
