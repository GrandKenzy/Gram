# CExample: Motor Mínimo de Parsing de C con Gram Framework

`CExample` es un proyecto de demostración práctico que enseña cómo construir un analizador sintáctico para un lenguaje real utilizando las capacidades nativas del **Gram Framework**.

Demuestra que Gram no es solo una biblioteca de análisis conceptual, sino un motor de combinadores de gramáticas robusto, extensible y declarativo capaz de procesar lenguajes de programación de nivel industrial como C.

---

## 1. Características Soportadas

El motor sintáctico de `CExample` reconoce un subconjunto expresivo del lenguaje C:

- **Tipos de datos nativos:** `int`, `char`, `float`, `double`, `void`, `short`, `long`, `unsigned`, `signed`, `const`.
- **Modificadores de puntero:** Declaración de punteros escalares y múltiples (`int* ptr`, `char** argv`).
- **Declaración e inicialización de variables:** Variables locales y globales con valores por defecto o expresiones (`int total = 0;`).
- **Prototipos de funciones:** Declaraciones formales de cabecera terminadas en punto y coma (`int add(int a, int b);`).
- **Definiciones completas de funciones:** Funciones con parámetros y bloques de código delimitados por llaves `{ ... }`.
- **Sentencias de control de flujo:**
  - Condicionales `if (cond) { ... } else { ... }`
  - Bucles `while (cond) { ... }`
  - Bucles `for (init; cond; step) { ... }`
  - Sentencias de salida y control: `return expr;`, `break;`, `continue;`.
- **Expresiones aritméticas y lógicas:** Operadores `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `||`.
- **Llamadas a funciones:** Invocación con argumentos separados por coma (`factorial(n - 1)`, `printf(...)`).
- **Preprocesador y comentarios:**
  - Extracción automática de directivas `#include <stdio.h>` o `#include "header.h"`.
  - Comentarios de una línea `// ...`.
  - Comentarios multilínea `/* ... */`.

---

## 2. Estructura del Proyecto

```
examples/CExample/
├── grammar.py        # Definición de reglas RuleItem y combinadores Gram
├── c_parser.py       # Clase CParser (preprocesador, tokenizador, ASTAnalyzer, símbolos)
├── sample.c          # Archivo de prueba en C con variables, recursión, bucles y llamadas
├── main.py           # Ejecutable CLI que parsea un archivo .c y muestra el AST
├── __init__.py       # Exportaciones públicas de la API de CExample
└── README.md         # Esta documentación técnica
```

---

## 3. ¿Cómo Funciona la Gramática en Gram?

En Gram, cada constructo sintáctico se define como una subclase de `RuleItem` y se compone mediante **combinadores declarativos**:

### Palabras Clave y Colores de Resaltado
Las palabras clave de C se registran con sus códigos de color hexadecimales para soporte de editores (incluido VSIX de VS Code):
```python
words.add_keyword("int", hex_color="#4EC9B0")
words.add_keyword("return", hex_color="#C586C0")
words.add_keyword("while", hex_color="#C586C0")
```

### Declaración de Variables (`C_VAR_DECL`)
```python
class C_VAR_DECL(RuleItem):
    code = 9112
    name = "C_VAR_DECL"
    description = "Declaración de variable: tipo [*] id [= expr]? ;"
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        MatchToken(Token.IDENT),
        Opt(Seq(MatchToken(Token.ASSIGN), Ref(C_EXPR))),
        MatchToken(Token.SEMICOLON),
    )
```

### Sentencias de Control (`C_IF_STMT` y `C_WHILE_STMT`)
```python
class C_IF_STMT(RuleItem):
    code = 9120
    name = "C_IF_STMT"
    grammar = Seq(
        MatchKeyword("if"),
        MatchToken(Token.LPAREN),
        Ref(C_EXPR),
        MatchToken(Token.RPAREN),
        Alt(Ref(C_BLOCK), Ref("C_STMT")),
        Opt(Seq(MatchKeyword("else"), Alt(Ref(C_BLOCK), Ref("C_STMT")))),
    )
```

### Definición de Funciones (`C_FUNC_DEF`)
```python
class C_FUNC_DEF(RuleItem):
    code = 9126
    name = "C_FUNC_DEF"
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        MatchToken(Token.IDENT),
        Ref(C_FUNC_PARAMS),
        Ref(C_BLOCK),
    )
```

### Integración en el Diccionario del Parser
Todas las reglas se enlazan en el diccionario formal de Gram comenzando desde `PROGRAM`:
```python
c_grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(
        Ref(C_FUNC_DEF),
        Ref(C_FUNC_DECL),
        Ref(C_VAR_DECL),
        Ref(C_STMT),
    ),
    C_TYPE: C_TYPE.grammar,
    C_VAR_DECL: C_VAR_DECL.grammar,
    C_FUNC_DEF: C_FUNC_DEF.grammar,
    # ...
}
```

---

## 4. Ejecución del Ejemplo

