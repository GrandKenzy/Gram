# 03. Guía de Uso

Esta sección proporciona una guía práctica de extremo a extremo para construir, aislar, diagnosticar y crear herramientas de editor para un frontend de lenguaje con **Gram**.

Mientras que **[02. Combinadores](../02-Combinadores/index.md)** sirve como catálogo de las primitivas de análisis sintáctico individuales, **03. Uso** explica cómo los componentes del framework circundante—registros léxicos, declaraciones de `RuleItem`, modelado de AST con `nodeable`, aislamiento con `Session`, telemetría con `Diagnostics` y herramientas de editor `gram.vsix`—trabajan juntos en un compilador o DSL real.

---

## Vista General de la Sección

| Guía | Temas Tratados |
| :--- | :--- |
| **[01. Keywords y Configuración Léxica](./01-keywords-y-lexico.md)** | Inicialización de entradas `Keyword` (`words.add_keyword`), agrupación semántica en `WordGroup` (`words.add_group`), personalización de símbolos y operadores (`tokens.insert_symbol`, `tokens.disabled_symbol`), delimitadores multilínea, flags de strings y configuración del `Lexer` mediante `gram.config`. |
| **[02. RuleItem y `nodeable`](./02-ruleitem-y-nodeable.md)** | Creación de reglas de producción con `RuleItem`, gestión automática de IDs (`AutoCode`, `SetCode`), validación del punto de entrada raíz (`Alt(Ref(...))`) y cómo `nodeable = True` vs. `nodeable = False` controla el empaquetado en `ASTRef` o la inserción plana (*inlining*) de nodos secundarios. |
| **[03. Sesiones de Lenguaje](./03-sesiones.md)** | Aislamiento y conmutación entre múltiples frontends de lenguaje en el mismo proceso usando `gram.sessions.Session` (`clear_global`, `init`, `migrate`, `load`, `tokenize`, `parse`). |
| **[04. Diagnósticos y Sistema de Errores](./04-diagnosticos-y-errores.md)** | Uso de `gram.utilities.Diagnostics` para telemetría jerárquica del compilador (`node`, `down`, `debug`, `warn`, `error`, `StackInfo`), emisión de errores OSGDC (`gram.errors`, `StackError`) e intercepción de fallos con `Diagnostics.hook_errors` y `ErrorAction`. |
| **[05. VSIX y Herramientas de Editor (Beta)](./05-vsix-y-herramientas-editor.md)** | Asociación de `colors`, `autocomplete`, `suggestions`, `hints` y `playhints` a clases `RuleItem`, uso de selectores de anclaje `TokenSelector` (`@TOKEN:±offset`), renderizado de previsualizaciones ANSI TrueColor de 24 bits y generación/empaquetado de extensiones `.vsix` y servidores LSP. |

---

## Flujo de Trabajo Típico de un Frontend

```text
1. Configurar Léxico y Flags           ->  config.*, words.add_group(), words.add_keyword()
2. Declarar Reglas de Gramática        ->  class MyRule(combinators.RuleItem): entrypoint = ...
3. Aislar en una Sesión (Opcional)     ->  session.clear_global() -> session.init() -> ... -> session.migrate()
4. Tokenizar y Parsear Código Fuente   ->  Lexer(src).process() -> Parser(tokens).parse(ENTRYPOINT)
5. Inspeccionar AST, Trazas y Logs     ->  Árbol ASTRef / ASTNode, Diagnostics / StackInfo / StackError
6. Exportar Herramientas Editor (Beta) ->  VSIXAnalyzer -> VSIXGenerator -> vsix.up()
```
