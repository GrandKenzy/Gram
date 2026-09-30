# Gram Framework

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-258%20passed-success.svg)](https://github.com/GrandKenzy/Gram)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Dependencies](https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg)](https://github.com/GrandKenzy/Gram)

**Gram** es un framework moderno, modular y fuertemente tipado para el diseño de Lenguajes de Dominio Específico (DSLs), análisis léxico y sintáctico con combinadores, construcción de Árboles de Sintaxis Abstracta (AST), plugins con auditoría de seguridad y generación de extensiones para editores con soporte de Language Server Protocol (LSP).

---

## Características Principales

- **Motor de Combinadores Declarativos:**
  Primitivas sintácticas (`Seq`, `Alt`, `Many`, `Some`, `Opt`, `Sep`, `Delim`, `Repeat`, `Not`, `MatchToken`, `MatchKeyword`, `Ref`) y combinadores de plugins (`ChainL`, `ChainR`, `ExpressionBuilder`, `Save`, `Load`, `Tag`, `If`, `Error`, `Req`, `Peek`, `Until`).

- **Parser con Backtracking Atómico e Inmutable:**
  Manejo determinista del estado mediante `savepoint` y `restore`, eliminando efectos secundarios y permitiendo backtracking seguro ante ramas sintácticas alternativas.

- **Árbol de Sintaxis Abstracta (AST) y Telemetría:**
  Nodos `ASTNode` y `ASTProgram` estructurados jerárquicamente, con soporte de análisis semántico, extracción de símbolos y visualización en árbol legible.

- **Sistema de Plugins con Auditoría de Seguridad:**
  - Arquitectura modular basada en `PluginBase` y `manifest.json`.
  - Auditoría estática mediante análisis AST (`gram check`) para detectar llamadas peligrosas (`eval`, `exec`, subprocesos no autorizados).
  - Entorno de ejecución con permisos de usuario aprobados explícitamente y soporte de entorno virtual dedicado (`gram env`).
  - Tres plugins oficiales incluidos: `expressions`, `storage` y `GRAM_ESSENCIAL_PACK`.

- **GLANG (Gram Language DSL):**
  Lenguaje declarativo para definir gramáticas en archivos `.glang` sin necesidad de escribir diccionarios de Python.

- **Generador de Extensiones VS Code (VSIX) y Servidor LSP:**
  Generación automática de esquemas TextMate, autocompletado en tiempo real, servidor Language Server Protocol (LSP), marcado de errores en vivo, compilador objetivo e ID canónico universal de Gram para instalación/desinstalación sin redundancias.

- **Cero Dependencias Externas:**
  Todo el núcleo, motor léxico, combinadores, plugins oficiales, GLANG y servidor LSP funcionan exclusivamente con la biblioteca estándar de Python (3.10+).

---

## Instalación Rápida

Instalación en modo desarrollo:

```bash
git clone https://github.com/GrandKenzy/Gram.git
cd Gram
pip install -e .
```

O verificar directamente con Python:

```bash
python -m gram --version
```

---

## Inicio Rápido (Python API)

```python
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators import (
    DECLARATION,
    PROGRAM,
    Alt,
    Many,
    MatchKeyword,
    MatchToken,
    Ref,
    RuleItem,
    Seq,
)
from gram.core.lexer import Lexer, Token, words
from gram.core.parser import Parser

# 1. Registrar palabras clave personalizadas
words.add_keyword("let", hex_color="#569CD6")

# 2. Definir una regla sintáctica como RuleItem
class LetStatement(RuleItem):
    name = "LetStatement"
    grammar = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
    )

# 3. Definir la gramática formal con PROGRAM y DECLARATION
grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(Ref(LetStatement)),
    LetStatement: LetStatement.grammar,
}

# 4. Tokenizar código fuente
lexer = Lexer("let x = 42")
tokens = [t for t in lexer.process() if t.token != Token.EOF]

# 5. Analizar y construir el AST
parser = Parser(tokens)
analyzer = ASTAnalyzer(parser, grammar)
ast = analyzer.process()

# 6. Inspeccionar el árbol generado
for node in ast.body:
    print(node.format())
    # Salida: └── [L0] LetStatement (code=0) -> values=['let', 'x', 42]
```

---

## Interfaz de Línea de Comandos (CLI)

Gram proporciona una CLI completa accesible mediante `gram` o `python -m gram`:

```bash
# Validar un plugin antes de instalarlo (auditoría estática AST)
gram check gram/plugins/source/expressions

# Instalar y listar plugins del catálogo
gram install gram/plugins/source/expressions
gram list

# Compilar un archivo de gramática GLANG (.glang)
gram glang compile mi_lenguaje.glang

# Generar e instalar la extensión VSIX para VS Code
gram vsix install
```

---

## Proyectos de Ejemplo Incluidos

En el directorio [`examples/`](examples/) encontrarás implementaciones completas de producción:

1. **[`CExample`](examples/CExample/README.md):**
   Motor mínimo de análisis sintáctico de C que reconoce variables, punteros, prototipos, funciones recursivas, bucles `while`/`for`, expresiones aritméticas y directivas `#include`.
   ```bash
   python examples/CExample/main.py
   ```

2. **[`cjson`](examples/cjson/README.md):**
   Compilador de C-Style JSON / SJSON que añade variables tipadas (números y strings), cálculos con precedencia de operadores, comentarios `//` y herencia modular `{ extend: "ruta" }` compilando a JSON estándar.
   ```bash
   python examples/cjson/main.py
   ```

---

## Centro de Documentación Técnica

La documentación detallada se encuentra en [`docs/`](docs/):

- **[Índice Maestro de Documentación](docs/README.md)**
- **[Catálogo Completo de Combinadores](docs/combinators.md)**
- **[Arquitectura y Seguridad de Plugins](docs/plugins.md)**
- **[Especificación del DSL GLANG](docs/glang.md)**
- **[Infraestructura VSIX y Servidor LSP para VS Code](docs/vsix.md)**
- **[Árbol de Sintaxis Abstracta (AST)](docs/ast.md)**
- **[Motor Léxico (Lexer)](docs/lexer.md)**
- **[Parser y Backtracking Atómico](docs/parser.md)**
- **[Catálogo Formal de Errores OSGDC](docs/errors.md)**
- **[Tokens y Tipos Léxicos](docs/tokens.md)**

---

## Suite de Pruebas Unitarias

Gram incluye una suite exhaustiva de 258 pruebas unitarias automatizadas con cobertura total de los subsistemas:

```bash
python -m unittest discover -s gram/tests
```

```text
Ran 258 tests in 17.8s
OK
```

---

## Licencia

Distribuido bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
