# Gram Framework

<p align="center">
  <strong>Framework de Meta-Interpretación y Diseño de Lenguajes en Python 3.10+</strong><br>
  Parser por combinadores, análisis AST, sandbox de plugins, compilador GLANG y soporte de extensiones VS Code con Language Server Protocol (LSP).
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <img src="https://img.shields.io/badge/version-1.0.0-informational.svg" alt="Version 1.0.0">
  <a href="https://github.com/GrandKenzy/Gram/actions"><img src="https://img.shields.io/badge/tests-266%20passed-success.svg" alt="Tests: 266 passed"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Free%20Use%20%26%20Commercial%20Output-brightgreen.svg" alt="License"></a>
  <a href="https://github.com/GrandKenzy/Gram"><img src="https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg" alt="Zero External Dependencies"></a>
</p>

> **Nota sobre el estado del proyecto (Versión 1.0.0):**  
> Gram se encuentra en desarrollo activo y constante evolución. Esta es la versión **1.0.0**. Cualquier feedback, sugerencia de mejora o reporte de incidencias es profundamente bienvenido y agradecido para continuar enriqueciendo el framework.

---

## ¿Qué es Gram?

**Gram** es un framework en Python puro diseñado para crear lenguajes de programación, DSLs (*Domain-Specific Languages*) y formatos de datos estructurados de manera declarativa y fuertemente tipada.

A diferencia de los generadores de parsers monolíticos o dependientes de dependencias C complejas, Gram implementa un motor de **combinadores sintácticos con backtracking atómico**, construcción de árboles de sintaxis abstracta (**AST**), un **sistema de plugins con sandbox de seguridad**, un lenguaje declarativo propio (**GLANG**) y un generador de extensiones para editores (**VSIX**) con servidor de lenguaje (**LSP**) integrado.

---

## Arquitectura y Componentes Clave

```
                    ┌─────────────────────────┐
                    │    Código Fuente        │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │      Lexer Léxico       │  <-- Palabras clave, indentación, comentarios
                    └───────────┬─────────────┘
                                │ Tokens
                                ▼
                    ┌─────────────────────────┐
                    │   Parser & Combinators  │  <-- Seq, Alt, Many, Sep, Opt, MatchToken, etc.
                    └───────────┬─────────────┘      (Backtracking atómico con savepoint/restore)
                                │
                                ▼
                    ┌─────────────────────────┐
                    │       ASTAnalyzer       │  <-- Nodos tipados (ASTProgram, ASTNode)
                    └───────────┬─────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Plugins &    │         │ GLANG DSL    │         │ VSIX & LSP   │
│ Sandbox AST  │         │ Compilador   │         │ para VS Code │
└──────────────┘         └──────────────┘         └──────────────┘
```

1. **Motor Léxico (`gram.core.lexer`):** Tokenizador modular que gestiona palabras clave coloreadas (`words`), operadores, símbolos, literales, comentarios de una línea (`//` o `#`) y bloques de indentación/dedentación.
2. **Parser y Combinadores (`gram.core.parser` & `gram.core.combinators`):** Motor descendente recursivo basado en combinadores (`Seq`, `Alt`, `Many`, `Some`, `Sep`, `Enclosed`, `Opt`, `MatchToken`, `MatchKeyword`, `Ref`). Utiliza puntos de control inmutables (`savepoint` / `restore`) para revertir el estado del parser de forma atómica y sin efectos secundarios ante ramas que fallan.
3. **Árbol de Sintaxis Abstracta (`gram.core.ast`):** Construcción estructurada del AST con `ASTProgram` y `ASTNode`, con telemetría de análisis (`Watcher`) e impresión jerárquica legible.
4. **Sistema de Plugins con Sandbox (`gram.plugins`):**
   - Manifiesto estándar `manifest.json` para declarar capacidades (`load`, `process`, `cli`), permisos y dependencias.
   - Auditoría estática mediante AST (`gram check`) antes de la carga de código para detectar llamadas inseguras (`eval`, `exec`, accesos no autorizados a subprocesos).
   - Aislamiento de entorno virtual con comandos de gestión (`gram env`).
   - Tres plugins oficiales incluidos: `expressions` (operadores y precedencia), `storage` (memoria de tokens) y `GRAM_ESSENCIAL_PACK` (combinadores de control avanzado).
5. **DSL GLANG (`gram.glang`):** Lenguaje declarativo que permite escribir gramáticas en archivos de texto `.glang` (mediante palabras clave como `rule`, `token`, `keyword`, `seq`, `alt`, `many`) en lugar de diccionarios de Python manuales. Los plugins pueden extender GLANG mediante archivos `*.glang.py`, cargados de forma resiliente con aislamiento de errores.
6. **Integración con VS Code (`gram.vsix`):** Generador de extensiones para editores que produce gramáticas TextMate con paleta de colores, servidor en vivo con el protocolo Language Server Protocol (LSP), autocompletado, marcado de errores en tiempo real y asignación a un compilador destino mediante el ID canónico de Gram.
7. **Cero Dependencias Externas:** 100% implementado con la biblioteca estándar de Python (3.10+).


