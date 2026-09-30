# Documentación Oficial de Gram Framework

Bienvenido al centro de documentación técnica de **Gram Framework** (v1.0.0). Esta documentación cubre la arquitectura, subsistemas, catálogo de combinadores, desarrollo de plugins, la DSL GLANG y la integración con Visual Studio Code vía VSIX/LSP.

---

## Índice General de Documentación

| Documento | Descripción |
| :--- | :--- |
| **[Catálogo de Combinadores](combinators.md)** | Referencia exhaustiva de todos los combinadores sintácticos: nativos (`Seq`, `Alt`, `Opt`, `Many`, `Some`, `MatchToken`, etc.) y de plugins (`Save`, `Load`, `Tag`, `ChainL`, `ChainR`, `ExpressionBuilder`, `SimpleCombinator`, `If`, `ErrorCombinator`, `Req`, `Peek`, `Not`, `Until`). |
| **[Sistema de Plugins](plugins.md)** | Arquitectura de extensiones, especificación de `manifest.json`, subclases de `PluginBase`, auditoría estática AST (`gram check`), sandbox/permisos de usuario y guías completas de los 3 plugins oficiales (`storage`, `expressions`, `GRAM_ESSENCIAL_PACK`). |
| **[GLANG (Gram Language)](glang.md)** | Lenguaje de Dominio Específico (DSL) declarativo para definir gramáticas en archivos `.glang` sin necesidad de escribir diccionarios de Python, con compilación automática y comandos CLI. |
| **[VSIX y LSP para VS Code](vsix.md)** | Infraestructura de generación y empaquetado de extensiones para Visual Studio Code (`.vsix`): esquemas de color TextMate, autocompletado, servidor Language Server Protocol (LSP) en vivo, marcado de errores y compilador objetivo con ID universal de Gram. |
| **[Árbol de Sintaxis Abstracta (AST)](ast.md)** | Estructura de nodos `ASTNode`, `ASTProgram`, `ASTAnalyzer`, sistema de telemetría y `Watcher`. |
| **[Motor Léxico (Lexer)](lexer.md)** | Tokenización de código fuente, gestión de palabras clave (`words`), grupos léxicos (`WordGroup`) y manejo de indentación. |
| **[Parser y Backtracking](parser.md)** | Pipeline de análisis sintáctico con `savepoint` y `restore` inmutables como única fuente de verdad. |
| **[Catálogo Formal de Errores](errors.md)** | Estándar de 5 dimensiones OSGDC (`[O]rigen`, `[S]ubsistema`, `[G]ravedad`, `[D]ocumentación`, `[C]ondición`) y códigos de error centralizados. |
| **[Tokens](tokens.md)** | Definición de enumeraciones `Token`, instancias `TokenType` y tokens personalizados. |
| **[Proyectos de Ejemplo](../examples/)** | Motores de demostración en producción: **CExample** (motor mínimo de parsing de C: funciones, variables, control de flujo y AST) y **cjson** (C-Style JSON con comentarios `//`, cálculos, variables y herencia `extend`). |

---

## Inicio Rápido con Gram CLI

Gram provee una interfaz unificada de línea de comandos (`gram.cli`):

```bash
# Validar un plugin antes de instalarlo
python -m gram.cli check gram/plugins/source/expressions

# Instalar y listar plugins en el catálogo
python -m gram.cli install gram/plugins/source/expressions
python -m gram.cli list

# Compilar una gramática GLANG (.glang)
python -m gram.cli glang compile mi_lenguaje.glang

# Generar e instalar la extensión de VS Code
python -m gram.cli vsix install
```
