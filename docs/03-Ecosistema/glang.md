# Guía y Referencia de GLANG (Gram Language)

GLANG es un Lenguaje de Dominio Específico (DSL) declarativo integrado en Gram que permite definir gramáticas sintácticas de forma visual, concisa y legible, eliminando la necesidad de escribir extensos diccionarios de combinadores en código Python.

---

## 1. ¿Por Qué Usar GLANG?

Tradicionalmente, en Gram una gramática se define mediante diccionarios de Python:

```python
# Modo tradicional (Python):
grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(Ref(LET_STMT), Ref(EXPR_STMT)),
    LET_STMT: Seq(MatchKeyword("let"), MatchToken(Token.IDENT), MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER)),
}
```

Con **GLANG**, la misma gramática se expresa de forma natural y estructurada en archivos `.glang`:

```glang
# Modo GLANG (.glang):
LET_STMT Seq:
    words "let"
    tokens.IDENT
    tokens.ASSIGN
    tokens.NUMBER

DECLARATION Alt:
    reference LET_STMT
    reference EXPR_STMT
```

### Ventajas de GLANG:
1. **Legibilidad Inmediata:** Estructura basada en bloques e indentación limpia.
2. **Cero Boilerplate:** No requiere instanciar clases de combinadores manualmente ni gestionar referencias diferidas en diccionarios.
3. **Integración Automática con VS Code:** Al compilar un archivo `.glang`, Gram registra la sintaxis en el subsistema `gram.vsix`, generando resaltado de colores y autocompletado de inmediato.
4. **Composición Modular:** Permite importar plugins oficiales (`include "expressions"`, `include "storage"`) y reutilizar sus reglas.

---

## 2. Sintaxis y Estructura de GLANG

Un archivo `.glang` consta de:
1. Directivas de inclusión (`include`).
2. Declaraciones de palabras clave (`Keyword`).
3. Definiciones de reglas gramaticales con sus combinadores y elementos hijos.

### 2.1 Directivas de Inclusión (`include`)

Importa gramáticas y combinadores expuestos por plugins instalados o archivos `.glang` externos:

```glang
include "expressions"
include "storage"
```

### 2.2 Declaración de Palabras Clave (`Keyword`)

Registra nuevas palabras reservadas directamente en el Lexer de Gram, asignándoles color para el editor de código, grupo léxico y documentación:

```glang
Keyword "function" {
    color: "#569CD6"
    group: "DECLARATIONS"
    description: "Declara una función invocable."
}

Keyword "let" {
    color: "#4EC9B0"
    group: "VARIABLES"
    description: "Declara una variable inmutable."
}
```

---

### 2.3 Definición de Reglas Gramaticales

La sintaxis principal utiliza el formato:

$$\text{<NOMBRE\_REGLA>}\quad\text{<COMBINADOR>:}$$
$$\quad\quad\text{<ELEMENTO\_1>}$$
$$\quad\quad\text{<ELEMENTO\_2>}$$

#### Combinadores Disponibles como Cabecera de Regla:
- `Seq:`: Secuencia ordenada estricta (todos deben coincidir en orden).
- `Alt:`: Alternativa (coincide con la primera rama exitosa).
- `Many:`: Cero o más repeticiones ($0..N$).
- `Some:`: Una o más repeticiones ($1..N$).
- `Opt:`: Opcional ($0..1$).
- `Separator:`: Lista de elementos delimitados por un separador.
- `Tokenize:`: Captura continua de tokens léxicos.

#### Elementos Hijos de Coincidencia:
Dentro de cada bloque indentado se definen los elementos a validar:

| Sintaxis en GLang | Equivalente en Python | Descripción |
| :--- | :--- | :--- |
| `tokens.NOMBRE` | `MatchToken(Token.NOMBRE)` | Coincide con un tipo de token del Lexer (`tokens.IDENT`, `tokens.NUMBER`, `tokens.PLUS`). |
| `words "texto"` | `MatchKeyword("texto")` | Coincide con una palabra clave específica. |
| `groups "GRUPO"` | `MatchGroup("GRUPO")` | Coincide con cualquier keyword de un grupo léxico (`WordGroup`). |
| `reference REGLA` | `Ref(REGLA)` | Referencia perezosa a otra regla definida en la gramática. |
| `literal "valor"` | `Literal("valor")` | Coincide con un valor literal constante exacto. |
| `seqsym "-" ">"` | `MatchSeqSymbol("-", ">")` | Secuencia de símbolos contiguos. |
| `pass` | `PASS` | Instrucción vacía (no-op). |

---

## 3. Ejemplo Completo de Especificación `.glang`

A continuación se muestra un archivo `calculadora.glang` completo:

