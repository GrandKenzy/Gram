# Arquitectura y Manejo de Estado

El motor léxico principal en `gram.core.lexer` está estructurado sobre un diseño limpio de dos clases:

1. **`LexerState` (`gram.core.lexer.control`):** El gestor de estado fundamental. Hereda de `Diagnostics` y gestiona las líneas fuente, las coordenadas del cursor físico (`line` y `col`), la pila de indentación semántica (`indents`), el colector de comentarios (`comments`) y la resolución dinámica de configuraciones.
2. **`Lexer` (`gram.core.lexer.core`):** La fachada de alto nivel. Hereda de `LexerState` e implementa el bucle de escaneo principal `process()`, la validación de condiciones previas del catálogo (`check_state()`) y métodos de fábrica (`tokenize()`, `stream()`).

---

## 1. Carga de Código Fuente (`_load_source`)

`Lexer` acepta código fuente en tres formatos distintos:

```python
from pathlib import Path
from gram.core.lexer import Lexer, words

# Siempre asegúrate de registrar al menos una palabra clave antes de ejecutar el lexer
words.add_keyword("fn", allow_override=True)

# 1. Desde una cadena directa en memoria
lexer_str = Lexer("fn principal() { return 0; }")

# 2. Desde una secuencia o lista de líneas
lexer_lines = Lexer(["fn calcular(x) {", "    return x * 2;", "}"])

# 3. Desde un objeto pathlib.Path en disco
source_path = Path("ejemplos/script.gram")
lexer_archivo = Lexer(source_path)
```

### Semántica de Carga

| Tipo de Entrada | Detalles de Procesamiento | Manejo de Errores |
| :--- | :--- | :--- |
| `str` | Se divide en líneas individuales mediante el método nativo `.splitlines()` de Python. | Ninguno. Una cadena vacía produce una lista vacía de líneas que resulta en un único `Token.EOF`. |
| `Sequence[str]` | A cada elemento de la secuencia se le eliminan los saltos de línea finales `\r` y `\n` mediante `.rstrip('\r\n')`. | Conserva espacios en blanco iniciales y líneas vacías para el cálculo de indentación. |
| `Path` | Valida que el archivo exista en disco. Lee el archivo con codificación UTF-8 y lo divide en líneas. Configura además `Format.FileTar` para trazas de error. | Si el archivo no existe, registra un fallo en diagnósticos y lanza `LexerError` (`LEXER_FILE_NOT_FOUND`). |

---

## 2. Coordenadas del Cursor y Primitivas de Navegación

`LexerState` mantiene punteros de posición para líneas y caracteres:

- **`self.line` (`int`):** Índice de línea actual (base 0 internamente). Al emitirse dentro de un `TokenType` o al reportarse en errores de usuario, se presenta en **base 1** (`self.line + 1`).
- **`self.col` (`int`):** Desplazamiento de columna del carácter actual en la línea activa (índice crudo en base 0).
- **`self.source` (`list[str]`):** Lista de cadenas con las líneas físicas cargadas.

### API de Navegación

| Método / Propiedad | Tipo de Retorno | Descripción |
| :--- | :--- | :--- |
| `lexer.currline` | `str` | Retorna `self.source[self.line]` si `self.line` está en rango; en caso contrario, retorna `""`. |
| `lexer.has_lines()` | `bool` | Retorna `True` si quedan líneas pendientes (`self.line < len(self.source)`). |
| `lexer.is_empty()` | `bool` | Retorna `True` si `self.currline.strip() == ""`. |
| `lexer.peek(offset=0)` | `str` | Inspecciona el carácter en `self.col + offset` de la línea actual sin desplazar el cursor. Retorna `""` si la columna queda fuera de rango. |
| `lexer.advance(steps=1)` | `str` | Retorna el carácter bajo el cursor actual (`peek()`) e incrementa `self.col` en `steps`. |

