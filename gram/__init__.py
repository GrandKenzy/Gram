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
from gram import config, errors, ir, utilities, vsix
from gram.utilities.error import configure_runtime

configure_runtime(
    should_exit=lambda: bool(config.ERROR_EXIT_ON_ERROR),
    hide_console=lambda: bool(config.ERROR_HIDE_CONSOLE),
    dispatch_error_hooks=utilities.Diagnostics.dispatch_error_hooks,
)

from gram.core import ast, combinators, lexer, parser, rules
from gram.core.process import (
    process,
)

__version__ = "3.0.0"
__version_info__ = (3, 0, 0, "final", 0)


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
    "ir",
    "lexer",
    "parser",
    "process",
    "rules",
    "utilities",
    "version",
    "vsix",
]
