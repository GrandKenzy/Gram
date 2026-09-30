"""
Subpaquete de Combinadores de Coincidencia (`gram.core.combinators.match`).
==========================================================================
Proporciona combinadores atómicos especializados en validar y filtrar tokens:
- `MatchToken`: Coincidencia por tipo de token (`Token` enum, `CustomToken` o nombre).
- `MatchKeyword`: Coincidencia por palabra clave registrada en el lexer.
- `MatchGroup`: Coincidencia por pertenencia a un grupo semántico (`WordGroup`).
- `MatchSymbol` / `MatchSeqSymbol`: Coincidencia textual por expresión regular o símbolos.
- `generador_expr`: Función constructora de expresiones regulares.
"""
from __future__ import annotations

from gram.core.combinators.match.match_group import MatchGroup
from gram.core.combinators.match.match_keyword import MatchKeyword
from gram.core.combinators.match.match_symbol import (
    MatchSeqSymbol,
    MatchSymbol,
    generador_expr,
)
from gram.core.combinators.match.match_token import MatchToken

__all__ = [
    "MatchGroup",
    "MatchKeyword",
    "MatchSeqSymbol",
    "MatchSymbol",
    "MatchToken",
    "generador_expr",
]
