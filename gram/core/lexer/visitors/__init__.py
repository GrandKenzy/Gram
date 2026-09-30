"""
Subpaquete de Visitantes Especializados del Lexer (`gram.core.lexer.visitors`).
================================================================================
Contiene los analizadores especializados por categoría léxica:
  - numbers: Literales numéricos (enteros, decimales, notación científica, hex, bin, oct).
  - strings: Cadenas simples, dobles y docstrings multilínea.
  - symbols: Operadores y delimitadores mediante maximal munch.
  - words: Identificadores, booleanos, nulos y palabras clave (words.py).
"""
from __future__ import annotations

from gram.core.lexer.visitors import numbers, strings, symbols, words

__all__ = ['numbers', 'strings', 'symbols', 'words']
