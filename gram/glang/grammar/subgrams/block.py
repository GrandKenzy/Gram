"""
Gramática de Bloques de GLANG (`gram.glang.grammar.subgrams.block`).
===================================================================
Define la regla BLOCK para bloques delimitados por indentación.
"""
from __future__ import annotations

from gram.core.combinators import MatchToken, Ref, Seq
from gram.glang.rules import CLN_VALID_DECLARATION, grammarType
from gram.native.rules import BLOCK

grammar: grammarType = {
    BLOCK: Seq(
        MatchToken('INDENT'),
        Ref(CLN_VALID_DECLARATION),
        MatchToken('DEDENT'),
    )
}

__all__ = ['grammar']