### Desde la Línea de Comandos (CLI)
Para parsear el archivo de demostración incluido ([sample.c](file:///c:/Users/Kentucky/Desktop/Gram/examples/CExample/sample.c)):

```powershell
python examples/CExample/main.py
```

O para analizar cualquier archivo `.c` externo:

```powershell
python examples/CExample/main.py ruta/a/tu_codigo.c
```

### Uso Programático desde Python

```python
from examples.CExample import CParser

parser = CParser()

codigo_c = """
#include <stdio.h>

int factorial(int n) {
    if (n <= 1) {
        return 1;
    } else {
        return n * factorial(n - 1);
    }
}
"""

# 1. Parsear y obtener el AST
ast = parser.parse(codigo_c)

# 2. Extraer tabla de símbolos
simbolos = parser.extract_symbols(ast)
print("Funciones:", simbolos["functions"])
print("Includes:", simbolos["includes"])

# 3. Imprimir el árbol jerárquico
print(parser.format_tree(ast))
```

---

## 5. Salida de Ejemplo (`sample.c`)

Al ejecutar `python examples/CExample/main.py`, Gram genera la siguiente salida estructurada:

```text
======================================================================
  Gram Framework - CExample: Motor Mínimo de Parsing de Lenguaje C
======================================================================
Archivo objetivo: .../examples/CExample/sample.c

----------------------------------------------------------------------
  1. RESUMEN DE SÍMBOLOS EXTRAÍDOS
----------------------------------------------------------------------
Directivas #include:
  * #include <stdio.h>

Variables Globales (1):
  * Línea  6: int g_max_iterations

Funciones (5):
  * Línea  9: [Prototipo ] int add()
  * Línea 12: [Definición] int factorial()
  * Línea 21: [Definición] int sum_to_n()
  * Línea 32: [Definición] int add()
  * Línea 37: [Definición] int main()

----------------------------------------------------------------------
  2. ÁRBOL DE SINTAXIS ABSTRACTA (AST)
----------------------------------------------------------------------
ASTProgram (Declaraciones raíz: 6)
+-- Includes de Preprocesador:
|   +-- #include <stdio.h>
+-- \-- [L0] C_VAR_DECL (code=9112) [BLOCK] -> values=['int', 'g_max_iterations']
|       +-- [L1] C_POINTER (code=9102)
|       \-- [L1] C_EXPR (code=9111) -> values=[100]
+-- \-- [L0] C_FUNC_DECL (code=9127) [BLOCK] -> values=['int', 'add']
|       +-- [L1] C_POINTER (code=9102)
|       \-- [L1] C_FUNC_PARAMS (code=9125) [BLOCK]
|           \-- [L2] C_PARAMS (code=9114) [BLOCK]
|               +-- [L3] C_PARAM (code=9113) [BLOCK] -> values=['int', 'a']
|               |   \-- [L4] C_POINTER (code=9102)
|               \-- [L3] C_PARAM (code=9113) [BLOCK] -> values=['int', 'b']
|                   \-- [L4] C_POINTER (code=9102)
+-- \-- [L0] C_FUNC_DEF (code=9126) [BLOCK] -> values=['int', 'factorial']
|       +-- [L1] C_POINTER (code=9102)
|       +-- [L1] C_FUNC_PARAMS (code=9125) [BLOCK]
|       |   \-- [L2] C_PARAMS (code=9114) [BLOCK]
|       |       \-- [L3] C_PARAM (code=9113) [BLOCK] -> values=['int', 'n']
|       |           \-- [L4] C_POINTER (code=9102)
|       \-- [L1] C_BLOCK (code=9119) [BLOCK]
|           \-- [L2] C_IF_STMT (code=9120) [BLOCK] -> values=['if', 'else']
|               +-- [L3] C_EXPR (code=9111) -> values=['n', 1]
|               +-- [L3] C_BLOCK (code=9119) [BLOCK]
|               |   \-- [L4] C_RETURN_STMT (code=9115) [BLOCK] -> values=['return']
|               |       \-- [L5] C_EXPR (code=9111) -> values=[1]
|               \-- [L3] C_BLOCK (code=9119) [BLOCK]
|                   \-- [L4] C_RETURN_STMT (code=9115) [BLOCK] -> values=['return']
|                       \-- [L5] C_EXPR (code=9111) [BLOCK] -> values=['n']
|                           \-- [L6] C_UNARY (code=9109) [BLOCK]
|                               \-- [L7] C_PRIMARY (code=9107) [BLOCK]
|                                   \-- [L8] C_CALL (code=9105) [BLOCK] -> values=['factorial']
|                                       \-- [L9] C_CALL_ARGS (code=9104) -> values=['n', 1]
...
----------------------------------------------------------------------
  3. MÉTRICAS DEL ANÁLISIS
----------------------------------------------------------------------
Total declaraciones raíz analizadas: 6
Distribución de sentencias: {'C_VAR_DECL': 1, 'C_FUNC_DECL': 1, 'C_FUNC_DEF': 4}

[OK] Análisis sintáctico completado con éxito con Gram Framework.
```

---

## 6. Pruebas Unitarias

El motor incluye una suite exhaustiva de pruebas en [gram/tests/test_c_example.py](file:///c:/Users/Kentucky/Desktop/Gram/gram/tests/test_c_example.py). Para ejecutarlas:

```powershell
python -m unittest gram/tests/test_c_example.py
```