```python
# Ejemplo de inspección manual durante un escaneo personalizado
lexer = Lexer("alpha := 10")
print(lexer.currline)      # "alpha := 10"
print(lexer.peek())          # "a"
print(lexer.peek(1))         # "l"
caracter = lexer.advance(5)  # Consume "alpha", retorna "a"
print(lexer.col)             # 5
print(lexer.peek())          # " "
```

---

## 3. Configuración Dinámica y Enlace de Catálogos

Las instancias de `LexerState` pueden ejecutarse de manera global (leyendo de `gram.config` y del catálogo global `words.MAP_KEYWORDS`) o encapsuladas dentro de una instancia de `Session`. `LexerState` abstrae esta dualidad mediante métodos de acceso uniformes:

```python
# Patrón de resolución interna en LexerState
def get_config(self, name: str, default=None):
    if self.session is not None:
        return self.session.config.get(name, getattr(config, name, default))
    return getattr(config, name, default)

def get_keyword(self, name: str):
    if self.session is not None:
        return self.session.get_keyword(name)
    from gram.core.lexer import words
    return words.get_keyword(name)

def get_symbols(self):
    if self.session is not None:
        return self.session.symbols
    return tokens.MAP_SYMBOLS
```

Esto garantiza que un lexer configurado dentro de una sesión nunca contaminará palabras clave, símbolos o banderas de configuración hacia el estado global u otros hilos de ejecución.

---

## 4. Validación de Precondiciones: `check_state()`

Antes de iniciar el bucle de escaneo léxico, Gram ejecuta `check_state(self.session)`.

```python
def check_state(session=None) -> int:
    count = session.keyword_count() if session is not None else words.count_keywords()
    if count == 0:
        errors.LexerError(
            "EmptyKeywords",
            errors.LEXER_EMPTY_KEYWORDS,
            "No se encontró ninguna palabra clave registrada.",
            "Registre al menos una palabra clave mediante words.add_keyword() antes de ejecutar el Lexer.",
        ).raise_error()
    return count
```

> [!IMPORTANT]
> Gram exige al menos una palabra clave registrada antes de ejecutar el análisis léxico. Si se llama a `Lexer(source).process()` con un catálogo vacío, se lanza inmediatamente un `LexerError` con código `LEXER_EMPTY_KEYWORDS`.
> Si tu DSL no posee aún palabras clave reservadas, registra una palabra comodín temporal:
> ```python
> words.add_keyword("dummy", allow_override=True)
> ```

---

## 5. El Bucle Principal de Escaneo (`process()`)

Invocar `Lexer.process()` ejecuta la tubería de análisis en una sola pasada:

```python
def process(self) -> list[TokenType]:
```

### Diagrama de Flujo de Ejecución

```
                 Llamada a process()
                        │
                        ▼
            check_state(self.session)
                        │
                        ▼
         Inicializar tokens_list: list[TokenType]
                        │
         ┌──────────────┴──────────────┐
         ▼                             │
  while self.has_lines():              │
         │                             │
    ¿Línea vacía? ───► SÍ ───► Emitir NEWLINE (si no se ignoran)
         │                     Avanzar línea, reset col = 0
         ▼ NO                          │
    ¿Sólo comentario? ──► SÍ ──► Guardar comentario (si está habilitado)
         │                       Avanzar línea, reset col = 0
         ▼ NO                    (NO modifica la pila indents)
    1. process_indent() ──► Agregar tokens INDENT / DEDENT
         │
    2. while self.col < len(currline):
         │
         ├─► char en " \r\t" ──► advance()
         ├─► multiline_match() ──► process_multiline()
         ├─► is_comment_start() ──► process_comment()
         └─► visitors.visit(self, char) ──► tokens_list.append(token)
         │
    3. Emitir NEWLINE (si LEXER_IGNORE_NEWLINES es False)
       Avanzar línea, reset col = 0
         │
         └──────────────┬──────────────┘
                        │
         (Fin de todas las líneas)
                        ▼
    4. Desenrollar indentación pendiente:
       while len(self.indents) > 1:
           emitir Token.DEDENT
                        │
                        ▼
    5. Agregar token terminal Token.EOF
                        │
                        ▼
             return tokens_list
```

