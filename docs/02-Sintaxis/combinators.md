# Catálogo Completo de Combinadores Sintácticos (`gram.core.combinators`)

El sistema de combinadores de Gram provee los bloques constructivos declarativos, modulares y atómicos para la definición y análisis de gramáticas. 

En la arquitectura moderna de Gram:
- **La posición del cursor en el `Parser` (`parser.savepoint()` / `parser.restore()`) actúa como la única fuente de verdad (*Single Source of Truth*)**, garantizando backtracking atómico, composición limpia y cero efectos colaterales.
- **Invocación Unificada:** Todos los combinadores implementan `parse(analyzer, current, ignore_errors)` y soportan despacho directo mediante `Combinator._dispatch_sub()`.
- **Integración con Errores Formales OSGDC:** Utilizan la taxonomía centralizada de `gram.errors` (`COMBINATOR_FAILED`, `PARSER_EARLY_EOF`, `PARSER_UNEXPECTED_TOKEN`, etc.).

---

## Tabla de Contenidos

1. [Combinadores Nativos de Coincidencia (Matchers)](#1-combinadores-nativos-de-coincidencia-matchers)
   - [MatchToken](#matchtoken)
   - [MatchKeyword](#matchkeyword)
   - [MatchGroup](#matchgroup)
   - [MatchSymbol](#matchsymbol)
   - [MatchSeqSymbol](#matchseqsymbol)
   - [Literal](#literal)
   - [Item](#item)
2. [Combinadores Nativos de Estructura y Flujo](#2-combinadores-nativos-de-estructura-y-flujo)
   - [Seq (Secuencia)](#seq-secuencia)
   - [Alt (Alternativa)](#alt-alternativa)
   - [Opt (Opcional)](#opt-opcional)
   - [Many (Cero o Más)](#many-cero-o-más)
   - [Some (Uno o Más)](#some-uno-o-más)
   - [Separator / Sep (Separador)](#separator--sep-separador)
   - [Enclosed / Bracketed (Delimitados)](#enclosed--bracketed-delimitados)
   - [Ref (Referencia Perezosa)](#ref-referencia-perezosa)
   - [Tokenize](#tokenize)
3. [Combinadores del Plugin `storage`](#3-combinadores-del-plugin-storage)
   - [Save](#save)
   - [Load](#load)
   - [Tag](#tag)
4. [Combinadores del Plugin `expressions`](#4-combinadores-del-plugin-expressions)
   - [ChainL (Asociatividad Izquierda)](#chainl-asociatividad-izquierda)
   - [ChainR (Asociatividad Derecha)](#chainr-asociatividad-derecha)
   - [ExpressionBuilder](#expressionbuilder)
   - [ArithmeticExpr](#arithmeticexpr)
   - [IsDigit](#isdigit)
   - [MathBinaryOp, MathUnaryOp, MathGroup](#mathbinaryop-mathunaryop-mathgroup)
5. [Combinadores del Plugin `GRAM_ESSENCIAL_PACK`](#5-combinadores-del-plugin-gram_essencial_pack)
   - [SimpleCombinator](#simplecombinator)
   - [If (Condicional y Lookahead)](#if-condicional-y-lookahead)
   - [ErrorCombinator](#errorcombinator)
   - [Req (Requerimientos Fluidos)](#req-requerimientos-fluidos)
   - [Skip](#skip)
   - [Peek (Lookahead Positivo)](#peek-lookahead-positivo)
   - [Not (Lookahead Negativo)](#not-lookahead-negativo)
   - [Until (Consumo hasta Objetivo)](#until-consumo-hasta-objetivo)

---

## 1. Combinadores Nativos de Coincidencia (Matchers)

### `MatchToken`
Valida que el token actual coincida con un tipo específico de token (`Token` enum, `CustomToken` o cadena de texto).

- **Firma:** `MatchToken(token: Token | CustomToken | str)`
- **Consumo:** Consume exactamente 1 token si coincide. Si no coincide, revierte el cursor y retorna `None` (o lanza `ParserError` si `ignore_errors=False`).
- **Ejemplo:**
  ```python
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  match_ident = MatchToken(Token.IDENT)
  match_number = MatchToken(Token.NUMBER)
  ```

### `MatchKeyword`
Valida que el token actual sea una palabra clave registrada formalmente en el Lexer.

- **Firma:** `MatchKeyword(keyword: str | Keyword)`
- **Consumo:** Consume 1 token si coincide con la palabra reservada esperada.
- **Ejemplo:**
  ```python
  from gram.core.combinators import MatchKeyword

  match_if = MatchKeyword("if")
  match_return = MatchKeyword("return")
  ```

### `MatchGroup`
Valida que el token actual pertenezca a un grupo léxico (`WordGroup`) registrado en el Lexer (ej. modificadores, operadores lógicos, tipos de datos).

- **Firma:** `MatchGroup(group: str | WordGroup)`
- **Consumo:** Consume 1 token si pertenece al grupo especificado.
- **Ejemplo:**
  ```python
  from gram.core.combinators import MatchGroup

  match_type = MatchGroup("PRIMITIVE_TYPES")
  ```

### `MatchSymbol`
Valida que el token coincida con un símbolo o signo de puntuación puntual (ej. `;`, `:`, `,`).

- **Firma:** `MatchSymbol(symbol: str)`
- **Consumo:** Consume 1 token simbólico.
- **Ejemplo:**
  ```python
  from gram.core.combinators import MatchSymbol

  match_colon = MatchSymbol(":")
  ```

### `MatchSeqSymbol`
Valida secuencias ordenadas de símbolos que componen un operador multicarácter o delimitador compuesto (ej. `==`, `!=`, `->`, `=>`).

- **Firma:** `MatchSeqSymbol(*symbols: str)`
- **Consumo:** Consume la cantidad de tokens correspondiente a la secuencia si todos coinciden en orden exacto; realiza backtracking completo si alguno falla.
- **Ejemplo:**
  ```python
  from gram.core.combinators import MatchSeqSymbol

  match_arrow = MatchSeqSymbol("-", ">")
  ```

### `Literal`
Verifica que el valor literal del token (`token.value`) coincida exactamente con un valor escalar dado, independientemente del tipo de token.

- **Firma:** `Literal(value: Any)`
- **Consumo:** Consume 1 token. Si coincide, retorna un `LiteralNode` que contiene ese `TokenType`.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Literal

  match_null = Literal("null")
  match_zero = Literal(0)
  ```

### `Item`
Agrupa combinadores en una secuencia atómica. Si todos coinciden, retorna un `ItemNode` con los tokens resultantes; si uno falla, restaura el parser al inicio.

- **Firma:** `Item(*matchs: Combinator)`
- **Retorno:** `ItemNode`, una lista de `TokenType` coincidentes, o `None` si la secuencia falla.

---

## 2. Combinadores Nativos de Estructura y Flujo

### `Seq (Secuencia)`
Ejecuta una lista de combinadores en orden estricto contra el flujo de tokens. **Todos** los elementos deben coincidir. Si alguno falla, revierte atómicamente el estado del parser al punto de inicio.

- **Firma:** `Seq(*combinators: Combinator)`
- **Retorno:** `list[Any]` con los resultados individuales de cada combinador si la secuencia tuvo éxito; `None` si falló (en modo seguro).
- **Ejemplo:**
  ```python
  from gram.core.combinators import Seq, MatchKeyword, MatchToken
  from gram.core.lexer import Token

  # let <ident> = <number> ;
  var_decl = Seq(
      MatchKeyword("let"),
      MatchToken(Token.IDENT),
      MatchToken(Token.ASSIGN),
      MatchToken(Token.NUMBER),
      MatchToken(Token.SEMICOLON),
  )
  ```

### `Alt (Alternativa)`
Prueba una lista ordenada de combinadores alternativos. Evalúa cada rama de izquierda a derecha con backtracking atómico garantizado entre intentos. Retorna el resultado de la primera rama exitosa.

- **Firma:** `Alt(*combinators: Combinator)`
- **Retorno:** Resultado de la primera alternativa que coincida; `None` si ninguna coincide.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Alt, MatchToken
  from gram.core.lexer import Token

  literal_val = Alt(
      MatchToken(Token.NUMBER),
      MatchToken(Token.STRING),
      MatchToken(Token.IDENT),
  )
  ```

### `Opt (Opcional)`
Indica que un combinador es opcional (cero o una coincidencia). Si coincide, consume y retorna el resultado; si no coincide, revierte el cursor y retorna `None` sin producir un error sintáctico.

- **Firma:** `Opt(combinator: Combinator)`
- **Retorno:** Instancia de `OptResult(matched=True/False, value=...)`.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Seq, Opt, MatchToken
  from gram.core.lexer import Token

  # return <expr>?
  return_stmt = Seq(
      MatchToken(Token.RETURN),
      Opt(MatchToken(Token.NUMBER)),
  )
  ```

### `Many (Cero o Más)`
Consume repetidamente el combinador hijo tantas veces como sea posible ($0..N$). Se detiene cuando el combinador ya no coincide o se alcanza el final del archivo.

- **Firma:** `Many(combinator: Combinator)`
- **Retorno:** `list[Any]` con todas las coincidencias acumuladas (puede ser vacía `[]`).
- **Ejemplo:**
  ```python
  from gram.core.combinators import Many, MatchToken
  from gram.core.lexer import Token

  many_idents = Many(MatchToken(Token.IDENT))
  ```

### `Some (Uno o Más)`
Similar a `Many`, pero exige **al menos una coincidencia** exitosa ($1..N$). Si no coincide la primera vez, falla con backtracking.

- **Firma:** `Some(combinator: Combinator)`
- **Retorno:** `list[Any]` con al menos un elemento.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Some, MatchToken
  from gram.core.lexer import Token

  params = Some(MatchToken(Token.IDENT))
  ```

### `Separator / Sep (Separador)`
Analiza una serie de elementos separados por un delimitador repetitivo (ejemplo: argumentos separados por comas `a, b, c`).

- **Firma:** `Sep(item: Combinator, separator: Combinator, allow_trailing: bool = False)`
- **Retorno:** Instancia de `SeparatorResult` con los elementos analizados.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Sep, MatchToken
  from gram.core.lexer import Token

  # a, b, c
  arg_list = Sep(MatchToken(Token.IDENT), MatchToken(Token.COMMA))
  ```

### `Enclosed / Bracketed (Delimitados)`
Analiza contenido rodeado por delimitadores de apertura y cierre (paréntesis, corchetes, llaves, etc.).

- **Firma:** `Enclosed(open_comb: Combinator, body: Combinator, close_comb: Combinator)`
- **Ejemplo:**
  ```python
  from gram.core.combinators import Bracketed, MatchToken
  from gram.core.lexer import Token

  # ( expr )
  paren_expr = Bracketed(
      MatchToken(Token.LPAREN),
      MatchToken(Token.NUMBER),
      MatchToken(Token.RPAREN),
  )
  ```

### `Ref (Referencia Perezosa)`
Referencia diferida a otra regla sintáctica declarada en el catálogo o diccionario de gramática. Permite recursión directa e indirecta sin problemas de orden de definición.

- **Firma:** `Ref(rule: RuleItem | str, generate_node: bool = False, name: str | None = None)`
- **AST:** Por defecto no añade un bloque `RefNode`; conserva el resultado de la regla referenciada directamente bajo el nodo contenedor. Con `generate_node=True`, añade un `RefNode` alrededor de ese resultado; `name` permite asignarle un nombre visible.
- **Ejemplo:**
  ```python
  from gram.core.combinators import Ref, DECLARATION

  decl_ref = Ref(DECLARATION)
  named_decl_ref = Ref(DECLARATION, generate_node=True, name="DeclarationRef")
  ```

### `Tokenize`
Encapsula un combinador para que retorne únicamente la lista aplanada de tokens consumidos durante su evaluación, ideal para capturar bloques de texto crudo.

- **Firma:** `Tokenize(combinator: Combinator)`

---

## 3. Combinadores del Plugin `storage`

El plugin `storage` provee mecanismos de memoria y etiquetado sintáctico sin consumo destructivo de tokens.

### `Save`
Captura el token actual bajo el cursor y lo almacena en la pila `StorageStacK` bajo una clave dada **sin consumirlo**.

- **Firma:** `Save(key: str)`
- **Comportamiento:**
  - Guarda el token en `StorageStacK.save(key, token)`.
  - Rebobina el cursor una posición hacia atrás para que el token quede disponible para el combinador subsiguiente.
- **Ejemplo:**
  ```python
  from gram.plugins.source.storage import Save, StorageStacK
  from gram.core.combinators import Seq, MatchToken
  from gram.core.lexer import Token

  # Guarda el identificador en "last_id" y luego lo consume normalmente
  regla = Seq(Save("last_id"), MatchToken(Token.IDENT))
  ```

### `Load`
Recupera el último token almacenado en `StorageStacK` bajo la clave especificada e inyecta su valor en el flujo sin consumos adicionales.

- **Firma:** `Load(key: str)`
- **Comportamiento:** Retorna `StorageStacK.get(key)` si existe; lanza `ParserError` si la clave no tiene tokens registrados.
- **Ejemplo:**
  ```python
  from gram.plugins.source.storage import Load

  cargar_id = Load("last_id")
  ```

### `Tag`
Añade una etiqueta semántica identificadora (`tag.<nombre>`) al AST sin consumir tokens reales del código fuente.

- **Firma:** `Tag(name: str)`
- **Comportamiento:** Inyecta un `TokenType(Token.IDENT, f"tag.{name}")` en los resultados del parser restaurando el cursor.
- **Ejemplo:**
  ```python
  from gram.plugins.source.storage import Tag
  from gram.core.combinators import Seq, MatchToken
  from gram.core.lexer import Token

  marcar_tipo = Seq(Tag("tipo_variable"), MatchToken(Token.IDENT))
  ```

---

## 4. Combinadores del Plugin `expressions`

El plugin `expressions` provee parsing y evaluación completa de expresiones matemáticas y lógicas, evitando construir analizadores aritméticos manualmente.

### `ChainL (Asociatividad Izquierda)`
Analiza secuencias de operadores asociativos por la izquierda:
$$\text{a} + \text{b} + \text{c} \longrightarrow ((\text{a} + \text{b}) + \text{c})$$

- **Firma:** `ChainL(operand: Combinator, operator: Combinator)`
- **Ejemplo:**
  ```python
  from gram.plugins.source.expressions import ChainL
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  # 1 + 2 + 3 -> ((1 + 2) + 3)
  suma = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.PLUS))
  ```

### `ChainR (Asociatividad Derecha)`
Analiza secuencias de operadores asociativos por la derecha (como la potenciación o la asignación encadenada):
$$\text{a} ** \text{b} ** \text{c} \longrightarrow (\text{a} ** (\text{b} ** \text{c}))$$

- **Firma:** `ChainR(operand: Combinator, operator: Combinator)`
- **Ejemplo:**
  ```python
  from gram.plugins.source.expressions import ChainR
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  # 2 ** 3 ** 2 -> (2 ** (3 ** 2))
  potencia = ChainR(MatchToken(Token.NUMBER), MatchToken(Token.POW))
  ```

### `ExpressionBuilder`
Constructor declarativo fluido que permite definir niveles de precedencia sin recursión izquierda infinita.

- **Firma:** `ExpressionBuilder()`
- **Métodos:**
  - `.atom(combinator)`: Define la unidad base (números, identificadores, expresiones entre paréntesis).
  - `.infix_left(operator_comb)`: Añade un nivel de operadores con asociatividad izquierda.
  - `.infix_right(operator_comb)`: Añade un nivel de operadores con asociatividad derecha.
  - `.prefix(operator_comb)`: Añade operadores unarios prefijos.
  - `.build()`: Compila el combinador resultante.
- **Ejemplo:**
  ```python
  from gram.plugins.source.expressions import ExpressionBuilder
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  expr = (
      ExpressionBuilder()
      .atom(MatchToken(Token.NUMBER))
      .infix_left(MatchToken(Token.STAR) | MatchToken(Token.SLASH))
      .infix_left(MatchToken(Token.PLUS) | MatchToken(Token.MINUS))
      .build()
  )
  ```

### `ArithmeticExpr`
Combinador integral pre-configurado que incluye aritmética completa (`+`, `-`, `*`, `/`, `//`, `%`, `**`), operadores unarios y anidamiento arbitrario con paréntesis `( )`.

- **Firma:** `ArithmeticExpr()`
- **Ejemplo:**
  ```python
  from gram.plugins.source.expressions import ArithmeticExpr

  parser_expr = ArithmeticExpr()
  ```

### `IsDigit`
Valida que el token actual sea un dígito numérico válido.

### `MathBinaryOp`, `MathUnaryOp`, `MathGroup`
Nodos y combinadores internos de operaciones matemáticas para el árbol de sintaxis abstracta.

---

## 5. Combinadores del Plugin `GRAM_ESSENCIAL_PACK`

`GRAM_ESSENCIAL_PACK` provee primitivas avanzadas y abstracciones para acelerar la creación de extensiones en Gram.

### `SimpleCombinator`
Clase base simplificada para crear combinadores basados en predicados sobre tokens individuales sin manipular cursores ni lidiar con pilas de llamadas.

- **Métodos a implementar:**
  - `evaluate(self, current: TokenType) -> bool`: Retorna `True` si el token cumple la condición. Gram consume automáticamente el token si retorna `True`.
  - `get_error(self, current: TokenType) -> tuple[CodeError, str]`: Genera el código y mensaje de error en caso de fallo fuera de contextos alternativos.
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import SimpleCombinator
  from gram.core.lexer import Token, TokenType

  class NumeroPar(SimpleCombinator):
      def evaluate(self, current: TokenType) -> bool:
          if current.token != Token.NUMBER:
              return False
          try:
              return int(current.value) % 2 == 0
          except (ValueError, TypeError):
              return False
  ```

### `If (Condicional y Lookahead)`
Evalúa una secuencia de condiciones y bifurca la ejecución entre una rama afirmativa (`ok`) y una alternativa (`fail`), garantizando backtracking atómico.

- **Firma:** `If(conditions: list[Combinator], ok=None, fail=None, *, restore: bool = False)`
- **Modos:**
  - `restore=False` (por defecto): Si las condiciones se cumplen, las consume y continúa ejecutando `ok` hacia adelante.
  - `restore=True` (Modo Lookahead Puro): Si las condiciones se cumplen, restaura el cursor al inicio y ejecuta `ok` desde el primer token.
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import If
  from gram.core.combinators import MatchToken, MatchKeyword
  from gram.core.lexer import Token

  # Si sigue un número, parsea suma; si no, parsea asignación
  condicional = If(
      conditions=[MatchToken(Token.NUMBER)],
      ok=MatchToken(Token.PLUS),
      fail=MatchToken(Token.ASSIGN),
  )
  ```

### `ErrorCombinator`
Inspecciona y captura errores acumulados en `StackError` durante el análisis previo.

- **Firma:** `ErrorCombinator(length: int = 1)`
- **Comportamiento:** Si hay errores registrados, los extrae y devuelve. Si no hay errores, falla permitiendo que reglas alternativas tomen el control.
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import ErrorCombinator

  captura = ErrorCombinator(length=3)
  ```

### `Req (Requerimientos Fluidos)`
Combinador fluido para requerir, validar y transformar tokens mediante encadenamiento de métodos legibles.

- **Firma:** `Req(target_token: str)`
- **Métodos de Validación:**
  - `.is_lower()` / `.is_upper()`: Mayúsculas / minúsculas.
  - `.is_snake_case()` / `.is_camel_case()`: Convenciones de nombres.
  - `.startswith(prefix)` / `.endswith(suffix)`: Prefijos y sufijos.
  - `.length(n)` / `.min(n)` / `.max(n)`: Límites de tamaño o valor.
  - `.equal(val)` / `.unequal(val)`: Igualdad estricta.
  - `.contains(*items)` / `.excludes(*items)`: Subcadenas requeridas o prohibidas.
- **Métodos de Transformación:**
  - `.apply_lower()` / `.apply_upper()` / `.apply_camel()`: Mutaciones de formato.
  - `.transform(callable)`: Conversión de tipo (ej. `int`, `float`).
  - `.replace(old, new)` / `.addl(prefix)` / `.addr(suffix)`: Modificaciones de texto.
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import Req

  id_valido = (
      Req("IDENT")
      .is_lower()
      .length(5)
      .startswith("usr_")
  )
  ```

### `Skip`
Señal de terminación temprana y exitosa para secuencias `Seq`. Cuando se alcanza, interrumpe los siguientes combinadores sin error y da por completada la secuencia.

- **Firma:** `Skip()`

### `Peek (Lookahead Positivo)`
Verifica que un combinador coincida a partir del token actual, pero **restaura inmediatamente el cursor** a la posición inicial sin consumir ningún token (ancho cero).

- **Firma:** `Peek(combinator: Combinator)`
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import Peek
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  mira_si_viene_ident = Peek(MatchToken(Token.IDENT))
  ```

### `Not (Lookahead Negativo)`
Tiene éxito únicamente si el combinador interno **NO coincide** con el token actual. Nunca consume tokens (ancho cero).

- **Firma:** `Not(combinator: Combinator)`
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import Not
  from gram.core.combinators import MatchKeyword

  no_es_return = Not(MatchKeyword("return"))
  ```

### `Until (Consumo hasta Objetivo)`
Consume tokens secuencialmente en bucle hasta que el combinador `target` coincide.

- **Firma:** `Until(target: Combinator, consume_target: bool = False, max_tokens: int | None = None)`
- **Ejemplo:**
  ```python
  from gram.plugins.source.GRAM_ESSENCIAL_PACK import Until
  from gram.core.combinators import MatchToken
  from gram.core.lexer import Token

  # Consume todo hasta encontrar punto y coma
  hasta_punto_coma = Until(MatchToken(Token.SEMICOLON), consume_target=True)
  ```
