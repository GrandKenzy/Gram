"""
Módulo Puente de Compatibilidad (`gram.core.lexer.word`).
=========================================================
Proporciona acceso directo e idéntico a todas las definiciones y funciones
de `gram.core.lexer.words` garantizando total compatibilidad hacia atrás.
"""
from __future__ import annotations

import sys
from gram.core.lexer import words
from gram.core.lexer.words import *

# Sincronización explícita en sys.modules
sys.modules['gram.core.lexer.word'] = words
