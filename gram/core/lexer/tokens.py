"""
Lexical Token Catalog and Types (`gram.core.lexer.tokens`).
===========================================================
Defines the formal `Token` enumeration, the `TokenType` lexeme container,
the dynamic `CustomToken` class for runtime extensions, and the bidirectional
`MAP_SYMBOLS` operator/delimiter lookup table.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Any

from gram import errors


class Token(Enum):
    """
    Exhaustive enumeration of token types recognized within the Gram framework,
    organized into 11 logical categories for structured syntactic analysis.
    """

    # ==============================================================
    # 1. STRUCTURE AND FLOW
    # ==============================================================
    EOF = 0
    NEWLINE = auto()
    IDENT = auto()
    INDENT = auto()
    DEDENT = auto()
    COMMENT = auto()
    KEYWORD = auto()

    # ==============================================================
    # 2. LITERALS
    # ==============================================================
    STRING = auto()
    CHAR = auto()
    NUMBER = auto()
    BOOL = auto()
    NULL = auto()
    DOCSTRING = auto()

    # ==============================================================
    # 3. ARITHMETIC OPERATORS
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
    # 4. ASSIGNMENT OPERATORS
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
    # 5. COMPARISON OPERATORS
    # ==============================================================
    EQUAL = auto()                # ==
    NOT_EQUAL = auto()            # !=
    LESS = auto()                 # <
    GREATER = auto()              # >
    LESS_EQUAL = auto()           # <=
    GREATER_EQUAL = auto()        # >=

    # ==============================================================
    # 6. LOGICAL AND BITWISE OPERATORS
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
    # 7. DELIMITERS
    # ==============================================================
    LPAREN = auto()               # (
    RPAREN = auto()               # )
    LBRACKET = auto()             # [
    RBRACKET = auto()             # ]
    LBRACE = auto()               # {
    RBRACE = auto()               # }

    # ==============================================================
    # 8. PUNCTUATION AND SPECIAL SYMBOLS
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
    # 9. ARROWS
    # ==============================================================
    ARROW = auto()                # ->
    FAT_ARROW = auto()            # =>
    LEFT_ARROW = auto()           # <-
    DOUBLE_ARROW = auto()         # <->

    # ==============================================================
    # 10. UNICODE (LOGIC AND MATHEMATICS)
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
    # 11. SPECIAL STATES
    # ==============================================================
    ERROR = auto()
    UNKNOWN = auto()
    EMPTY_LINE = auto()

    @classmethod
    def from_string(cls, name: str) -> Token | None:
        """Retrieve a `Token` member by its string name (case-insensitive)."""
        if not isinstance(name, str):
            return None
        return cls.__members__.get(name.strip().upper())

    @classmethod
    def from_code(cls, code: int) -> Token | None:
        """Retrieve a `Token` member by its integer ordinal value."""
        try:
            return cls(code)
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_tokens(cls) -> tuple[Token, ...]:
        """Return an immutable tuple containing all defined `Token` members."""
        return tuple(cls)


class CustomToken:
    """
    Represents a dynamically defined token type created at runtime.

    Enables language plugins, `Tokenize`, and symbol matchers to synthesize
    custom token types without mutating the immutable `Token` enumeration.
    """

    __slots__ = ("description", "name", "value")

    def __init__(
        self,
        name: str = "CustomToken",
        value: Any = None,
        description: str = "",
    ) -> None:
        """Initialize the dynamic token with a name, optional value, and description."""
        self.name: str = name
        self.value: Any = value if value is not None else name
        self.description: str = description

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
            return self.name == other or other == "CustomToken"
        return False

    def __hash__(self) -> int:
        return hash(self.name)


class TokenType:
    """
    Concrete lexeme instance emitted by the lexical analyzer.

    Encapsulates the formal token type (`Token` or `CustomToken`), the captured
    value from the source code, and 1-based line / 0-based column coordinates.
    """

    __slots__ = ("col", "description", "line", "token", "value")

    def __init__(
        self,
        token: Token | CustomToken,
        value: Any = None,
        line: int = 0,
        col: int = 0,
        description: str = "",
    ) -> None:
        """Initialize a concrete lexeme token with its type, value, and coordinates."""
        self.token: Token | CustomToken = token
        self.value: Any = value
        self.line: int = max(0, line) + 1
        self.col: int = max(0, col)
        self.description: str = description

    def long(self) -> int:
        """Return the ending column index of this token (`col + len(str(value))`)."""
        length = len(str(self.value)) if self.value is not None else 0
        return self.col + length

    def formatter(self, msg: str) -> str:
        """
        Interpolate contextual token placeholders (`$name`, `$value`, `$line`,
        `$col`, `$symbol`, `$long`) into a diagnostic string.
        """
        token_name: str = self.token.name
        token_val: str = str(self.token.value)
        content_val: str = str(self.value) if self.value is not None else token_name
        symbol_val: str = MAP_SYMBOLS.get(self.token, "")

        return (
            msg.replace("$name", token_name)
            .replace("$tvalue", token_val)
            .replace("$content", content_val)
            .replace("$value", content_val)
            .replace("$line", str(self.line))
            .replace("$len", str(self.line))
            .replace("$col", str(self.col))
            .replace("$symbol", symbol_val)
            .replace("$sym", symbol_val)
            .replace("$long", str(self.long()))
        )

    _formatter = formatter

    def raise_error(
        self,
        title: str,
        *caution: str,
        code: errors.CodeError | None = None,
        exit: bool = False,
    ) -> None:
        """
        Raise a structured `errors.LexerError` interpolating this token's
        coordinates and context into the caution messages.
        """
        err_code = code if code is not None else errors.LEXER_UNEXPECTED_CHARACTER
        msg = (
            f"{title} (Token: {self.token}, Valor: '{self.value}') "
            f"en línea {self.line}, columna {self.col}"
        )
        formatted_caution = tuple(self.formatter(c) for c in caution)
        errors.LexerError(msg, err_code, *formatted_caution).raise_error(exit=exit)

    def __repr__(self) -> str:
        return (
            f"TokenType(token={self.token}, value={self.value!r}, "
            f"line={self.line}, col={self.col})"
        )

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
            return self.token.name == other or str(self.value) == other
        return False

    def __hash__(self) -> int:
        return hash((self.token, str(self.value), self.line, self.col))


class _MapSymbolsDict(dict[str, Token]):
    """
    Bidirectional dictionary optimized for $O(1)$ lookup of operators and symbols
    by string symbol (`'+' -> Token.PLUS`), `Token` enum (`Token.PLUS -> '+'`),
    or token name (`'PLUS' -> '+'`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rev: dict[Any, str] = {}
        for sym, tok in self.items():
            self._rev[tok] = sym
            self._rev[tok.name] = sym

    def __getitem__(self, key: Any) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        if key in self._rev:
            return self._rev[key]
        raise KeyError(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if super().__contains__(key):
            return super().get(key, default)
        if key in self._rev:
            return self._rev[key]
        return default

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or key in self._rev


MAP_SYMBOLS: _MapSymbolsDict = _MapSymbolsDict({
    # Arithmetic Operators
    "+": Token.PLUS,
    "-": Token.MINUS,
    "*": Token.STAR,
    "/": Token.SLASH,
    "%": Token.PERCENT,
    "**": Token.POW,
    "//": Token.FLOOR_DIV,
    "++": Token.INCREMENT,
    "--": Token.DECREMENT,

    # Assignment Operators
    "=": Token.ASSIGN,
    "+=": Token.PLUS_ASSIGN,
    "-=": Token.MINUS_ASSIGN,
    "*=": Token.STAR_ASSIGN,
    "/=": Token.SLASH_ASSIGN,
    "%=": Token.PERCENT_ASSIGN,
    "**=": Token.POW_ASSIGN,
    "//=": Token.FLOOR_DIV_ASSIGN,
    "&=": Token.AND_ASSIGN,
    "|=": Token.OR_ASSIGN,
    "^=": Token.XOR_ASSIGN,
    "<<=": Token.SHL_ASSIGN,
    ">>=": Token.SHR_ASSIGN,
    ":=": Token.WALRUS,

    # Comparison Operators
    "==": Token.EQUAL,
    "!=": Token.NOT_EQUAL,
    "<": Token.LESS,
    ">": Token.GREATER,
    "<=": Token.LESS_EQUAL,
    ">=": Token.GREATER_EQUAL,

    # Logical and Bitwise Operators
    "~": Token.NOT,
    "&&": Token.AND_LOGIC,
    "||": Token.OR_LOGIC,
    "&": Token.AND,
    "|": Token.OR,
    "^": Token.XOR,
    "<<": Token.SHL,
    ">>": Token.SHR,

    # Delimiters
    "(": Token.LPAREN,
    ")": Token.RPAREN,
    "[": Token.LBRACKET,
    "]": Token.RBRACKET,
    "{": Token.LBRACE,
    "}": Token.RBRACE,

    # Punctuation and Special Characters
    ",": Token.COMMA,
    ".": Token.DOT,
    ":": Token.COLON,
    ";": Token.SEMICOLON,
    "@": Token.AT,
    "#": Token.HASH,
    "$": Token.DOLLAR,
    "?": Token.QUESTION,
    "?=": Token.QUESTION_ASSIGN,
    "!": Token.EXCLAMATION,
    "\\": Token.BACKSLASH,
    "_": Token.UNDERSCORE,

    # Arrows
    "->": Token.ARROW,
    "=>": Token.FAT_ARROW,
    "<-": Token.LEFT_ARROW,
    "<->": Token.DOUBLE_ARROW,

    # Unicode Logic & Math
    "∧": Token.LOGIC_AND,
    "∨": Token.LOGIC_OR,
    "¬": Token.LOGIC_NOT,
    "√": Token.SQRT,
    "∞": Token.INFINITY,
    "°": Token.DEGREE,
    "·": Token.MIDDLE_DOT,
    "•": Token.BULLET,
    "§": Token.SECTION,
    "...": Token.THREE_DOTS,
})

_SORTED_SYMBOLS: list[str] = sorted(MAP_SYMBOLS.keys(), key=len, reverse=True)


def get_tokens() -> tuple[Token, ...]:
    """Return an immutable tuple of all `Token` enum members."""
    return Token.get_tokens()


def get_sorted_symbols() -> list[str]:
    """
    Return all registered operator and symbol strings sorted by descending length
    to guarantee maximal-munch tokenization.
    """
    return list(_SORTED_SYMBOLS)


__all__ = [
    "MAP_SYMBOLS",
    "CustomToken",
    "Token",
    "TokenType",
    "get_sorted_symbols",
    "get_tokens",
]