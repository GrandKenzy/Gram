"""
Gram Framework (`gram`).
========================
Pure-Python meta-interpretation and DSL parsing framework.

Exposes the top-level subpackages and metadata:
- `lexer` (`gram.core.lexer`): `Lexer`, `Token`, `TokenType`, `CustomToken`, `words`, `Keyword`, `WordGroup`.
- `parser` (`gram.core.parser`): `Parser`, `ParseState`, `Checkpoint`, `TokenInfo`.
- `ast` (`gram.core.ast`): `ASTAnalyzer`, `ASTState`, `ASTNode`, `ASTRef`, `ArrayNode`, `RayTracing`.
- `combinators` (`gram.core.combinators`): `Seq`, `Alt`, `Opt`, `Many`, `Some`, `Separator`, `Enclosed`,
  `Until`, `UntilIndent`, `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `Ref`, `RuleItem`,
  `Item`, `Literal`, `Save`, `Load`, `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator`,
  `Req`, `ArithmeticExpr`, `ConditionalExpr`, `DualExpr`.
- `rules` (`gram.core.rules`): `AutoCode`, `SetCode`, `CodeManager`.
- `config`, `errors`, `utilities`, `vsix`.
"""
from __future__ import annotations

# System submodules
from gram import config, errors, utilities, vsix
from gram.core import ast, combinators, lexer, parser, rules
from gram.core.process import (
    process,
)

__version__ = "2.0.0b2"
__version_info__ = (2, 0, 0, "beta", 2)


def version() -> str:
    """Retorna la versión actual del Framework Gram."""
    return __version__


__all__ = [
    # Metadatos
    "__version__",
    "__version_info__",
    "ast",
    "combinators",
    "config",
    "errors",
    "lexer",
    "parser",
    "process",
    "rules",
    "utilities",
    "version",
    "vsix",
]
