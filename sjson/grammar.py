"""
Gramática Formal de SJSON para Gram Framework (`gram.sjson.grammar`).
======================================================================
Define las reglas sintácticas RuleItem para el parser y el generador de temas/VSIX.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators import (
    Alt,
    MatchToken,
    Opt,
    Ref,
    RuleItem,
    Separator,
    Seq,
)
from gram.core.lexer.tokens import Token


class SJSON_VALUE(RuleItem):
    """Valor genérico de SJSON (objeto, array, expresión, número, cadena, bool, null)."""
    code = 8001
    name = "SJSON_VALUE"
    description = "Valor JSON o expresión calculada"


class SJSON_PAIR(RuleItem):
    """Par clave: valor de un objeto SJSON con soporte para claves con o sin comillas."""
    code = 8002
    name = "SJSON_PAIR"
    description = "Par clave: valor en objeto SJSON"


class SJSON_OBJECT(RuleItem):
    """Objeto SJSON delimitado por llaves { ... } con soporte para trailing comma y extend."""
    code = 8003
    name = "SJSON_OBJECT"
    description = "Objeto asociativo SJSON"


class SJSON_ARRAY(RuleItem):
    """Arreglo SJSON delimitado por [ ... ] con trailing comma."""
    code = 8004
    name = "SJSON_ARRAY"
    description = "Arreglo indexado SJSON"


class SJSON_VAR_DECL(RuleItem):
    """Declaración de variable con let o var."""
    code = 8005
    name = "SJSON_VAR_DECL"
    description = "Declaración de variable let/var (solo números y strings)"


class SJSON_EXPR(RuleItem):
    """Expresión o cálculo aritmético o concatenación de strings."""
    code = 8006
    name = "SJSON_EXPR"
    description = "Expresión evaluable con operadores +, -, *, /, %"


SJSON_PAIR.grammar = Seq(
    Alt(MatchToken(Token.STRING), MatchToken(Token.IDENT)),
    MatchToken(Token.COLON),
    Ref(SJSON_VALUE),
)

SJSON_OBJECT.grammar = Seq(
    MatchToken(Token.LBRACE),
    Separator(values=[Alt(Ref(SJSON_VAR_DECL), Ref(SJSON_PAIR))], sep=Token.COMMA, allow_trailing=True),
    MatchToken(Token.RBRACE),
)

SJSON_ARRAY.grammar = Seq(
    MatchToken(Token.LBRACKET),
    Separator(values=[Ref(SJSON_VALUE)], sep=Token.COMMA, allow_trailing=True),
    MatchToken(Token.RBRACKET),
)

SJSON_VAR_DECL.grammar = Seq(
    Alt(MatchToken(Token.KEYWORD), MatchToken(Token.IDENT)),
    MatchToken(Token.IDENT),
    MatchToken(Token.ASSIGN),
    Ref(SJSON_VALUE),
)

SJSON_VALUE.grammar = Alt(
    Ref(SJSON_OBJECT),
    Ref(SJSON_ARRAY),
    MatchToken(Token.STRING),
    MatchToken(Token.NUMBER),
    MatchToken(Token.BOOL),
    MatchToken(Token.NULL),
    MatchToken(Token.IDENT),
)


def get_sjson_grammar() -> dict[type[RuleItem], Any]:
    """Retorna el mapa formal de gramática de SJSON."""
    from gram.native.rules import DECLARATION, PROGRAM

    PROGRAM.grammar = Ref(DECLARATION)
    DECLARATION.grammar = Alt(Ref(SJSON_VALUE), Ref(SJSON_VAR_DECL))

    return {
        PROGRAM: PROGRAM.grammar,
        DECLARATION: DECLARATION.grammar,
        SJSON_VALUE: SJSON_VALUE.grammar,
        SJSON_PAIR: SJSON_PAIR.grammar,
        SJSON_OBJECT: SJSON_OBJECT.grammar,
        SJSON_ARRAY: SJSON_ARRAY.grammar,
        SJSON_VAR_DECL: SJSON_VAR_DECL.grammar,
    }
