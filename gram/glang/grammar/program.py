"""
Gramática Raíz de GLANG (`gram.glang.grammar.program`).
======================================================
Define la regla PROGRAM como repetición de declaraciones.
"""
from __future__ import annotations

from gram.core.combinators import Many, Ref
from gram.glang.rules import grammarType
from gram.native.rules import DECLARATION, PROGRAM

grammar: grammarType = {
    PROGRAM: Many(
        Ref(DECLARATION),
    )
}

__all__ = ['grammar']
