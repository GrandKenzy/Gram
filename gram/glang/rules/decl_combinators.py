"""
Reglas Sintácticas de Combinadores de GLANG (`gram.glang.rules.decl_combinators`).
================================================================================
Define las reglas gramaticales para parsear combinadores y expresiones hijas
en especificaciones sintácticas de GLang (.glang).
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators import (
    Alt,
    Combinator,
    Item,
    Many,
    MatchKeyword,
    MatchToken,
    Opt,
    Ref,
    RuleItem,
    Separator,
    Seq,
    Some,
    Tokenize,
)
from gram.core.lexer.tokens import Token
from gram.native.rules import BLOCK, ENDLINE, PASS


class CLN_REFERENCE(RuleItem):
    name = "REFERENCE"
    code = 40
    description = "Referencia por nombre o código a otra regla sintáctica (ej. reference IDENT o reference 1000)."
    grammar = Seq(
        MatchKeyword("reference"),
        Alt(
            MatchToken("IDENT"),
            MatchToken("NUMBER"),
        ),
        Ref(ENDLINE),
    )
    suggestions: dict[int, Any] = {
        1: [("IDENT", "Referencia por nombre de identificador"), ("1000", "Referencia por código numérico")]
    }
    suggestions_autocomplete = True


def get_token_suggestions() -> list[tuple[str, str, str]]:
    """Genera lista de sugerencias de tokens disponibles para autocompletado."""
    try:
        from gram.core.lexer.tokens import Token as _Token
        result = []
        for member in _Token:
            result.append((member.name, f"#{member.value}", ""))
        return result
    except Exception:
        return []


class CLN_TOKEN(RuleItem):
    name = "TOKEN"
    code = 41
    description = "Coincidencia con un tipo de token léxico (ej. tokens.IDENT, tokens.NUMBER, tokens.STRING)."
    grammar = Seq(
        MatchKeyword("tokens"),
        MatchToken("DOT"),
        MatchToken("IDENT"),
        Ref(ENDLINE),
    )
    colors: dict[int, str] = {2: "#4EC9B0"}
    suggestions: dict[int, Any] = {2: get_token_suggestions}
    suggestions_autocomplete = True


class CLN_LITERAL(RuleItem):
    name = "LITERAL"
    code = 46
    description = "Coincidencia con un valor literal constante (cadena, número, booleano)."
    grammar = Seq(
        MatchKeyword("literal"),
        Opt(
            Alt(
                MatchToken("STRING"),
                MatchToken("NUMBER"),
                MatchToken("BOOL"),
                MatchToken("CHAR"),
                MatchToken("IDENT"),
            )
        ),
        Ref(ENDLINE),
    )
    suggestions_autocomplete = True


class CLN_ANY(RuleItem):
    name = "ANY"
    code = 65
    description = "Coincidencia con cualquier token individual (any) o producción gramatical (anygrammar)."
    grammar = Seq(
        Alt(MatchKeyword("any"), MatchKeyword("anygrammar")),
        Ref(ENDLINE),
    )
    suggestions: dict[int, Any] = {
        0: [("any", "Cualquier token individual"), ("anygrammar", "Cualquier producción gramatical")]
    }
    suggestions_autocomplete = True


class CLN_TOKENLIST(RuleItem):
    name = "TOKENLIST"
    code = 192442
    description = "Secuencia delimitada de elementos léxicos entre corchetes ([...])."
    grammar = Seq(
        MatchToken("LBRACKET"),
        Separator(
            values=[
                Item(
                    MatchKeyword("tokens"),
                    MatchToken("DOT"),
                    MatchToken("IDENT"),
                ),
                Item(
                    MatchKeyword("words"),
                    Alt(MatchToken("STRING"), MatchToken("IDENT")),
                ),
                Item(
                    MatchKeyword("literal"),
                    Opt(
                        Alt(
                            MatchToken("STRING"),
                            MatchToken("NUMBER"),
                            MatchToken("BOOL"),
                            MatchToken("CHAR"),
                            MatchToken("IDENT"),
                        )
                    ),
                ),
                Item(
                    MatchKeyword("reference"),
                    Alt(
                        MatchToken("IDENT"),
                        MatchToken("NUMBER"),
                    ),
                ),
                MatchToken("STRING"),
                MatchToken("NUMBER"),
                MatchToken("IDENT"),
            ]
        ),
        MatchToken("RBRACKET"),
    )


class CLN_GROUP(RuleItem):
    name = "GROUP"
    code = 42
    description = "Coincidencia con cualquier palabra clave perteneciente a un grupo temático ($NOMBRE_GRUPO)."
    grammar = Seq(
        MatchKeyword("groups"),
        MatchToken("DOLLAR"),
        MatchToken("IDENT"),
        Opt(
            Seq(
                Opt(Alt(MatchKeyword("exclude"), MatchKeyword("only"))),
                Ref(CLN_TOKENLIST),
            )
        ),
        Ref(ENDLINE),
    )
    suggestions: dict[int, Any] = {0: [("groups", "Coincidencia de grupo de palabras clave")]}
    suggestions_autocomplete = True


class CLN_WORD(RuleItem):
    name = "WORD"
    code = 43
    description = "Coincidencia con una palabra textual o identificador exacto (words \"palabra\")."
    grammar = Seq(
        MatchKeyword("words"),
        Alt(MatchToken("STRING"), MatchToken("IDENT")),
        Ref(ENDLINE),
    )
    suggestions: dict[int, Any] = {0: [("words", "Palabra textual exacta")]}
    suggestions_autocomplete = True


class CLN_SEQ_SYMBOL(RuleItem):
    name = "SEQ_SYMBOL"
    code = 64
    description = "Coincidencia de símbolos secuenciales o patrones de expresión regular (seqsym o regex)."
    grammar = Alt(
        Seq(
            MatchKeyword("seqsym"),
            Alt(
                Seq(MatchKeyword("regex"), MatchToken("STRING")),
                Seq(MatchKeyword("symbols"), Ref(CLN_TOKENLIST)),
                MatchToken("STRING"),
            ),
            Ref(ENDLINE),
        ),
        Seq(
            MatchKeyword("regex"),
            MatchToken("STRING"),
            Ref(ENDLINE),
        ),
    )
    suggestions_autocomplete = True


class CLN_SEP_ARG(RuleItem):
    name = "SEP_ARG"
    code = 61
    description = "Argumento de delimitación para un combinador Separator."
    grammar = Alt(
        Seq(
            MatchKeyword("tokens"),
            MatchToken("DOT"),
            MatchToken("IDENT"),
        ),
        Seq(
            MatchKeyword("literal"),
            Alt(
                MatchToken("STRING"),
                MatchToken("CHAR"),
                MatchToken("IDENT"),
            ),
        ),
        MatchToken("STRING"),
        MatchToken("IDENT"),
    )


class CLN_SEPARATOR(RuleItem):
    name = "SEPARATOR"
    code = 60
    description = "Combinador de secuencias de elementos delimitados por separadores (ej. Separator sep \",\")."
    grammar = Alt(
        Seq(
            Alt(MatchKeyword("Separator"), MatchKeyword("separator")),
            Many(
                Alt(
                    Seq(MatchKeyword("sep"), Ref(CLN_SEP_ARG)),
                    Seq(MatchKeyword("name"), MatchToken("STRING")),
                )
            ),
            MatchToken("COLON"),
            Ref(ENDLINE),
            Ref(BLOCK),
        ),
        Seq(
            Alt(MatchKeyword("Separator"), MatchKeyword("separator")),
            Some(
                Alt(
                    Seq(Opt(MatchKeyword("values")), Ref(CLN_TOKENLIST)),
                    Seq(MatchKeyword("sep"), Ref(CLN_SEP_ARG)),
                    Seq(MatchKeyword("name"), MatchToken("STRING")),
                )
            ),
            Ref(ENDLINE),
        ),
    )
    suggestions: dict[int, Any] = {0: [("Separator", "Combinador de elementos delimitados por separador")]}
    suggestions_autocomplete = True


class CLN_ITEM(RuleItem):
    name = "ITEM"
    code = 49
    description = "Elemento unitario dentro de un combinador Separator (Item: ...)."
    grammar = Alt(
        Seq(
            Alt(MatchKeyword("Item"), MatchKeyword("item")),
            MatchToken("COLON"),
            Ref(ENDLINE),
            Ref(BLOCK),
        ),
        Seq(
            Alt(MatchKeyword("Item"), MatchKeyword("item")),
            Ref(CLN_TOKENLIST),
            Ref(ENDLINE),
        ),
    )
    suggestions: dict[int, Any] = {0: [("Item", "Elemento de Separator")]}
    suggestions_autocomplete = True


class CLN_TOKENIZE(RuleItem):
    name = "TOKENIZE"
    code = 63
    description = "Combinador de tokenización y ensamblado léxico (Tokenize / New)."
    grammar = Seq(
        Alt(
            MatchKeyword("Tokenize"),
            MatchKeyword("tokenize"),
            MatchKeyword("New"),
        ),
        Opt(Alt(MatchToken("STRING"), MatchToken("IDENT"))),
        Many(
            Alt(
                Seq(MatchKeyword("name"), Alt(MatchToken("STRING"), MatchToken("IDENT"))),
                Seq(MatchKeyword("join"), MatchToken("STRING")),
            )
        ),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Tokenize", "Tokenización personalizada"), ("New", "Nueva entidad de token")]}
    suggestions_autocomplete = True


class CLN_SEQ(RuleItem):
    name = "SEQUENCE"
    code = 45
    description = "Bloque combinador Seq: todos los elementos en orden secuencial estricto."
    grammar = Seq(
        MatchKeyword("Seq"),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Seq:", "Bloque de secuencia estricta")]}
    suggestions_autocomplete = True


class CLN_OPTIONAL(RuleItem):
    name = "OPTIONAL"
    code = 100
    description = "Bloque combinador Opt u optional: cero o una ocurrencia (?)."
    grammar = Seq(
        Alt(MatchKeyword("optional"), MatchKeyword("Opt")),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Opt:", "Bloque opcional"), ("optional:", "Bloque opcional")]}
    suggestions_autocomplete = True


class CLN_ALT(RuleItem):
    name = "ALTERNATIVE"
    code = 55
    description = "Bloque combinador Alt: múltiples ramas gramaticales alternativas."
    grammar = Seq(
        MatchKeyword("Alt"),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Alt:", "Bloque de alternativa")]}
    suggestions_autocomplete = True


class CLN_SOME(RuleItem):
    name = "SOME"
    code = 51
    description = "Bloque combinador Some: una o más repeticiones consecutivas (+)."
    grammar = Seq(
        MatchKeyword("Some"),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Some:", "Una o más repeticiones (+)")]}
    suggestions_autocomplete = True


class CLN_MANY(RuleItem):
    name = "MANY"
    code = 52
    description = "Bloque combinador Many: cero o más repeticiones consecutivas (*)."
    grammar = Seq(
        MatchKeyword("Many"),
        MatchToken("COLON"),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    suggestions: dict[int, Any] = {0: [("Many:", "Cero o más repeticiones (*)")]}
    suggestions_autocomplete = True


class CLN_VALID_DECLARATION(RuleItem):
    name = "VALID_DECLARATION_BODY"
    code = 44
    description = "Cuerpo sintáctico válido dentro de un combinador o regla de GLang."
    grammar = Some(
        Alt(
            Ref(PASS),
            Ref(CLN_TOKEN),
            Ref(CLN_WORD),
            Ref(CLN_LITERAL),
            Ref(CLN_ANY),
            Ref(CLN_SEQ_SYMBOL),
            Ref(CLN_GROUP),
            Ref(CLN_REFERENCE),
            Ref(CLN_SEPARATOR),
            Ref(CLN_TOKENIZE),
            Ref(CLN_ITEM),
            Ref(CLN_SEQ),
            Ref(CLN_ALT),
            Ref(CLN_SOME),
            Ref(CLN_MANY),
            Ref(CLN_OPTIONAL),
        )
    )


__all__ = [
    "CLN_REFERENCE",
    "CLN_TOKEN",
    "CLN_LITERAL",
    "CLN_ANY",
    "CLN_TOKENLIST",
    "CLN_GROUP",
    "CLN_WORD",
    "CLN_SEQ_SYMBOL",
    "CLN_SEP_ARG",
    "CLN_SEPARATOR",
    "CLN_ITEM",
    "CLN_TOKENIZE",
    "CLN_SEQ",
    "CLN_OPTIONAL",
    "CLN_ALT",
    "CLN_SOME",
    "CLN_MANY",
    "CLN_VALID_DECLARATION",
    "get_token_suggestions",
]
