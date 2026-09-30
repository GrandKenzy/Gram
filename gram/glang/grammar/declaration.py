"""
Gramática de Declaraciones de GLANG (`gram.glang.grammar.declaration`).
======================================================================
Define la regla DECLARATION como alternativa de las declaraciones maestras.
"""
from __future__ import annotations

from gram.core.combinators import Alt, Ref
from gram.glang.rules import (
    CLN_DECLARATION,
    CLN_DEFINE,
    CLN_KEYWORD,
    CLN_PROGRAM,
    INCLUDE,
    grammarType,
)
from gram.native.rules import DECLARATION

grammar: grammarType = {
    DECLARATION: Alt(
        Ref(INCLUDE),
        Ref(CLN_DEFINE),
        Ref(CLN_KEYWORD),
        Ref(CLN_PROGRAM),
        Ref(CLN_DECLARATION),
    )
}

__all__ = ['grammar']
