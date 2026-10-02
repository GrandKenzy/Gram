# Documentación Oficial de Gram Framework

Bienvenido al centro de documentación técnica de **Gram Framework** (v1.0.0). Esta documentación cubre la arquitectura modular, el pipeline de análisis sintáctico con backtracking atómico, el catálogo de combinadores, la definición declarativa de reglas con `RuleItem`, el desarrollo de plugins en entornos seguros, el lenguaje declarativo GLANG y la integración directa con Visual Studio Code vía extensiones VSIX y servidor LSP.

---

## Estructura de la Documentación

La documentación se organiza en cuatro áreas clave:

### 1. Arquitectura del Compilador
Comprende el ciclo de vida completo de transformación desde código fuente hasta árboles de sintaxis tipados.
* **[01 Arquitectura — General](01-Arquitectura/index.md):** Visión global del pipeline y principios arquitectónicos.
* **[Motor Léxico](01-Arquitectura/lexer.md):** Tokenizador modular, análisis de indentación sensible al contexto, grupos léxicos y palabras clave.
* **[Catálogo de Tokens](01-Arquitectura/tokens.md):** Tipado formal de `TokenType`, `Token` inmutable con metadatos y `CustomToken`.
* **[Parser y Backtracking](01-Arquitectura/parser.md):** Consumo determinista de tokens y máquina de estados con puntos de control transaccionales inmutables (`ParseControl`).
* **[Árbol de Sintaxis Abstracta (AST)](01-Arquitectura/ast.md):** Estructura jerárquica de nodos `ASTNode`, agregación en `ASTProgram` y telemetría vía `Watcher`.

### 2. Sintaxis y Definición de Reglas
Bloques constructivos y modelado formal de gramáticas y lenguajes.
* **[02 Sintaxis — General](02-Sintaxis/index.md):** Paradigma declarativo de definición sintáctica.
* **[Catálogo de Combinadores](02-Sintaxis/combinators.md):** Referencia exhaustiva de combinadores nativos (`Seq`, `Alt`, `Opt`, `Many`, `Some`, etc.) y de plugins (`Save`, `Load`, `Tag`, `ChainL`, `If`, etc.).
* **[Especificación de RuleItem](02-Sintaxis/rule_item.md):** Documentación formal de `RuleItem`, metaclase `RuleMeta`, metadatos TextMate, snippets LSP y comportamiento AST.

### 3. Ecosistema y Herramientas
Módulos para ampliar, distribuir y dotar de soporte de editor a los lenguajes creados.
* **[03 Ecosistema — General](03-Ecosistema/index.md):** Visión integral del ecosistema y herramientas de desarrollo.
* **[DSL GLANG](03-Ecosistema/glang.md):** Lenguaje declarativo para definir gramáticas en archivos `.glang` sin necesidad de código Python manual.
* **[Sistema de Plugins](03-Ecosistema/plugins.md):** Arquitectura de extensiones, manifiestos `manifest.json`, auditoría estática AST (`gram check`) y sandbox de permisos.
* **[VSIX y LSP para VS Code](03-Ecosistema/vsix.md):** Infraestructura de empaquetado de extensiones `.vsix`, temas TextMate y servidor Language Server Protocol en tiempo real.

### 4. Referencia y Diagnóstico
Especificaciones técnicas y catálogos de códigos centralizados.
* **[04 Referencia — General](04-Referencia/index.md):** Estándar de telemetría y diagnósticos.
* **[Catálogo Formal de Errores OSGDC](04-Referencia/errors.md):** Matriz estandarizada de 5 dimensiones (`[O]rigen`, `[S]ubsistema`, `[G]ravedad`, `[D]ocumentación`, `[C]ondición`).

---

## Proyectos de Ejemplo

Gram incluye proyectos de demostración completos en la carpeta `examples/`:
* **CExample:** Motor mínimo de parsing de un subconjunto de lenguaje C (funciones, tipos, variables, control de flujo y AST).
* **sjson (Super JSON):** Formato enriquecido derivado de JSON con soporte para variables, operaciones aritméticas, comentarios `//` y directivas de herencia `extend`.

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
