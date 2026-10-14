"""
Base Classes for Syntactic Combinators and Rules (`gram.core.combinators.base`).
================================================================================
Defines the abstract `Combinator` base class, the `RuleMeta` metaclass, and the
declarative `RuleItem` base class for formal grammar production rules.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.rules.codes import AutoCode, SetCode, code_manager

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer

_NON_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")


class Combinator:
    """
    Abstract base class for all Gram Framework syntactic combinators.

    Each combinator encapsulates a declarative strategy for matching, consuming,
    branching, or repeating tokens across the parser's token stream.
    """

    header_class: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.header_class: bool = self.__class__.header_class
        super().__init__()

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Execute syntactic parsing for this combinator against `analyzer`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer holding the parser state.

        Returns:
            Any: Generated AST node(s), token(s), or None if no match occurred.
        """
        err = errors.GrammarError(
            "CombinatorNotImplemented",
            errors.GRAMMAR_ANY_NOT_IMPLEMENTED,
            f"El combinador {self.__class__.__name__} debe implementar el método parse().",
            "Implemente el método parse(self, analyzer: ASTAnalyzer) en la subclase del combinador.",
        )
        analyzer.report_error(err)
        raise NotImplementedError(
            f"Combinator {self.__class__.__name__} must implement parse()."
        )

    @classmethod
    def type(cls) -> str:
        """Return the canonical class name of the combinator."""
        return cls.__name__

    def __or__(self, other: Any) -> Combinator:
        """Overload the binary `|` operator to compose alternative (`Alt`) branches."""
        if not isinstance(other, Combinator):
            return NotImplemented
        try:
            from gram.core.combinators.alternative import Alt

            if isinstance(self, Alt):
                if isinstance(other, Alt):
                    return Alt(*(self.combinators + other.combinators))
                return Alt(*(self.combinators + (other,)))
            if isinstance(other, Alt):
                return Alt(self, *other.combinators)
            return Alt(self, other)
        except ImportError:
            return NotImplemented

    def __add__(self, other: Any) -> Combinator:
        """Overload the binary `+` operator to compose sequential (`Seq`) steps."""
        if not isinstance(other, Combinator):
            return NotImplemented
        try:
            from gram.core.combinators.sequence import Seq

            if isinstance(self, Seq):
                if isinstance(other, Seq):
                    return Seq(*(self.combinators + other.combinators))
                return Seq(*(self.combinators + (other,)))
            if isinstance(other, Seq):
                return Seq(self, *other.combinators)
            return Seq(self, other)
        except ImportError:
            return NotImplemented

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class RuleMeta(type):
    """
    Metaclass for declarative `RuleItem` grammar rules.

    Automatically allocates unique rule codes via `AutoCode` and registers
    positive integer rule IDs in the central `code_manager`.
    """

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> type:
        raw_code = namespace.get("code")

        if raw_code is AutoCode or (
            isinstance(raw_code, type) and issubclass(raw_code, AutoCode)
        ) or "code" not in namespace and bases:
            namespace["code"] = AutoCode()
        elif callable(raw_code) and not isinstance(raw_code, type):
            try:
                namespace["code"] = raw_code()
            except TypeError:
                pass

        cls = super().__new__(mcls, name, bases, namespace)

        code_val = getattr(cls, "code", 0)
        if isinstance(code_val, int) and code_val > 0:
            code_manager.register(code_val, rule=cls)

        return cls

    def __repr__(cls) -> str:
        return (
            f"{cls.__name__}("
            f"code={cls.code!r}, "
            f"name={cls.name or cls.__name__!r}, "
            f"grammar={bool(cls.grammar)}"
            f")"
        )
    grammar = None
    name = None
    code = None


class RuleItem(metaclass=RuleMeta):
    """
    Declarative base class for formal grammar production rules.

    Associates a numeric rule code, root combinator expression, documentation,
    syntax highlighting colors, and IDE/VSIX completion metadata.
    """

    code: int = 0
    name: str = ""
    description: str = ""
    grammar: Combinator | None = None
    docs: str = ""
    colors: dict[int, str] = {}
    suggestions: dict[int | str, Any] = {}
    suggestions_autocomplete: bool = False
    is_structural: bool = False
    ignore: bool = False
    no_simplify: bool = False
    queries: Any = None
    hints: dict[int, Any] = {}

    @classmethod
    def contain_grammar(cls) -> bool:
        """Return True if this rule defines a non-null `grammar` combinator."""
        return cls.grammar is not None

    @classmethod
    def compile(cls) -> dict[str, Any]:
        """
        Compile rule metadata into a structured dictionary suitable for
        editor extensions (VSIX, TextMate grammars, and Language Servers).
        """
        r_name = cls.name or cls.__name__
        r_colors = dict(cls.colors) if isinstance(cls.colors, dict) else {}
        r_sugg = dict(cls.suggestions) if isinstance(cls.suggestions, dict) else {}
        r_hints = dict(cls.hints) if isinstance(cls.hints, dict) else {}

        raw_queries = cls.queries
        if raw_queries is None:
            r_queries: list[Any] = []
        elif isinstance(raw_queries, (list, tuple, set)):
            r_queries = list(raw_queries)
        else:
            r_queries = [raw_queries]

        auto_keywords: list[str] = []

        def _collect_keywords(comb: Any) -> None:
            if comb is None:
                return
            if hasattr(comb, "keyword") and isinstance(comb.keyword, str):
                auto_keywords.append(comb.keyword)
            if hasattr(comb, "combinators") and isinstance(
                comb.combinators, (list, tuple)
            ):
                for sub in comb.combinators:
                    _collect_keywords(sub)
            if hasattr(comb, "combinator"):
                _collect_keywords(comb.combinator)
            if hasattr(comb, "values") and isinstance(comb.values, (list, tuple)):
                for sub in comb.values:
                    _collect_keywords(sub)

        _collect_keywords(cls.grammar)
        for q in r_queries:
            if (
                hasattr(q, "trigger_keywords")
                and not q.trigger_keywords
                and auto_keywords
            ):
                q.trigger_keywords = list(auto_keywords)

        color_val = r_colors.get(0, "#FFFFFF")
        clean_name = _NON_IDENT_RE.sub("_", r_name).lower()
        scope_name = f"entity.name.rule.gram.{clean_name}"

        return {
            "name": r_name,
            "code": cls.code,
            "description": cls.description,
            "docs": cls.docs,
            "colors": r_colors,
            "color": color_val,
            "scope": scope_name,
            "is_structural": cls.is_structural,
            "ignore": cls.ignore,
            "suggestions": r_sugg,
            "suggestions_autocomplete": cls.suggestions_autocomplete,
            "queries": r_queries,
            "hints": r_hints,
            "contain_grammar": cls.contain_grammar(),
            "grammar": cls.grammar,
        }


RuleType = type[RuleItem] | str

__all__ = [
    "AutoCode",
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "SetCode",
]