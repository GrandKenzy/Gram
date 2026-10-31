# Subsistema de Análisis Léxico (`gram.core.lexer`)

> **Subsistema:** `gram.core.lexer`  
> **Runtime:** Python 3.12+ puro (Cero dependencias externas en tiempo de ejecución)  
> **Estado:** Estable (Versión `3.0.0`)

El **Subsistema de Análisis Léxico** es el motor frontal de escaneo de Gram. Procesa código fuente a partir de cadenas de texto, secuencias de líneas o rutas de archivos en disco, transformando flujos de caracteres crudos en secuencias ordenadas de lexemas fuertemente tipados (`TokenType`), culminando siempre con un token terminal `Token.EOF`.

A diferencia de tokenizadores basados en expresiones regulares monolíticas o tablas de estados opacas, el lexer de Gram implementa una arquitectura modular de dos capas (`LexerState` y `Lexer`), una tubería de despacho especializada por visitors (`gram.core.lexer.visitors`), seguimiento semántico de espacios en blanco al estilo Python, resolución codiciosa de operadores por longitud máxima (*maximal munch* sobre `MAP_SYMBOLS`), e integración nativa con el sistema de telemetría y diagnósticos de Gram (`Diagnostics`).

---

## Diagrama de Arquitectura

```
Código Fuente (str | list[str] | Path)
                  │
                  ▼
          ┌───────────────┐
          │  LexerState   │ ◄─── gram.config / Session.config
          └───────┬───────┘
                  │ (cursor de línea, cursor de col, pila indents)
                  ▼
            ┌───────────┐
            │   Lexer   │ (bucle principal process())
            └─────┬─────┘
                  │
     ┌────────────┼────────────────────────┬──────────────────────┐
     ▼            ▼                        ▼                      ▼
Espacios y    Motor de Indentación    Delimitadores Multilínea    Despacho de Visitors
Saltos Línea   (INDENT / DEDENT)       (Strings y Comentarios)    (visitors.visit)
                                                                  │
                                   ┌──────────────┬───────────────┼──────────────┐
                                   ▼              ▼               ▼              ▼
                                Números        Cadenas         Símbolos        Palabras
                               (DECIMAL/      (Simples/Multi/ (MAP_SYMBOLS/   (BOOL/NULL/
                                NUMBER)        Escapes/Flags)  Maximal Munch)  KEYWORD/IDENT)
                                   │              │               │              │
                                   └──────────────┴───────┬───────┴──────────────┘
                                                          ▼
                                                  list[TokenType]
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                 ▼
                                  Parser(tokens)               TokenStream(tokens)
```

---

## Capacidades Principales

1. **Clasificación Determinista:** Toda palabra escaneada sigue un estricto orden jerárquico de 4 niveles: booleanos configurados (`Token.BOOL`), valor nulo configurado (`Token.NULL`), palabras clave registradas (`Token.KEYWORD`) e identificadores de usuario (`Token.IDENT`).
2. **Operadores por Longitud Máxima (*Maximal Munch*):** Los operadores nativos y símbolos personalizados de `MAP_SYMBOLS` se ordenan descendentemente por longitud, garantizando que operadores compuestos como `**=`, `->`, `:=` o `...` se reconozcan antes que caracteres individuales.
3. **Literales Numéricos Compatibles con C:** Soporta enteros decimales, números de punto flotante (`3.14`, `1.5e-4`, punto inicial `.5`), enteros binarios (`0b`), octales (`0o`) y hexadecimales enteros o flotantes (`0x1.2p3`). Los sufijos C (`u`, `l`, `f`) conservan su representación textual exacta para el análisis semántico posterior.
4. **Indentación Semántica por Pila:** Mantiene una pila de niveles de indentación con políticas de conteo por espacios (`spaces`), tabuladores (`tabs`) o cálculo mixto visual (`mixed`), emitiendo tokens `Token.INDENT` y `Token.DEDENT`, y reportando discordancias de nivel (*indentation mismatch*).
5. **Comentarios y Delimitadores Configurables:** Soporte para comentarios de una sola línea (`#`, `//`, `;`), comentarios de bloque C (`/* ... */`) y delimitadores multilínea arbitrarios (`add_multline`), permitiendo su descarte o almacenamiento opcional en `lexer.comments`.
6. **Aislamiento por Sesión:** Todos los catálogos de palabras clave (`Keyword`), grupos semánticos (`WordGroup`) y tablas de símbolos (`MAP_SYMBOLS`) pueden encapsularse dentro de instancias aisladas de `Session`.
7. **Telemetría y Diagnósticos de Cero Sobrecarga:** Hereda directamente de `Diagnostics`, gestionando árboles de nodos de ejecución y registros estructurados de errores cuando la telemetría está habilitada, o minimizando sobrecostes cuando se apaga.

---

## Índice de Capítulos

### [01. Arquitectura y Manejo de Estado](./01-arquitectura-y-estado.md)
Examen exhaustivo de `Lexer` y `LexerState`, carga de código fuente (`str`, `Sequence[str]`, `Path`), coordenadas del cursor, ciclo de vida de la pila de indentación, validación previa mediante `check_state()` y trazas de ejecución.

### [02. Catálogo de Tokens y Despacho de Símbolos](./02-tokens-y-simbolos.md)
Referencia completa de las 11 categorías formales de `Token`, la estructura de lexema `TokenType` y formateo de diagnósticos (`formatter`), tokens dinámicos `CustomToken`, banderas `TokenFlags` y el motor *maximal-munch* de `MAP_SYMBOLS` con `insert_symbol()` y `disabled_symbol()`.

### [03. Literales y Visitors Especializados](./03-literales-y-visitors.md)
Desglose técnico de la arquitectura de despacho `visitors/`: literales numéricos (prefijos de base, punto flotante, guiones bajos, sufijos C, distinción entre `Token.DECIMAL` y `Token.NUMBER`), cadenas y docstrings (secuencias de escape, Unicode `\uXXXX`, prefijos `L`, `u`, `U`, `u8`) y precedencia de palabras.

### [04. Indentación, Comentarios y Delimitadores](./04-indentacion-y-comentarios.md)
Guía detallada del motor de indentación semántica (pila `indents`, estilos de espaciado, expansión de tabuladores, detección de errores), variantes de comentarios unilínea, comentarios de bloque, preservación en `lexer.comments` y registro de delimitadores multilínea personalizados (`add_multline`).

### [05. Navegación del Flujo de Tokens (`TokenStream`)](./05-flujo-token-stream.md)
Manual de referencia de `TokenStream`: manipulación del cursor (`position`, `advance`, `rewind`, `reset`), inspección anticipada (`current`, `peek`), comprobación condicional (`check`, `match`), consumo estricto con error (`consume`), corte en rebanadas y filtrado de exclusión (`filter_tokens`).

### [06. Configuración y Diagnósticos](./06-configuracion-y-diagnosticos.md)
Matriz completa de ajustes de `config` que gobiernan el lexer, nodos jerárquicos de telemetría, gestión de fallos léxicos (`report_error`, `fail`, ganchos de error), catálogo de códigos OSGDC `LEXER_*` y aislamiento de léxicos por sesión.
