# Preprocesamiento, conversiones y expectativas

Estos combinadores permiten validar el token actual, registrar conversiones lógicas de identificadores y expresar condiciones estrictas sin consumir tokens.

## `Preprocess`

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
