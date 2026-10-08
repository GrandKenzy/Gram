# Guía y Referencia del Sistema de Plugins de Gram (`gram.plugins`)

El sistema de plugins de Gram permite extender el lenguaje, enriquecer el pipeline de análisis léxico y sintáctico, e integrar combinadores, reglas, evaluadores y herramientas para Visual Studio Code de manera segura y modular.

---

## 1. Arquitectura y Ciclo de Vida de un Plugin

Todo plugin en Gram es un directorio autocontenido que debe cumplir con la estructura canónica:

```
mi_plugin/
├── manifest.json       # Metadatos, capacidades y permisos requeridos
├── main.py             # Clase principal que hereda de PluginBase
├── __init__.py         # Fachada pública de importación
└── ...                 # Módulos y recursos adicionales
```

### Clase Principal: `PluginBase` (`gram.plugins.base`)

En la arquitectura moderna de Gram, todo plugin **debe** definir en su `main.py` una clase que herede de `PluginBase`. 

```python
from __future__ import annotations
from typing import Any
from gram.plugins.base import PluginBase
from gram.core.combinators.base import RuleItem

class MiPlugin(PluginBase):
    """Implementación oficial del plugin."""

    def on_load(self) -> bool:
        """
        Ejecutado automáticamente al cargar el plugin en memoria.
        Registra combinadores personalizados y compila extensiones si aplica.
        """
        return True

    def process(self, *args: Any, **kwargs: Any) -> Any:
        """
        Punto de entrada de procesamiento manual del plugin (invocado por gram.process).
        """
        return True

    def cli(self, *args: Any, **kwargs: Any) -> int:
        """
        Punto de entrada para comandos personalizados desde la consola CLI de Gram.
        """
        return 0

    def get_combinators(self) -> list[Any]:
        """Retorna las clases de combinadores expuestas por el plugin."""
        return []

    def get_rules(self) -> list[type[RuleItem]]:
        """Retorna las clases RuleItem expuestas por el plugin."""
        return []

    def get_grammar(self) -> dict[Any, Any]:
        """Retorna el diccionario de gramática física para ASTAnalyzer."""
        return {}
```

---

## 2. Manifiesto del Plugin (`manifest.json`)

El archivo `manifest.json` define la identidad, compatibilidad y capacidades activas del plugin:

```json
{
  "uuid": "a8f3b612-4c28-4e1a-9f5b-7d312c5e89a1",
  "plugin_name": "mi_plugin",
  "version": "1.0.0",
  "min_engine": "1.0.0",
  "min_python_version": [3, 10],
  "author": "Desarrollador Gram",
  "description": "Descripción detallada del plugin y sus capacidades.",
  "short": "Resumen en una línea",
  "main": "main.py",
  "type": "extendable",
  "use_venv": false,
  "version_state": "Stable",
  "capabilities": {
    "load": true,
    "process": true,
    "cli": false,
    "replaceable": false,
    "protect": 3
  },
  "requests": [],
  "config_requests": {},
  "python_lib_requests": {}
}
```

### Capacidades (`capabilities`)
- `load` (`bool`): Si es `True`, Gram invoca automáticamente `on_load()` al registrar el plugin.
- `process` (`bool`): Si es `True`, habilita `process()` para evaluar entradas y AST.
- `cli` (`bool`): Si es `True`, expone comandos directamente a la terminal de Gram (`gram <plugin_name>`).
- `protect` (`int`): Nivel de protección de memoria (1 a 4).

---

## 3. Seguridad Estática y Permisos

Para proteger el entorno del usuario, Gram aplica una verificación estática mediante AST y un sistema de permisos estricto:

### Auditoría de Código AST (`gram check`)
Antes de permitir la instalación o carga de un plugin, Gram analiza el árbol sintáctico de todos los archivos `.py` del plugin para garantizar:
- **Prohibición de ejecución dinámica:** No se permite el uso de `eval()`, `exec()`, llamadas directas a `compile()` ni `__import__()`.
- **Aislamiento de Builtins y Dunders:** Prohibido el acceso no autorizado a `__builtins__`, inspección de atributos especiales restringidos (`__subclasses__`, `__bases__`, etc.).
- **Aislamiento de Importaciones:** Solo se permiten módulos estándar de Python aprobados y submódulos de `gram.*`.

### Permisos del Usuario (`gram.plugins.permissions`)
Cualquier solicitud de acceso al sistema (archivos fuera del sandbox, librerías del sistema, variables de configuración) requiere la aprobación expresa del usuario final antes de que el plugin pueda ejecutarse.

---

## 4. Plugins Oficiales

Gram incluye tres plugins fundamentales en `gram/plugins/source/`:

```
gram/plugins/source/
├── storage/               # Almacenamiento en memoria y etiquetado
├── expressions/           # Expresiones matemáticas, asociatividad y evaluador
└── GRAM_ESSENCIAL_PACK/   # Kit de desarrollo, SimpleCombinator, If y utilidades
```

---

### Plugin 1: `storage`

El plugin `storage` provee mecanismos de retención de tokens en memoria y etiquetado semántico en el árbol de análisis sin realizar un consumo destructivo de tokens.

#### Componentes Clave:
- **`StorageStacK`:** Pila global en memoria accesible por clave (`StorageStacK.save(key, token)`, `StorageStacK.get(key)`, `StorageStacK.clear()`).
- **`Save(key)`:** Combinador que guarda el token actual bajo la clave especificada y revierte el cursor para que las reglas subsiguientes lo procesen.
- **`Load(key)`:** Recupera el token previamente almacenado bajo la clave indicada.
- **`Tag(name)`:** Inyecta un token semántico identificador (`tag.<nombre>`) en el AST sin consumir caracteres del código fuente.

#### Ejemplo de Uso:
```python
from gram.core.parser import Parser
from gram.core.lexer import Lexer, Token
from gram.plugins.source.storage import Save, Load, Tag, StorageStacK

code = "variable_usuario"
tokens = Lexer(code).process()
parser = Parser(tokens)
tok = parser.consume()

# 1. Guardar sin consumir
save_comb = Save("mi_var")
save_comb.parse(parser, tok)

# 2. Recuperar desde StorageStacK
recuperado = StorageStacK.get("mi_var")
print(f"Token guardado: {recuperado.value}") # "variable_usuario"

# 3. Etiquetado semántico
tag_comb = Tag("declaracion")
token_etiqueta = tag_comb.parse(parser, tok)
print(f"Token generado: {token_etiqueta.value}") # "tag.declaracion"
```

---

### Plugin 2: `expressions`

El plugin `expressions` soluciona el problema de construir analizadores de expresiones aritméticas y lógicas con múltiples niveles de precedencia y asociatividad.

#### Componentes Clave:
- **`ChainL(operand, operator)`:** Resuelve asociatividad por la izquierda ($a + b + c \to ((a + b) + c)$).
- **`ChainR(operand, operator)`:** Resuelve asociatividad por la derecha ($a ** b ** c \to (a ** (b ** c))$).
- **`ExpressionBuilder`:** Constructor fluido declarativo de precedencias.
- **`ARITHMETIC_EXPR`:** Regla sintáctica completa con soporte para `+`, `-`, `*`, `/`, `//`, `%`, `**`, unarios (`+`, `-`) y paréntesis anidados.
- **`ArithmeticExpr`:** Combinador que devuelve un AST operacional de nodos `ASTNode`; cada operación conserva sus operandos y su operador, en lugar de entregar una lista plana de tokens.
- **`ConditionalExpr`:** Combinador que valida comparaciones y lógica, y conserva la misma estructura operacional para su procesamiento posterior.
- **`evaluate(expression, env=None)`:** Evaluador de árbol sintáctico puro (seguro, sin `eval` de Python) que soporta variables y funciones matemáticas.

#### AST operacional de expresiones
`ArithmeticExpr.parse(...)` y `ConditionalExpr.parse(...)` producen un árbol procesable. Los nodos `Op` conservan la operación y sus operandos en orden: `op1` es el operando izquierdo (o el único operando de una operación unaria), `op2` es el derecho y `operator` contiene el token original del operador. Los atributos incluyen el operador como texto y su aridad.

Los operandos se representan recursivamente como nodos `Number`, `Boolean`, `Identifier`, `Group` o `Call`. Los grupos mantienen sus paréntesis; las llamadas conservan el nombre de la función, los argumentos y la puntuación de origen. Así, la precedencia y la asociación quedan explícitas en la forma del árbol:

```text
(10 + 20) * 3
Op(operator="*", arity=2)
├── op1: Group
│   └── Op(operator="+", arity=2)
│       ├── op1: Number(value=10)
│       └── op2: Number(value=20)
└── op2: Number(value=3)
```

Ejemplo de análisis, inspección y evaluación del mismo AST:

```python
from gram.core.lexer import Lexer
from gram.core.parser import Parser
from gram.plugins.source.expressions import ArithmeticExpr, evaluate

parser = Parser(Lexer("(10 + 20) * 3").process())
tree = ArithmeticExpr().parse(parser, parser.peek())

assert tree.name == "Op"
assert tree.attributes["operator"] == "*"
assert tree.op1.name == "Group"
assert tree.op2.attributes["value"] == 3
assert evaluate(tree) == 90
```

