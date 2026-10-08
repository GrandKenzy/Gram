"""
Catálogo de Tokens y Tipos Léxicos (`gram.core.lexer.tokens`).
==============================================================
Define la enumeración formal `Token`, la clase contenedora de emisión `TokenType`,
la clase para tokens dinámicos `CustomToken`, y el mapeo bidireccional unificado
de operadores y símbolos (`MAP_SYMBOLS`).

Arquitectura del Analizador Léxico:
-----------------------------------
- `Token`: Catálogo inmutable de todos los tipos léxicos predefinidos reconocidos por Gram.
- `CustomToken`: Tokens extendidos en tiempo de ejecución (por plugins o extensiones).
- `TokenType`: Unidad atómica (lexema) generada por el lexer con metadatos posicionales (línea, columna, valor).
- `MAP_SYMBOLS`: Diccionario bidireccional optimizado para mapear operadores/símbolos con sus respectivos Tokens.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Any, ClassVar

from gram import errors
from gram.utilities.error import Error, LexerError


class Token(Enum):
    """
    ES:
        Enumeración exhaustiva de los tipos de token reconocidos en el framework Gram.
        Se organiza en 11 categorías lógicas para facilitar el análisis sintáctico.

    EN:
        Exhaustive enumeration of token types recognized within the Gram framework.
        Organized into 11 logical categories for structured parsing.
    """

    # ==============================================================
    # 1. ESTRUCTURA Y FLUJO
    # ==============================================================
    EOF = 0
    NEWLINE = auto()
    IDENT = auto()
    INDENT = auto()
    DEDENT = auto()
    COMMENT = auto()
    KEYWORD = auto()

    # ==============================================================
    # 2. LITERALES
    # ==============================================================
    STRING = auto()
    CHAR = auto()
    NUMBER = auto()
    BOOL = auto()
    NULL = auto()
    DOCSTRING = auto()

    # ==============================================================
    # 3. OPERADORES ARITMÉTICOS
    # ==============================================================
    PLUS = auto()                 # +
    MINUS = auto()                # -
    STAR = auto()                 # *
    SLASH = auto()                # /
    PERCENT = auto()              # %
    POW = auto()                  # **
    FLOOR_DIV = auto()            # //
    INCREMENT = auto()            # ++
    DECREMENT = auto()            # --

    # ==============================================================
    # 4. OPERADORES DE ASIGNACIÓN
    # ==============================================================
    ASSIGN = auto()               # =
    PLUS_ASSIGN = auto()          # +=
    MINUS_ASSIGN = auto()         # -=
    STAR_ASSIGN = auto()          # *=
    SLASH_ASSIGN = auto()         # /=
    PERCENT_ASSIGN = auto()       # %=
    POW_ASSIGN = auto()           # **=
    FLOOR_DIV_ASSIGN = auto()     # //=
    AND_ASSIGN = auto()           # &=
    OR_ASSIGN = auto()            # |=
    XOR_ASSIGN = auto()           # ^=
    SHL_ASSIGN = auto()           # <<=
    SHR_ASSIGN = auto()           # >>=
    WALRUS = auto()               # :=

    # ==============================================================
    # 5. OPERADORES DE COMPARACIÓN
    # ==============================================================
    EQUAL = auto()                # ==
    NOT_EQUAL = auto()            # !=
    LESS = auto()                 # <
    GREATER = auto()              # >
    LESS_EQUAL = auto()           # <=
    GREATER_EQUAL = auto()        # >=

    # ==============================================================
    # 6. OPERADORES LÓGICOS Y BITWISE
    # ==============================================================
    NOT = auto()                  # ~
    NOT_LOGIC = auto()            # !
    AND_LOGIC = auto()            # &&
    OR_LOGIC = auto()             # ||
    AND = auto()                  # &
    OR = auto()                   # |
    XOR = auto()                  # ^
    SHL = auto()                  # <<
    SHR = auto()                  # >>

    # ==============================================================
    # 7. DELIMITADORES
    # ==============================================================
    LPAREN = auto()               # (
    RPAREN = auto()               # )
    LBRACKET = auto()             # [
    RBRACKET = auto()             # ]
    LBRACE = auto()               # {
    RBRACE = auto()               # }

    # ==============================================================
    # 8. PUNTUACIÓN Y SÍMBOLOS ESPECIALES
    # ==============================================================
    COMMA = auto()                # ,
    DOT = auto()                  # .
    COLON = auto()                # :
    SEMICOLON = auto()            # ;
    AT = auto()                   # @
    HASH = auto()                 # #
    DOLLAR = auto()               # $
    QUESTION = auto()             # ?
    QUESTION_ASSIGN = auto()      # ?=
    EXCLAMATION = auto()          # !
    BACKSLASH = auto()            # \
    UNDERSCORE = auto()           # _

    # ==============================================================
    # 9. FLECHAS
    # ==============================================================
    ARROW = auto()                # ->
    FAT_ARROW = auto()            # =>
    LEFT_ARROW = auto()           # <-
    DOUBLE_ARROW = auto()         # <->

    # ==============================================================
    # 10. UNICODE (LÓGICA Y MATEMÁTICA)
    # ==============================================================
    LOGIC_AND = auto()            # ∧
    LOGIC_OR = auto()             # ∨
    LOGIC_NOT = auto()            # ¬
    SQRT = auto()                 # √
    INFINITY = auto()             # ∞
    DEGREE = auto()               # °
    MIDDLE_DOT = auto()           # ·
    BULLET = auto()               # •
    SECTION = auto()              # §
    THREE_DOTS = auto()           # ...

    # ==============================================================
    # 11. ESTADOS ESPECIALES
    # ==============================================================
    ERROR = auto()
    UNKNOWN = auto()
    EMPTY_LINE = auto()

    @classmethod
    def from_string(cls, name: str) -> Token | None:
        """
        ES: Obtiene un Token a partir de su nombre textual (insensible a mayúsculas).
        EN: Retrieves a Token by its string name (case-insensitive).
        """
        if not isinstance(name, str):
            return None
        return cls.__members__.get(name.strip().upper())

    @classmethod
    def from_code(cls, code: int) -> Token | None:
        """
        ES: Obtiene un Token a partir de su valor numérico ordinal.
        EN: Retrieves a Token by its integer ordinal code.
        """
        try:
            return cls(code)
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_tokens(cls) -> tuple[Token, ...]:
        """
        ES: Retorna una tupla inmutable con todos los tokens definidos en la enumeración.
        EN: Returns an immutable tuple containing all defined tokens.
        """
        return tuple(cls)


class CustomToken:
    """
    ES:
        Representa un tipo de token definido dinámicamente en tiempo de ejecución.
        Permite a plugins y extensiones de lenguaje añadir tokens propios sin alterar
        la enumeración inmutable `Token`.

    EN:
        Represents a dynamically defined token type at runtime.
        Enables language plugins and extensions to add custom tokens without mutating
        the immutable `Token` enumeration.
    """

    name: str
    value: Any
    description: str

    def __init__(self, name: str = 'CustomToken', value: Any = None, description: str = '') -> None:
        """
        ES: Inicializa el token dinámico con un nombre identificativo, un valor opcional y documentación.
        EN: Initializes the dynamic token with an identifier name, optional value, and description.
        """
        self.name = name
        self.value = value if value is not None else name
        self.description = description

    def __repr__(self) -> str:
        return f"Token.{self.name}"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CustomToken):
            return self.name == other.name
        if isinstance(other, Token):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other or other == 'CustomToken'
        return False

    def __hash__(self) -> int:
        return hash(self.name)


class TokenType:
    """
    ES:
        Instancia concreta de un lexema emitido por el analizador léxico.
        Encapsula el tipo formal (`Token` o `CustomToken`), el valor textual capturado
        en el código fuente y las coordenadas de posición (línea y columna) para diagnósticos.

    EN:
        Concrete instance of a lexeme emitted by the lexical analyzer.
        Encapsulates the formal type (`Token` or `CustomToken`), the captured textual
        value from the source code, and positional coordinates (line and column) for diagnostics.
    """

    token: Token | CustomToken
    value: Any
    line: int
    col: int
    description: str

    def __init__(
        self,
        token: Token | CustomToken,
        value: Any = None,
        line: int = 1,
        col: int = 0,
        description: str = "",
    ) -> None:
        """
        ES:
            Inicializa un token concreto con su tipo, valor y coordenadas de origen.
        EN:
            Initializes a concrete token with its type, value, and source coordinates.
        """
        self.token = token
        self.value = value
        self.line = line if line >= 1 else 1
        self.col = col if col >= 0 else 0
        self.description = description

    def formatter(self, msg: str) -> str:
        """
        ES:
            Interpola variables contextuales en cadenas de diagnóstico o precaución.
            Sustituye marcadores estándar:
                - `$name`: Nombre identificador del tipo de token.
                - `$value` / `$content`: Contenido o valor capturado del token.
                - `$line`: Línea de origen en el código fuente.
                - `$col`: Columna de origen en el código fuente.
                - `$symbol`: Símbolo asociado si existe en `MAP_SYMBOLS`.

        EN:
            Interpolates contextual variables into diagnostic or caution strings.
        """
        token_name: str = self.token.name
        token_val: str = str(self.token.value)
        content_val: str = str(self.value) if self.value is not None else token_name
        symbol_val: str = MAP_SYMBOLS.get(self.token, "")

        return (
            msg
            .replace("$name", token_name)
            .replace("$tvalue", token_val)
            .replace("$content", content_val)
            .replace("$value", content_val)
            .replace("$line", str(self.line))
            .replace("$len", str(self.line))
            .replace("$col", str(self.col))
            .replace("$symbol", symbol_val)
            .replace("$sym", symbol_val)
        )

    # Alias para compatibilidad hacia atrás
    _formatter = formatter

    def raise_error(
        self,
        title: str,
        *caution: str,
        code: Any = None,
        exit: bool = False,
    ) -> None:
        """
        ES:
            Emite una excepción estructurada `LexerError` utilizando el estándar formal OSGDC.
            Interpola automáticamente las coordenadas y el contexto del token en el mensaje.

        EN:
            Raises a structured `LexerError` using Gram's OSGDC formal standard.
            Automatically interpolates token coordinates and context into the message.

        Args:
            title: Título descriptivo del error léxico.
            *caution: Párrafos explicativos o recomendaciones de resolución.
            code: Código CodeError formal (por defecto `errors.LEXER_UNEXPECTED_CHARACTER`).
            exit: Si es True, detiene la ejecución del intérprete.
        """
        err_code = code if code is not None else errors.LEXER_UNEXPECTED_CHARACTER
        msg = f"{title} (Token: {self.token}, Valor: '{self.value}') en línea {self.line}, columna {self.col}"
        formatted_caution = tuple(self.formatter(c) for c in caution)

        LexerError(msg, err_code, *formatted_caution).raise_error(exit=exit)

    def __repr__(self) -> str:
        return f"TokenType(token={self.token}, value={self.value!r}, line={self.line}, col={self.col})"

    def __str__(self) -> str:
        if self.value is not None:
            return str(self.value)
        return self.token.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TokenType):
            return self.token == other.token and self.value == other.value
        if isinstance(other, (Token, CustomToken)):
            return self.token == other
        if isinstance(other, str):
            token_name = self.token.name
            return token_name == other or str(self.value) == other
        return False

    def __hash__(self) -> int:
        return hash((self.token, str(self.value), self.line, self.col))


class _MapSymbolsDict(dict[str, Token]):
    """
    ES:
        Diccionario bidireccional optimizado para el mapeo de operadores y símbolos.
        Permite consulta en tiempo O(1) tanto por símbolo textual (`'+' -> Token.PLUS`),
        por instancia de enumeración (`Token.PLUS -> '+'`) y por nombre (`'PLUS' -> '+'`).

    EN:
        Bidirectional dictionary optimized for operators and symbols mapping.
        Supports O(1) lookup by textual symbol (`'+' -> Token.PLUS`),
        by enum instance (`Token.PLUS -> '+'`), and by name (`'PLUS' -> '+'`).
    """

    _rev: dict[Any, str]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rev = {}
        for sym, tok in self.items():
            self._rev[tok] = sym
            self._rev[tok.name] = sym

    def __getitem__(self, key: Any) -> Any:
        if key in self:
            return super().__getitem__(key)
        if key in self._rev:
            return self._rev[key]
        raise KeyError(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self:
            return super().get(key, default)
        if key in self._rev:
            return self._rev[key]
        return default

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or key in self._rev


# ==============================================================================
# TABLA DE SÍMBOLOS Y OPERADORES UNIFICADA
# ==============================================================================

MAP_SYMBOLS: _MapSymbolsDict = _MapSymbolsDict({
    # Operadores Aritméticos
    '+': Token.PLUS,
    '-': Token.MINUS,
    '*': Token.STAR,
    '/': Token.SLASH,
    '%': Token.PERCENT,
    '**': Token.POW,
    '//': Token.FLOOR_DIV,
    '++': Token.INCREMENT,
    '--': Token.DECREMENT,

    # Operadores de Asignación
    '=': Token.ASSIGN,
    '+=': Token.PLUS_ASSIGN,
    '-=': Token.MINUS_ASSIGN,
    '*=': Token.STAR_ASSIGN,
    '/=': Token.SLASH_ASSIGN,
    '%=': Token.PERCENT_ASSIGN,
    '**=': Token.POW_ASSIGN,
    '//=': Token.FLOOR_DIV_ASSIGN,
    '&=': Token.AND_ASSIGN,
    '|=': Token.OR_ASSIGN,
    '^=': Token.XOR_ASSIGN,
    '<<=': Token.SHL_ASSIGN,
    '>>=': Token.SHR_ASSIGN,
    ':=': Token.WALRUS,

    # Operadores de Comparación
    '==': Token.EQUAL,
    '!=': Token.NOT_EQUAL,
    '<': Token.LESS,
    '>': Token.GREATER,
    '<=': Token.LESS_EQUAL,
    '>=': Token.GREATER_EQUAL,

    # Operadores Lógicos y Bitwise
    '~': Token.NOT,
    '&&': Token.AND_LOGIC,
    '||': Token.OR_LOGIC,
    '&': Token.AND,
    '|': Token.OR,
    '^': Token.XOR,
    '<<': Token.SHL,
    '>>': Token.SHR,

    # Delimitadores
    '(': Token.LPAREN,
    ')': Token.RPAREN,
    '[': Token.LBRACKET,
    ']': Token.RBRACKET,
    '{': Token.LBRACE,
    '}': Token.RBRACE,

    # Puntuación y Caracteres Especiales
    ',': Token.COMMA,
    '.': Token.DOT,
    ':': Token.COLON,
    ';': Token.SEMICOLON,
    '@': Token.AT,
    '#': Token.HASH,
    '$': Token.DOLLAR,
    '?': Token.QUESTION,
    '?=': Token.QUESTION_ASSIGN,
    '!': Token.EXCLAMATION,
    '\\': Token.BACKSLASH,
    '_': Token.UNDERSCORE,

    # Flechas
    '->': Token.ARROW,
    '=>': Token.FAT_ARROW,
    '<-': Token.LEFT_ARROW,
    '<->': Token.DOUBLE_ARROW,

    # Unicode Lógica
    '∧': Token.LOGIC_AND,
    '∨': Token.LOGIC_OR,
    '¬': Token.LOGIC_NOT,

    # Unicode Matemática
    '√': Token.SQRT,
    '∞': Token.INFINITY,
    '°': Token.DEGREE,

    # Otros Símbolos
    '·': Token.MIDDLE_DOT,
    '•': Token.BULLET,
    '§': Token.SECTION,
    '...': Token.THREE_DOTS,
})


def get_tokens() -> tuple[Token, ...]:
    """
    ES: Retorna una tupla inmutable con todos los tokens reconocidos por Gram.
    EN: Returns an immutable tuple with all recognized tokens in Gram.
    """
    return Token.get_tokens()


def get_sorted_symbols() -> list[str]:
    """
    ES:
        Retorna todos los operadores y símbolos registrados en `MAP_SYMBOLS`,
        ordenados en longitud descendente. Garantiza la regla de máxima coincidencia
        (maximal munch) para evitar que operadores compuestos (ej. `==`, `++`, `**`)
        sean consumidos erróneamente como símbolos simples individuales (`=`, `+`, `*`).

    EN:
        Returns all operators and symbols registered in `MAP_SYMBOLS` sorted
        by descending length. Ensures the maximal munch rule during tokenization.
    """
    return sorted(MAP_SYMBOLS.keys(), key=len, reverse=True)


__all__ = [
    'Token',
    'CustomToken',
    'TokenType',
    'MAP_SYMBOLS',
    'get_tokens',
    'get_sorted_symbols',
]