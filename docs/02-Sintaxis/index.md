# Sintaxis y Definición de Reglas

En **Gram Framework**, la sintaxis de un lenguaje o formato no se define mediante tablas monolíticas de transiciones (como en generadores estilo Yacc o Bison), sino a través de una arquitectura declarativa compuesta por **Combinadores Sintácticos** de alto nivel y la clase base declarativa **`RuleItem`**.

---

## Modelo de Producción Gramatical

El análisis sintáctico de Gram opera combinando pequeñas funciones y objetos atómicos que modelan reglas gramaticales complejas:

```
┌────────────────────────────────────────────────────────┐
│                        RuleItem                        │
│  - code, name, description, grammar                    │
│  - TextMate colors, LSP snippets & suggestions         │
└──────────────────────────┬─────────────────────────────┘
                           │ implementa
                           ▼
┌────────────────────────────────────────────────────────┐
│               Combinadores Sintácticos                 │
│  Nativos: Seq, Alt, Opt, Many, Some, Sep, Enclosed...  │
│  Plugins: Save, Load, Tag, ChainL, ChainR, If...       │
└────────────────────────────────────────────────────────┘
```

---

## Módulos de esta Sección

| Módulo | Documento | Descripción |
| :--- | :--- | :--- |
| **Catálogo de Combinadores** | [combinators.md](combinators.md) | Manual de referencia con todos los combinadores sintácticos: primitivas nativas (`Seq`, `Alt`, `Opt`, `Many`, `Some`, `MatchToken`, etc.) y combinadores provistos por plugins oficiales (`Save`, `Load`, `Tag`, `ChainL`, `ChainR`, `ExpressionBuilder`, `SimpleCombinator`, `If`, `ErrorCombinator`, `Req`, `Peek`, `Not`, `Until`). |
| **Especificación de RuleItem** | [rule_item.md](rule_item.md) | Especificación formal de la clase base declarativa `RuleItem`, metaclase `RuleMeta`, propiedades (`code`, `name`, `description`, `docs`, `grammar`, `colors`, `suggestions`), comportamiento AST y vinculación con VSIX/LSP. |

---

## Características de la Sintaxis en Gram

1. **Declarativa y Expresiva:** Las reglas gramaticales se construyen combinando operadores lógicos intuitivos (`Seq` para secuencias, `Alt` para opciones, `Opt` para elementos opcionales).
2. **Preparada para IDEs:** Cada regla no solo procesa texto en tiempo de ejecución, sino que declara sus colores de sintaxis (TextMate), documentación contextual flotante (Hover) y fragmentos de autocompletado (Snippets) directamente en su definición.
3. **Resiliencia y Extensibilidad:** Nuevos combinadores se pueden añadir sin alterar el parser central a través del sistema de plugins.
