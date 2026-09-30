"""
Gramática Unificada de GLANG (`gram.glang.grammar`).
====================================================
Combina todas las secciones de gramática en un único diccionario ejecutable.
"""
from __future__ import annotations

from gram.glang.grammar.declaration import grammar as declaration_grammar
from gram.glang.grammar.program import grammar as program_grammar
from gram.glang.grammar.subgrams.block import grammar as block_grammar
from gram.glang.rules import grammarType

grammar: grammarType = {}
grammar.update(program_grammar)
grammar.update(declaration_grammar)
grammar.update(block_grammar)

__all__ = ['grammar']
