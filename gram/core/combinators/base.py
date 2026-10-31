"""
Base Classes for Syntactic Combinators and Rules (`gram.core.combinators.base`).
================================================================================
Defines the abstract `Combinator` base class, the `RuleMeta` metaclass, and the
declarative `RuleItem` base class for formal grammar production rules.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from gram import errors
from gram.core.combinators.kinds import CombinatorKind, get_combinator_kind, is_compilable_combinator, is_semantic_combinator
from gram.core.rules.codes import AutoCode, SetCode, code_manager

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer

_NON_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")
_PREDICTIVE_EPOCH = 0


def _touch_predictive_epoch() -> int:
    """Advance the process-local grammar mutation epoch."""
    global _PREDICTIVE_EPOCH
    _PREDICTIVE_EPOCH += 1
    return _PREDICTIVE_EPOCH


def _predictive_epoch() -> int:
    """Return the process-local grammar mutation epoch."""
    return _PREDICTIVE_EPOCH


class Combinator:
    """
    Abstract base class for all Gram Framework syntactic combinators.

    Each combinator encapsulates a declarative strategy for matching, consuming,
    branching, or repeating tokens across the parser's token stream.
    """

    combinator_kind: ClassVar[CombinatorKind | None] = None
    header_class: bool = False
    ignore: bool = False
    _predictive_revision: int = 0

    _PREDICTIVE_IGNORED_ATTRIBUTES = frozenset(
        {
            "_predictive_revision",
            "_predictive_plan",
            "_predictive_source",
            "_predictive_epoch",
            "_predictive_context",
            "header_class",
            "ignore",
            "audit",
        }
    )

    def __setattr__(self, name: str, value: Any) -> None:
        existed = hasattr(self, name)
        object.__setattr__(self, name, value)
        if not existed or name in self._PREDICTIVE_IGNORED_ATTRIBUTES:
            return
        revision = getattr(self, "_predictive_revision", 0) + 1
        object.__setattr__(self, "_predictive_revision", revision)
        _touch_predictive_epoch()

    def __init__(self, *args: Any, ignore: bool = False, **kwargs: Any) -> None:
        self.header_class: bool = self.__class__.header_class
        self.ignore: bool = ignore
        super().__init__()

    @staticmethod
    def get_session(analyzer: ASTAnalyzer):
        """Return the language session active for this combinator evaluation."""
        session = getattr(analyzer, "session", None)
        if session is not None:
            return session
        return getattr(getattr(analyzer, "parser", None), "session", None)

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

            audit = bool(getattr(self, "audit", False) or getattr(other, "audit", False))
            if isinstance(self, Alt):
                if isinstance(other, Alt):
                    return Alt(*(self.combinators + other.combinators), audit=audit)
                return Alt(*(self.combinators + (other,)), audit=audit)
            if isinstance(other, Alt):
                return Alt(self, *other.combinators, audit=audit)
            return Alt(self, other, audit=audit)
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

    Automatically resolves `name = 'auto'` (or omitted `name`) to the class
    identifier, allocates unique rule codes via `AutoCode`, and registers
    user-defined rules in `code_manager`.
    """

    entrypoint: Combinator | None = None
    name: str = ""
    code: int = 0
    nodeable: bool = True

    def __setattr__(cls, name: str, value: Any) -> None:
        previous = getattr(cls, name, None)
        super().__setattr__(name, value)
        if name == "entrypoint" and previous is not value:
            revision = getattr(cls, "_predictive_revision", 0) + 1
            super().__setattr__("_predictive_revision", revision)
            _touch_predictive_epoch()

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> type:
        # Avoid allocating an AutoCode for the base RuleItem class itself
        if not bases:
            return super().__new__(mcls, name, bases, namespace)

        raw_name = namespace.get("name")
        if raw_name == "auto" or not raw_name:
            namespace["name"] = name

        raw_code = namespace.get("code")
        if callable(raw_code):
            namespace["code"] = raw_code()
        elif not raw_code:
            namespace["code"] = AutoCode()

        cls = super().__new__(mcls, name, bases, namespace)
        type.__setattr__(cls, "_predictive_revision", 0)
        code_manager.register(cls.code, cls)
        return cls

    def __repr__(cls) -> str:
        return (
            f"{cls.__name__}("
            f"code={cls.code!r}, "
            f"name={cls.name or cls.__name__!r}, "
            f"nodeable={cls.nodeable!r}, "
            f"entrypoint={bool(cls.entrypoint)}"
            f")"
        )



from collections.abc import Callable
from typing import Any

SuggestionProvider = Callable[..., list[str]] | tuple[str, ...] | list[str]
TokenIndexKey = int | str  # Soporta 0, 1, -1, "this", "this:-1", "this:1"

class RuleItem(metaclass=RuleMeta):
    code: int = 0
    name: str = ""
    nodeable: bool = True
    description: str = ""
    entrypoint: Combinator | None = None
    _predictive_revision: int = 0

    # Mapas declarativos VSIX / LSP (requieren nodeable = True)
    colors: dict[TokenIndexKey, str] = {}
    autocomplete: dict[TokenIndexKey, str] = {}
    suggestions: dict[TokenIndexKey, SuggestionProvider] = {}
    hints: dict[TokenIndexKey, str] = {}
    playhints: dict[TokenIndexKey, str] = {}

    is_structural: bool = False
    ignore: bool = False
    no_simplify: bool = False

RuleType = type[RuleItem] | str

__all__ = [
    "AutoCode",
    "Combinator",
    "CombinatorKind",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "SetCode",
    "get_combinator_kind",
    "is_compilable_combinator",
    "is_semantic_combinator",
]