La evaluación acepta directamente el árbol operacional. También se puede recorrer con `walk()`, buscar nodos por nombre con `find()`, consultar `attributes` y obtener los tokens originales con `collect_tokens()`. En reglas gramaticales, `ARITHMETIC_EXPR` y `CONDITIONAL_EXPR` son transparentes para evitar un bloque envolvente redundante; se conserva la jerarquía operacional interna.

#### Funciones Matemáticas Disponibles en `evaluate()`:
`sqrt`, `abs`, `min`, `max`, `sin`, `cos`, `tan`, `round`, `floor`, `ceil`, `log`, `exp`, `pow`.

#### Ejemplo de Uso:
```python
from gram.plugins.source.expressions import evaluate, ExpressionsPlugin

# 1. Evaluación aritmética con precedencia y paréntesis
res1 = evaluate("2 + 3 * 4")        # 14
res2 = evaluate("(2 + 3) * 4")      # 20
res3 = evaluate("2 ** 3 ** 2")      # 512 (asociativo por la derecha: 2 ** 9)

# 2. Evaluación con variables de entorno
entorno = {"radio": 5, "pi": 3.14159}
area = evaluate("pi * radio ** 2", env=entorno)

# 3. Funciones matemáticas
res_math = evaluate("sqrt(16) + min(10, 5)") # 9.0

# 4. Uso a través de la instancia del plugin
plugin = ExpressionsPlugin()
plugin.process("100 / (2 + 3)") # 20.0
```

---

### Plugin 3: `GRAM_ESSENCIAL_PACK` (GEP)

`GRAM_ESSENCIAL_PACK` es el kit de utilidades y abstracción para desarrolladores de Gram. Simplifica la creación de plugins y añade combinadores de control de flujo.

#### Componentes Clave:
- **`SimpleCombinator`:** Clase base para crear combinadores con predicados sobre tokens individuales.
- **`If`:** Combinador condicional con ramas `ok` y `fail`, y soporte para lookahead anticipado (`restore=True`).
- **`ErrorCombinator`:** Captura e inspecciona errores en la pila `StackError`.
- **`Req`:** Fluent API para validación y mutación de tokens (`.is_lower()`, `.length()`, etc.).
- **`Skip`, `Peek`, `Not`, `Until`:** Primitivas de control de flujo y lookahead.
- **API de Registro:** `register_keyword`, `register_rule`, `register_group`, `register_error`, `register_combinator`.

#### Ejemplo: Creación de un Plugin Nuevo Usando GEP

A continuación se muestra cómo crear un plugin completo en pocas líneas utilizando `GRAM_ESSENCIAL_PACK`:

```python
# mi_extension/main.py
from __future__ import annotations
from typing import Any
from gram.plugins.base import PluginBase
from gram.core.lexer import Token, TokenType
from gram.plugins.source.GRAM_ESSENCIAL_PACK import (
    SimpleCombinator,
    register_keyword,
    register_rule,
    Seq,
    MatchKeyword,
    MatchToken,
)

# 1. Definir un combinador simple
class SoloMayusculas(SimpleCombinator):
    def evaluate(self, current: TokenType) -> bool:
        return current.token == Token.IDENT and str(current.value).isupper()

# 2. Definir la clase del plugin
class MiExtensionPlugin(PluginBase):
    def on_load(self) -> bool:
        # Registrar una palabra clave nueva
        register_keyword("constante", color="#FFA500")

        # Registrar una regla sintáctica: constante NOMBRE_MAYUSCULA = 123;
        register_rule(
            name="CONST_DECL",
            code=8001,
            combinator=Seq(
                MatchKeyword("constante"),
                SoloMayusculas(),
                MatchToken(Token.ASSIGN),
                MatchToken(Token.NUMBER),
                MatchToken(Token.SEMICOLON),
            ),
            description="Declaración de constantes en mayúsculas",
        )
        return True

    def process(self, *args: Any, **kwargs: Any) -> Any:
        return True
```

---

## 5. Gestión de Plugins mediante Gram CLI

La herramienta de línea de comandos de Gram (`gram.cli`) provee comandos dedicados para la administración del ciclo de vida de los plugins:

```bash
# Validar estáticamente e inspeccionar un plugin sin instalarlo
python -m gram.cli check gram/plugins/source/storage

# Instalar un plugin en el catálogo global de Gram
python -m gram.cli install gram/plugins/source/expressions

# Listar todos los plugins instalados y su estado
python -m gram.cli list

# Cargar y verificar un plugin en memoria
python -m gram.cli load expressions

# Desinstalar un plugin
python -m gram.cli uninstall expressions
```
