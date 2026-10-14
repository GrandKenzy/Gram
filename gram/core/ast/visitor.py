"""
AST Combinator Visitor (`gram.core.ast.visitor`).
=================================================
Provides the `Visitor` dispatch function that validates and logs combinator
evaluation in the parser's diagnostic stream before invoking `combinator.parse`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators import Combinator, Ref

if TYPE_CHECKING:
    from gram.core.ast.analyzer import ASTAnalyzer


def Visitor(self: ASTAnalyzer, combinator: Combinator) -> Any:
    """
    Evaluate a grammar combinator against the current `ASTAnalyzer` state.

    Args:
        self (ASTAnalyzer): The active AST analyzer instance.
        combinator (Combinator): The combinator to parse.

    Returns:
        Any: The parsed AST node(s) or None if matching failed or combinator is invalid.
    """
    if isinstance(combinator, Ref):
        self.raytracing.addpath(combinator.rule_name)
        if getattr(combinator, "branchable", False) or getattr(combinator, "brancheable", False):
            self.raytracing.generate_branch()

    should_trace = not getattr(combinator, "ignore", False)
    if should_trace:
        self.current_level += 1
        self.raytracing.add(combinator, level=self.current_level)

    try:
        if not isinstance(combinator, Combinator):
            self.error(f'Objeto inválido pasado a Visitor: {combinator!r}')
            self.report_error(
                errors.GrammarError(
                    'UnsupportedCombinator',
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f'Se esperaba una instancia de Combinator en Visitor, pero se recibió "{type(combinator).__name__}".',
                    'Verifique que todas las reglas gramaticales estén construidas con combinadores válidos.',
                )
            )
            return None

        self.parser.debug(f'Procesando el combinador de tipo {combinator.type()}')
        return combinator.parse(self)
    finally:
        if should_trace:
            self.current_level -= 1


__all__ = ['Visitor']