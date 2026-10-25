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
from gram.core.combinators.signals import ControlFlowSignal

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

    if self.trace_mode == 'off':
        return combinator.parse(self)

    if isinstance(combinator, Ref):
        self.raytracing.addpath(combinator.rule_name)
        if getattr(combinator, "branchable", False):
            self.raytracing.generate_branch()

    should_trace = not getattr(combinator, "ignore", False)
    record = None
    if should_trace:
        self.current_level += 1
        if self.trace_mode == 'detailed':
            record = self.raytracing.begin(
                combinator, depth=self.current_level, position=self.parser.pos
            )
        else:
            self.raytracing.add(combinator, level=self.current_level)

    try:
        self.parser.debug(f'Procesando el combinador de tipo {combinator.type()}')
        result = combinator.parse(self)
    except BaseException as exception:
        if record is not None:
            self.raytracing.end(
                record,
                position=self.parser.pos,
                outcome='CONTROL' if isinstance(exception, ControlFlowSignal) else 'ERROR',
                exception_type=type(exception).__name__,
            )
        raise
    else:
        if record is not None:
            self.raytracing.end(
                record,
                position=self.parser.pos,
                outcome='SUCCESS' if result is not None else 'FAILED',
            )
        return result
    finally:
        if should_trace:
            self.current_level -= 1


__all__ = ['Visitor']