---

## Instalación

### Desde el repositorio:

```bash
git clone https://github.com/GrandKenzy/Gram.git
cd Gram
pip install -e .
```

### Verificación:

```bash
python -m gram --version
# o directamente con el comando de consola:
gram --version
```

---

## Inicio Rápido (API en Python)

El siguiente ejemplo muestra cómo definir una regla sintáctica, registrar palabras clave y construir un AST con Gram:

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

# 1. Registrar palabras clave y colores de sintaxis
words.add_keyword("let", hex_color="#569CD6")

# 2. Definir una regla sintáctica como subclase de RuleItem
class LetStatement(RuleItem):
    name = "LetStatement"
    grammar = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
    )

# 3. Vincular la gramática formal con PROGRAM y DECLARATION
grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(Ref(LetStatement)),
    LetStatement: LetStatement.grammar,
}

# 4. Tokenizar el código fuente
source_code = "let total = 100"
lexer = Lexer(source_code)
tokens = [t for t in lexer.process() if t.token != Token.EOF]

# 5. Analizar sintácticamente y construir el AST
parser = Parser(tokens)
analyzer = ASTAnalyzer(parser, grammar)
ast = analyzer.process()

# 6. Inspeccionar el árbol jerárquico
for node in ast.body:
    print(node.format())
    # Salida: └── [L0] LetStatement (code=0) -> values=['let', 'total', 100]
```

---

## Interfaz de Línea de Comandos (CLI)

Gram incluye una herramienta CLI completa accesible mediante `gram` o `python -m gram`:

```bash
# Validar un plugin con auditoría estática AST antes de instalarlo
gram check gram/plugins/source/expressions

# Instalar y listar plugins en el catálogo
gram install gram/plugins/source/expressions
gram list

# Administrar el entorno virtual aislado de Gram
gram env create
gram env list

# Compilar una gramática GLANG a Python
gram glang compile mi_gramatica.glang

# Generar la extensión VSIX para GLANG buscando extensiones de plugins (*.glang.py)
gram glang generate vsix

# Generar e instalar la extensión VSIX de GLANG en VS Code
gram glang --install vsix

# Desinstalar la extensión de GLANG de VS Code
gram glang --uninstall vsix

# Generar e instalar la extensión oficial VSIX de Gram para VS Code
gram vsix install
```

---

## Plugins Oficiales Incluidos

En `gram/plugins/source/` se encuentran tres plugins nativos sanitizados y verificados:

| Plugin | Descripción | Combinadores y Funcionalidades |
| :--- | :--- | :--- |
| **[`expressions`](gram/plugins/source/expressions/)** | Manejo de expresiones complejas con precedencia de operadores. | `ChainL` (asociatividad izquierda), `ChainR` (asociatividad derecha), `ExpressionBuilder` y evaluador aritmético/lógico. Extiende GLANG con `expressions.glang.py`. |
| **[`storage`](gram/plugins/source/storage/)** | Almacenamiento y recuperación contextual de tokens durante el parseo. | `Save` (guarda token en registro), `Load` (compara contra token guardado), `Tag` (etiqueta nodos AST). Extiende GLANG con `storage.glang.py`. |
| **[`GRAM_ESSENCIAL_PACK`](gram/plugins/source/GRAM_ESSENCIAL_PACK/)** | Combinadores avanzados de control de flujo sintáctico. | `SimpleCombinator` (creación fluida), `If` (parseo condicional), `ErrorCombinator`, `Req`, `Peek` y `Until`. Extiende GLANG con `essencial.glang.py`. |

---

## Proyectos de Ejemplo

Dentro de la carpeta [`examples/`](examples/) se incluyen implementaciones reales que demuestran el potencial del framework:

1. **[`CExample`](examples/CExample/):**
   Un analizador sintáctico para un subconjunto expresivo del lenguaje C implementado puramente con combinadores de Gram.
   - Reconoce tipos primitivos (`int`, `char`, `float`, etc.), punteros escalares (`int*`), prototipos, funciones recursivas, bucles `while`/`for`, directivas `#include` y construye la tabla de símbolos y el árbol AST completo.
   - Ejecución:
     ```bash
     python examples/CExample/main.py
     ```

2. **[`sjson`](examples/sjson/):**
   Compilador de **SJSON (Super JSON)** implementado sobre Gram.
   - Soporta variables numéricas y cadenas (`let` / `var`), cálculos aritméticos con precedencia, comentarios con `//` y herencia modular `{ extend: "ruta.json" }`, compilando determinísticamente a JSON estándar (RFC 8259).
   - Ejecución:
     ```bash
     python examples/sjson/main.py
     ```

---

## Documentación Técnica Completa

La documentación detallada se encuentra estructurada en la carpeta [`docs/`](docs/):