### Desglose Paso a Paso

1. **Aserción Previa:** Ejecuta `check_state()`. Si no se detectan keywords registradas, la ejecución se detiene de inmediato.
2. **Enmarcado de Diagnósticos:** Si `LEXER_ADD_INFO` está activo, crea y anida un nodo de telemetría `"LexingProcess"` en la pila de `Diagnostics`.
3. **Comprobación de Líneas Vacías:** Si `self.currline.strip() == ""`:
   - Si `LEXER_IGNORE_EMPTY_LINES=False` y `LEXER_IGNORE_NEWLINES=False`, agrega un `TokenType(Token.NEWLINE, None, line, 0)`.
   - Salta inmediatamente a la siguiente línea (`self.line += 1`, `self.col = 0`) sin alterar los niveles de indentación.
4. **Líneas Puras de Comentarios:** Si una línea sólo contiene espacios seguidos de un marcador de comentario unilínea, el comentario es extraído, almacenado en `self.comments` si corresponde, y la línea avanza. **Las líneas de sólo comentarios nunca alteran la pila de indentación**.
5. **Cálculo de Indentación:** Llama a `self.process_indent()`. Los espacios y tabuladores iniciales se convierten a un ancho visual de columna. Si el nivel crece, se emite `Token.INDENT`; si decrece, se emite uno o más `Token.DEDENT`.
6. **Escaneo de Caracteres:** El bucle interno procesa de izquierda a derecha la cadena `self.currline`:
   - Los espacios en blanco en línea (`' '`, `'\t'`, `'\r'`) se avanzan e ignoran.
   - Los delimitadores multilínea registrados (`"""`, `'''` o personalizados vía `add_multline`) tienen máxima prioridad y pueden consumir caracteres a través de múltiples líneas físicas.
   - Los comentarios unilínea (`#`, `//`) o de bloque (`/*`) consumen el contenido restante y continúan o rompen la línea física.
   - Cualquier otro carácter se delega al despachador `visitors.visit(self, char)`.
7. **Terminación de Línea:** Si `LEXER_IGNORE_NEWLINES=False`, se agrega un `TokenType(Token.NEWLINE, None, line, col)` antes de pasar a la siguiente línea.
8. **Desenrollado de Indentación al Final (EOF):** Una vez procesadas todas las líneas, cualquier bloque de indentación que permanezca abierto en la pila (`len(self.indents) > 1`) se desapila, emitiendo los tokens `Token.DEDENT` de cierre correspondientes.
9. **Centinela Final EOF:** Emite siempre `TokenType(Token.EOF, None, line, col)` como último token garantizado de la secuencia.

---

## 6. Métodos Auxiliares y Fábricas

Además de `process()`, `Lexer` proporciona dos utilidades de alto nivel:

### `tokenize(source, logfile=None) -> list[TokenType]`
Crea una nueva instancia de `Lexer` compartiendo la sesión y configuración activas, tokenizando `source` sin alterar el estado del objeto lexer actual:

```python
lexer = Lexer("fn primero()", session=mi_sesion)
tokens1 = lexer.process()

# Tokeniza otra fuente usando exactamente la misma configuración de sesión:
tokens2 = lexer.tokenize("fn segundo()")
```

### `stream() -> TokenStream`
Ejecuta `process()` y envuelve la lista resultante de tokens directamente en una instancia navegable de `TokenStream`:

```python
from gram.core.lexer import Lexer, TokenStream

stream: TokenStream = Lexer("let x = 42;").stream()
print(stream.current())  # TokenType(token=Token.KEYWORD, value='let', line=1, col=0)
```