```glang
# calculadora.glang — Especificación de Mini Lenguaje Aritmético

# 1. Palabras clave del lenguaje
Keyword "mostrar" {
    color: "#DCDCAA"
    group: "COMMANDS"
    description: "Muestra el resultado de una expresión."
}

# 2. Operaciones aritméticas elementales
OPERANDO Alt:
    tokens.NUMBER
    tokens.IDENT

SUMA_EXPR Seq:
    reference OPERANDO
    tokens.PLUS
    reference OPERANDO

RESTA_EXPR Seq:
    reference OPERANDO
    tokens.MINUS
    reference OPERANDO

MULT_EXPR Seq:
    reference OPERANDO
    tokens.STAR
    reference OPERANDO

# 3. Expresión general
EXPRESION Alt:
    reference SUMA_EXPR
    reference RESTA_EXPR
    reference MULT_EXPR
    reference OPERANDO

# 4. Declaración de sentencia "mostrar"
SENTENCIA_MOSTRAR Seq:
    words "mostrar"
    reference EXPRESION
    tokens.SEMICOLON

# 5. Punto de entrada de la gramática
DECLARATION Alt:
    reference SENTENCIA_MOSTRAR
```

---

## 4. Compilación y Uso en Python

Gram provee una interfaz unificada en el submódulo `gram.glang` para compilar e interpretar archivos `.glang`:

### Compilar a un Diccionario de Gramática Nativo

```python
import gram.glang

# Compilar un archivo .glang a un diccionario ejecutable de Gram
grammar_dict = gram.glang.compile("calculadora.glang")

# El diccionario resultante puede ser usado directamente en ASTAnalyzer
from gram.core.ast import ASTAnalyzer
analyzer = ASTAnalyzer("mostrar 10 + 20;", grammar_dict)
ast = analyzer.process()
```

### Usar `LanguageCompiler` Directamente

```python
from gram.glang import parse_glang_file, parse_dsl

# Desde un archivo
compiler = parse_glang_file("calculadora.glang")
ast = compiler.parse("mostrar 15 * 3;")

# O directamente desde un string DSL en memoria
dsl_codigo = """
ASIGNACION Seq:
    tokens.IDENT
    tokens.ASSIGN
    tokens.NUMBER
    tokens.SEMICOLON

DECLARATION Alt:
    reference ASIGNACION
"""
compilador_dsl = parse_dsl(dsl_codigo)
resultado_ast = compilador_dsl.parse("mi_variable = 42;")
```

---

## 5. Comandos GLANG en Gram CLI

Gram incluye soporte para manipular archivos `.glang`, generar extensiones de editor e instalar extensiones VSIX en VS Code directamente desde la línea de comandos:

```bash
# 1. Compilar un archivo .glang y validar su gramática
gram glang calculadora.glang
# o equivalentemente:
gram glang compile calculadora.glang

# 2. Parsear un archivo fuente utilizando una especificación .glang e imprimir el AST
gram glang calculadora.glang --source entrada.calc --print-ast

# 3. Generar la extensión VSIX de VS Code para GLANG buscando extensiones en plugins (*.glang.py)
gram glang generate vsix

# 4. Generar e instalar la extensión VSIX directamente en Visual Studio Code
gram glang --install vsix
# o también:
gram glang install vsix

# 5. Desinstalar la extensión de GLANG de Visual Studio Code
gram glang --uninstall vsix
# o también:
gram glang uninstall vsix
```

---

## 6. Extensibilidad de GLANG mediante Plugins (`*.glang.py`)

Cualquier plugin instalado o empaquetado en Gram puede extender las capacidades sintácticas y léxicas de GLANG incluyendo archivos con el patrón `*.glang.py` o `.glang.py` (por ejemplo: `expressions.glang.py`, `storage.glang.py`, `essencial.glang.py`).

### Estructura de un Archivo `*.glang.py`:
```python
# mi_plugin/mi_plugin.glang.py
from gram.core.lexer.words import add_group, add_keyword

def setup_glang() -> None:
    """Registra palabras clave, colores y combinadores en GLANG."""
    add_group("CUSTOM_OPS", color_group="#DCDCAA", allow_override=True)
    add_keyword("CustomCombinator", "#DCDCAA", group="CUSTOM_OPS", description="Mi nuevo combinador.", allow_override=True)
```

### Tolerancia a Fallos y Aislamiento:
Al ejecutar `gram glang generate vsix` o `gram glang --install vsix`, Gram escanea automáticamente todos los plugins en busca de archivos `*.glang.py`. 
- Si un plugin contiene un error sintáctico, una importación rota o una excepción en tiempo de ejecución en su `.glang.py`, **Gram captura el error, muestra una advertencia informativa e ignora ese plugin**.
- El generador **nunca se congela ni corrompe el VSIX generado**, garantizando máxima resiliencia en entornos de desarrollo con múltiples plugins de terceros.