- **[Índice Maestro de Documentación](docs/index.md)**
- **01. Arquitectura del Compilador:**
  - **[Visión General de Arquitectura](docs/01-Arquitectura/index.md)**
  - **[Motor Léxico (Lexer)](docs/01-Arquitectura/lexer.md):** Tokenización, palabras clave y grupos léxicos.
  - **[Tokens y Tipos Léxicos](docs/01-Arquitectura/tokens.md):** Especificación de tokens y su representación interna.
  - **[Parser y Backtracking](docs/01-Arquitectura/parser.md):** Pipeline de análisis sintáctico con puntos de control atómicos.
  - **[Árbol de Sintaxis Abstracta (AST)](docs/01-Arquitectura/ast.md):** Nodos `ASTNode`, `ASTProgram` y telemetría de ejecución.
- **02. Sintaxis y Reglas:**
  - **[Definición de Sintaxis](docs/02-Sintaxis/index.md)**
  - **[Catálogo Completo de Combinadores](docs/02-Sintaxis/combinators.md):** Manual de todos los combinadores nativos y de plugins.
  - **[Especificación de RuleItem](docs/02-Sintaxis/rule_item.md):** Clase base declarativa de reglas, metaclase y extensiones para IDE.
- **03. Ecosistema y Herramientas:**
  - **[Visión del Ecosistema](docs/03-Ecosistema/index.md)**
  - **[Especificación del DSL GLANG](docs/03-Ecosistema/glang.md):** Guía de sintaxis y compilación declarativa de gramáticas.
  - **[Arquitectura y Seguridad de Plugins](docs/03-Ecosistema/plugins.md):** Especificación de manifiestos, auditoría estática AST y modelo de permisos.
  - **[Infraestructura VSIX y Servidor LSP](docs/03-Ecosistema/vsix.md):** Generación de temas TextMate, autocompletado y servidor LSP.
- **04. Referencia:**
  - **[Diagnósticos y Referencia](docs/04-Referencia/index.md)**
  - **[Catálogo Formal de Errores OSGDC](docs/04-Referencia/errors.md):** Estándar de 5 dimensiones para clasificación y trazabilidad de fallos.

---

## Suite de Pruebas Unitarias

Gram cuenta con una suite integral de 266 pruebas automatizadas que cubren el 100% de los subsistemas (Lexer, Parser, AST, Errores OSGDC, Plugins, GLANG, VSIX, SJSON y CExample):

```bash
python -m unittest discover -s gram/tests
```

```text
Ran 266 tests in 17.8s
OK
```

---

## 🤝 Colaboración y Contacto

¿Te interesa colaborar en el desarrollo de Gram, aportar ideas o proponer integraciones?
- Puedes ponerte en contacto directamente enviando un mensaje a:  
  📫 **[kencv3002003@gmail.com](mailto:kencv3002003@gmail.com)**
- Cualquier feedback, sugerencia o reporte de incidencias ayuda muchísimo al crecimiento del proyecto.

---

## ☕ Donaciones y Apoyo al Proyecto

Gram es un proyecto desarrollado con dedicación para ofrecer herramientas de compilación, parsing y meta-interpretación de lenguajes de alto rendimiento, modulares y con cero dependencias externas.

Cualquier donación es profundamente bienvenida y se agradecería y apoyaría mucho para continuar su mantenimiento y evolución:
- Donaciones vía PayPal / transferencia:  
  💖 **[kencv3002003@gmail.com](mailto:kencv3002003@gmail.com)**

¡Muchas gracias por apoyar el desarrollo de software libre y educativo!

---

## 📄 Licencia

Gram se distribuye bajo una **Licencia de Uso Gratuito y Explotación Comercial de Productos Derivados** (disponible en versión completa en español e inglés en el archivo [LICENSE](LICENSE)).

### Resumen de Términos / Terms Summary:

- **Uso Gratuito (Free of Charge):**  
  Gram puede ser utilizado de forma completamente libre y gratuita para cualquier propósito personal, educativo, académico o comercial.
- **Venta de Productos Derivados (Commercial Output Allowed):**  
  Cualquier persona u organización puede comercializar, vender, licenciar y monetizar los productos resultantes del uso de Gram (lenguajes, DSLs, compiladores, parsers, herramientas de análisis o programas generados). El producto de tu trabajo te pertenece al 100%.
- **Prohibición de Modificación Directa (Core Immutability):**  
  Gram Framework no puede ser modificado directamente en su código base central. Cualquier extensión, nuevo combinador, sintaxis o comportamiento debe realizarse exclusivamente a través del sistema oficial de **Plugins** (`gram.plugins` y archivos `*.glang.py`).
- **Prohibición de Venta del Framework (Non-commercial Framework Resale):**  
  Gram Framework no puede ser vendido, sublicenciado, revendido ni comercializado como paquete o librería propia de forma independiente.

Para el texto legal formal completo en ambos idiomas, consulta el archivo [LICENSE](LICENSE).
