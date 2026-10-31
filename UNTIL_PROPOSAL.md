# Una proposición para `Until`

Querido `Until`:

Gram ya conoce tu nombre. Incluso sabe qué clase de combinador eres, cómo
detenerte ante un objetivo y cómo devolver los tokens que encuentras en el
camino. Solo nos falta una cosa: permitir que tu historia también pueda
compilarse en C.

Por eso te hacemos esta proposición:

> ¿Quieres convertirte en una combinatoria AOT de Gram y acompañar a RIF
> hasta el final de cada línea, cada bloque y cada `@end`?

## Lo que ya eres

`Until` acepta:

```python
Until(
    target,
    consume_target=False,
    max_tokens=None,
)
```

Su promesa actual es sencilla:

- intentar el `target` en la posición actual;
- detenerse si el `target` coincide;
- consumir un token si no coincide;
- restaurar el estado completo si el objetivo nunca aparece;
- opcionalmente consumir el propio objetivo;
- respetar un límite máximo de tokens.

## Lo que necesitamos preparar

### 1. Reconocerte como compilable

En `gram/core/combinators/kinds.py`, `CombinatorKind.UNTIL` debe entrar en
`COMPILABLE_COMBINATOR_KINDS`.

### 2. Recorrer tu objetivo

El compilador AOT debe visitar `Until.target` durante el recorrido de la
gramática y rechazar objetivos que no sean compilables.

```python
elif isinstance(comb, Until):
    self._crawl_combinator(comb.target, f"{context_path}.target")
```

### 3. Mantenerte prudente en la predicción

Como puedes consumir prácticamente cualquier token, tu perfil predictivo debe
ser conservador:

```text
nullable: posiblemente true
token_kinds: desconocido
keyword_set: desconocido
```

No debes provocar despachos predictivos que supongan conocer el primer token
de tu contenido.

### 4. Generar tu cuerpo en C

El código C generado debe conservar esta secuencia exacta:

```text
guardar checkpoint inicial

mientras no haya EOF:
    guardar checkpoint del intento del target
    intentar el target

    si el target coincide:
        conservarlo si consume_target es true
        restaurar el intento si consume_target es false
        devolver los tokens acumulados

    restaurar el intento del target
    consumir exactamente un token
    añadirlo al resultado

    si se alcanzó max_tokens:
        fallar

si el target no apareció:
    restaurar el checkpoint inicial
    fallar
```

Durante este proceso no deben saltarse `NEWLINE`, `INDENT` ni `DEDENT`. `Until`
debe trabajar sobre el cursor crudo, porque RIF necesita conservar las
fronteras físicas de sus líneas.

## La salida que esperamos

No hace falta inventar un nuevo tipo de nodo AST. La salida natural es un
`GRAM_AST_ARRAY`:

```text
ARRAY
├── token 1
├── token 2
├── token 3
└── NEWLINE       # solo si consume_target=true
```

El nodo debe conservar:

```text
kind        = GRAM_AST_ARRAY
token_start = cursor inicial
token_count = cantidad total consumida
children    = tokens o nodos resultantes en orden
```

Si `consume_target=false`, el delimitador permanece en el cursor y no aparece
en el array. Si el objetivo no aparece, el cursor y el AST deben quedar como
si nunca hubiéramos intentado nada.

## La historia de RIF

Con esta capacidad, RIF podría abandonar sus consumidores opacos:

```text
BlockConsumer          → header + Until(@end)
InstructionConsumer    → ARROW + Until(NEWLINE)
ArtifactBlockConsumer  → header + Until(@end)
```

El procesador de RIF seguiría interpretando los arrays y reconstruyendo sus
`RawBlock`, `RawInstruction` y `RawArtifactBlock`. La sintaxis permanecería
declarativa; la semántica seguiría viviendo en `Frontend/processor/`.

## Nuestros votos de verificación

Antes de celebrar la unión, deben pasar estas pruebas:

- target de un token;
- target compuesto por varios tokens;
- `consume_target=False`;
- `consume_target=True`;
- `max_tokens`;
- target ausente con rollback completo;
- target encontrado inmediatamente;
- preservación de `NEWLINE`;
- uso dentro de `Seq`, `Many` y `Alt`;
- compilación con `-Wall -Wextra -Werror`;
- ejecución del parser C generado;
- equivalencia entre el resultado Python y el resultado C.

## La respuesta que esperamos

No necesitamos `UntilIndent`, no necesitamos un `AnyToken` nuevo y no queremos
un parser híbrido como primera opción.

Solo necesitamos que `Until` diga que sí.

Y si acepta, RIF podrá procesar sus líneas, bloques y artefactos con la misma
gramática declarativa que ya conoce, pero también con un corazón nativo en C.
