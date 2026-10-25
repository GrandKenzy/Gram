# Preprocesamiento, conversiones y expectativas

Estos combinadores permiten validar el token actual, registrar conversiones lógicas de identificadores y expresar condiciones estrictas sin consumir tokens.

## `Preprocess`

> [!WARNING]
> **`Preprocess` es experimental y peligroso.** El callback se ejecuta dentro
> del análisis y la responsabilidad de sus efectos recae completamente en el
> usuario. Gram no puede saber si la lógica personalizada respeta las reglas
> de tu lexer, tus tablas de símbolos, tus conversiones o tu modelo de AST.
> Al usar `Preprocess`, tienes libertad total para inspeccionar y coordinar el
> análisis, pero también puedes romper sus invariantes y producir resultados
> difíciles de depurar.

`Preprocess` no es un sandbox ni una segunda fase automática del lexer: es un
punto de extensión ejecutado sobre el token efectivo actual. La única
 garantía estricta de Gram es que el callback debe devolver exactamente
 `True` y no puede mover `parser.pos`. Cualquier estado externo que modifiques
 —archivos, variables globales, registros léxicos o servicios externos— debe
 ser administrado y revertido por tu propia implementación.

### Herramientas para mantener el control

Antes de usar `Preprocess` para cambiar el comportamiento de un frontend,
combínalo con mecanismos que hagan explícito el ciclo de vida del estado:

- **Checkpoints y rollback:** crea un `parser.savepoint("nombre")` antes de
  una operación delicada y usa `parser.restore(checkpoint)` para volver atrás.
  El rollback cubre el estado que el parser rastrea —cursor, conversiones,
  tags, almacenamiento y reemplazos de tokens—, pero no deshace efectos
  externos realizados por el callback.
- **`failure_scope()` / `safe_mode()`:** agrupa validaciones especulativas y
  evita publicar inmediatamente un diagnóstico que todavía puede ser
  descartado por `Alt`, `Opt` u otro combinador de control.
- **Sesiones (`gram.sessions.Session`):** separa configuraciones de lenguajes
  distintos. Configura el lexer dentro de una sesión y usa `clear_global()`,
  `init()`, `migrate()` y `load()` para alternar entre frontends sin dejar
  registros léxicos contaminados entre archivos.
- **Conversiones explícitas:** usa `parser.export_conversions()` e
  `parser.import_conversions()` para compartir solo las conversiones que
  quieras. Para conservarlas entre archivos, pasa un `ConversionState`; si no
  lo pasas, cada parseo empieza aislado.
- **`Save` y `Load` con almacenamiento propio:** guarda datos dinámicos en un
  diccionario controlado por tu frontend, en lugar de depender siempre de
  `parser.storage`. El parser puede rastrear ese almacenamiento para incluirlo
  en los checkpoints.
- **`Expected` y `MatchToken`:** expresa invariantes como combinadores
  declarativos. Así reduces la cantidad de reglas manuales que el callback
  debe imponer y permites que el parser diagnostique los fallos.
- **Diagnósticos y `RayTracing`:** durante el desarrollo, desactiva la salida
  inmediata si necesitas inspeccionar varios errores y usa el tracing
  detallado para observar posiciones restauradas, ramas y resultados del
  análisis.

### Reglas prácticas

1. Mantén el callback corto, determinista y sin I/O.
2. Lee el token recibido y evita `consume()`, `advance()` o cualquier llamada
   que cambie `parser.pos`.
3. No mezcles registros globales del lexer con estado específico de un archivo;
   usa `Session` o una estructura explícita de contexto.
4. Si el callback muta estado que Gram no conoce, define tu propio snapshot y
   rollback junto con el checkpoint del parser.
5. Prueba siempre el camino de éxito, rechazo, excepción y backtracking.

```python
from gram.core.combinators import MatchToken, Preprocess, Seq
from gram.core.lexer import Token

Preprocess(func)
```

La función recibe `(analyzer, token)` y debe devolver exactamente `True`:

```python
def valid_name(analyzer, token):
    return str(token.value).isidentifier()

rule = Seq(Preprocess(valid_name), MatchToken(Token.IDENT))
```

`False`, `None`, otro retorno o una excepción producen un error. `Preprocess` no puede mover el cursor.

## `Convert`

```python
from gram.core.combinators import Convert, MatchToken, Seq
from gram.core.lexer import Token

Convert("Bunga", Token.DOT)
Convert("Bunga", Token.DOT, scope=True)
```

La conversión es exacta y solo afecta identificadores con el valor indicado.

- `scope=False`: convierte únicamente el token actual.
- `scope=True`: registra la conversión en el parser y los tokens futuros se resuelven lógicamente con el nuevo tipo.

El flujo físico de tokens no se recorre ni se reescribe completo. `MatchToken` consulta el tipo lógico:

```python
Seq(
    Convert("Bunga", Token.DOT, scope=True),
    MatchToken(Token.DOT),
)
```

Las conversiones con alcance forman parte de los checkpoints y se revierten durante el backtracking.

### Compartir conversiones entre archivos

Las conversiones activas pueden extraerse como una copia independiente:

```python
exported = parser_a.export_conversions()
parser_b.import_conversions(exported)
```

Para compartirlas directamente entre llamadas a `Session.parse()`, use `ConversionState`:

```python
state = session.new_conversion_state()

session.parse(tokens_a, "a.c", conversion_state=state)
session.parse(tokens_b, "b.c", conversion_state=state)
```

Sin `conversion_state`, cada archivo comienza con un estado nuevo. Un estado puede clonarse o limpiarse:

```python
isolated = state.clone()
state.clear()
```

El estado externo solo se actualiza si el parseo termina correctamente.

## `Expected`

Todas las variantes son aserciones de ancho cero:

```python
from gram.core.combinators import Expected

Expected.newline()
Expected.count(3)
Expected.ncount(2)
Expected.indent(4)
```

- `newline`: el siguiente token significativo debe estar en una línea posterior.
- `count`: deben quedar exactamente `n` tokens antes de `EOF`.
- `ncount`: no deben quedar exactamente `n` tokens antes de `EOF`.
- `indent`: la columna de indentación activa debe ser `n`.

Ninguna variante consume tokens.
