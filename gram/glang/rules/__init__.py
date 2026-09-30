"""
Subpaquete de Reglas Sintácticas de GLANG (`gram.glang.rules`).
==============================================================
Exporta las reglas y combinadores necesarios para parsear la gramática de GLang.
"""
from __future__ import annotations

from gram.core.combinators import Combinator, RuleItem, RuleType
from gram.glang.rules.decl_combinators import (
    CLN_ALT,
    CLN_ANY,
    CLN_GROUP,
    CLN_ITEM,
    CLN_LITERAL,
    CLN_MANY,
    CLN_OPTIONAL,
    CLN_REFERENCE,
    CLN_SEP_ARG,
    CLN_SEPARATOR,
    CLN_SEQ,
    CLN_SEQ_SYMBOL,
    CLN_SOME,
    CLN_TOKEN,
    CLN_TOKENLIST,
    CLN_TOKENIZE,
    CLN_VALID_DECLARATION,
    CLN_WORD,
)
from gram.glang.rules.decl_rules import (
    CLN_DECLARATION,
    CLN_DEFINE,
    CLN_KEYWORD,
    CLN_PROGRAM,
    INCLUDE,
)
from gram.native.rules import PASS

grammarType = dict[RuleType, Combinator]

__all__ = [
    'PASS',
    'CLN_REFERENCE',
    'CLN_WORD',
    'CLN_GROUP',
    'CLN_TOKEN',
    'CLN_VALID_DECLARATION',
    'CLN_ALT',
    'CLN_SEQ',
    'CLN_SOME',
    'CLN_MANY',
    'CLN_LITERAL',
    'CLN_ANY',
    'CLN_TOKENLIST',
    'CLN_SEQ_SYMBOL',
    'CLN_SEP_ARG',
    'CLN_SEPARATOR',
    'CLN_ITEM',
    'CLN_TOKENIZE',
    'CLN_OPTIONAL',
    'INCLUDE',
    'CLN_DEFINE',
    'CLN_KEYWORD',
    'CLN_PROGRAM',
    'CLN_DECLARATION',
    'grammarType',
]
