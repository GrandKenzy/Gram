"""
Grammar Rule Reference Combinator (`gram.core.combinators.reference`).
======================================================================
Provides the `Ref` combinator to dynamically resolve
and evaluate production rules, supporting mutual recursion, forward references,
and named `ASTRef` node wrapping.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from gram import errors
from gram.core.ast.nodes import ASTRef
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.kinds import CombinatorKind

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Ref(Combinator):
    """
    Rule reference combinator that delegates parsing to another `RuleItem`
    production rule and optionally wraps the output into an `ASTRef` node.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.REFERENCE

    def __init__(
        self,
        rule: type[RuleItem],
        name: str | None = None,
        strict: bool = False,
    ) -> None:
        """
        Initialize a reference to a target grammar rule.

        Args:
            rule (type[RuleItem]): Target grammar rule class to evaluate.
            name (str | None): Optional custom label; if set, wraps matched
                results in an `ASTRef` node.
        """
        super().__init__()
        self.rule: type[RuleItem] = rule
        self.name: str | None = name
        if self.name is None and not strict and getattr(self.rule, "nodeable", False):
            self.name = self.rule_name
        self.branchable: bool = False

    @property
    def rule_name(self) -> str:
        """Return the descriptive identifier of the referenced rule."""
        if isinstance(self.rule, str):
            return self.rule
        if isinstance(self.rule, Combinator):
            return getattr(self.rule, "name", "") or type(self.rule).__name__
        return getattr(self.rule, "name", "") or getattr(self.rule, "__name__", repr(self.rule))

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Resolve the referenced rule's grammar combinator and evaluate it
        through `analyzer.visitor`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any: `ASTRef` instance (if `self.name` is set), raw visitor result,
            or None if the rule has no grammar or fails to match.
        """
        parser = analyzer.parser
        father = parser.node("ProcessingRef", "Procesando referencia", set_target=True)
        try:
            r_name = self.rule_name
            if isinstance(self.rule, Combinator):
                entrypoint = self.rule
            else:
                entrypoint = getattr(self.rule, "entrypoint", None)

            if entrypoint is None:
                father.note(
                    f"La regla referenciada '{r_name}' no tiene gramática definida.",
                    "error",
                )
                analyzer.report_error(
                    errors.GrammarError(
                        "EmptyRuleReference",
                        errors.GRAMMAR_RULE_NOT_FOUND,
                        f'La regla referenciada "{r_name}" no tiene un combinador "entrypoint" definido.',
                        "Asegúrese de asignar un combinador válido al atributo 'entrypoint' de la regla.",
                    )
                )
                return None

            father.note(
                f"Analizando regla {r_name} de tipo {entrypoint.type()}.",
                "normal",
            )
            result = analyzer.visitor(entrypoint)
            if result is None:
                return None

            if self.name:
                nodes = result if isinstance(result, list) else [result]
                return ASTRef(self.name, nodes)
            return result
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Ref({self.rule_name!r})"



__all__ = [
    "Ref",
]
