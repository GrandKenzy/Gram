"""
Separator Combinator (`gram.core.combinators.separator`).
=========================================================
Provides the `Separator` combinator (and `Sep` alias) for parsing delimited
element sequences (such as comma-separated arguments or semicolon-separated
statements) with configurable minimum/maximum bounds and trailing separator support.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.item import ItemNode, Literal, LiteralNode
from gram.core.combinators.match import MatchSymbol, MatchToken
from gram.core.combinators.reference import Ref
from gram.core.combinators.signals import BreakFlowSignal, SkipFlowSignal
from gram.core.lexer.tokens import MAP_SYMBOLS, Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class SeparatorResult(list[Any]):
    """
    Result container for `Separator` combinator evaluations.

    Subclasses `list` and stores metadata indicating whether a trailing
    separator was consumed at the end of the sequence.
    """

    is_match: bool = True

    def __init__(
        self,
        items: Iterable[Any] | None = None,
        ended_token: TokenType | None = None,
        trailing_separator: bool = False,
    ) -> None:
        super().__init__(items if items is not None else [])
        self.ended_token: TokenType | None = ended_token
        self.trailing_separator: bool = trailing_separator

    def to_list(self) -> list[Any]:
        """Recursively convert nested `SeparatorResult`, `ItemNode`, and `LiteralNode` objects to plain Python lists."""
        result: list[Any] = []
        for item in self:
            if isinstance(item, SeparatorResult):
                result.append(item.to_list())
            elif isinstance(item, (ItemNode, LiteralNode)):
                result.append(list(item))
            else:
                result.append(item)
        return result

    @property
    def items(self) -> list[Any]:
        """Return a shallow copy of the matched elements as a standard list."""
        return list(self)

    def __bool__(self) -> bool:
        """Return True if at least one element was matched."""
        return len(self) > 0

    def __repr__(self) -> str:
        return (
            f"SeparatorResult({super().__repr__()}, "
            f"trailing={self.trailing_separator})"
        )


def _normalize_sep(sep: Any) -> Combinator:
    """Coerce a separator delimiter specification into a valid `Combinator` instance."""
    if isinstance(sep, Combinator):
        return sep
    if isinstance(sep, Token):
        return MatchToken(sep)
    if isinstance(sep, str):
        tok_enum = Token.from_string(sep)
        if tok_enum is not None:
            return MatchToken(tok_enum)
        if sep in MAP_SYMBOLS:
            return MatchToken(MAP_SYMBOLS[sep])
        return MatchSymbol(sep)
    return MatchToken(Token.COMMA)


class Separator(Combinator):
    """
    Delimited repetition combinator matching elements separated by a delimiter.

    Supports minimum and maximum occurrence constraints as well as optional
    trailing separators.
    """

    header_class: bool = True

    def __init__(
        self,
        values: Sequence[Any] | Combinator | Token | str,
        sep: Combinator | Token | str = Token.COMMA,
        min: int = 0,
        max: int | None = None,
        allow_trailing: bool = True,
    ) -> None:
        """
        Initialize the delimited repetition combinator.

        Args:
            values (Sequence[Any] | Combinator | Token | str): Allowed element combinator(s).
            sep (Combinator | Token | str): Delimiter combinator or token (defaults to `Token.COMMA`).
            min (int): Minimum required number of matched elements.
            max (int | None): Maximum allowed number of matched elements (`None` for unbounded).
            allow_trailing (bool): If True, permits a trailing delimiter after the final element.
        """
        super().__init__()

        flattened: list[Any] = []
        if isinstance(values, (list, tuple, set, frozenset)):
            for item in values:
                if isinstance(item, (list, tuple, set, frozenset)):
                    flattened.extend(item)
                else:
                    flattened.append(item)
        else:
            flattened.append(values)

        ref_list: list[Ref] = []
        tok_list: list[Combinator] = []

        for spec in flattened:
            if isinstance(spec, type) and issubclass(spec, RuleItem):
                spec = Ref(spec)

            if isinstance(spec, Ref):
                if not spec.name or not spec.name.strip():
                    errors.GrammarError(
                        "UnnamedRefInSeparator",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        f"El combinador {self.type()} recibió un Ref({spec.rule_name!r}) que no genera nodo ASTRef (name=None y nodeable=False).",
                        f"Active 'nodeable = True' en la regla {spec.rule_name!r} o pase un nombre explícito: Ref({spec.rule_name}, name='alias').",
                    ).raise_error()
                ref_list.append(spec)
            elif isinstance(spec, MatchToken):
                tok_list.append(spec)
            elif isinstance(spec, Token):
                tok_list.append(MatchToken(spec))
            elif isinstance(spec, str):
                tok_enum = Token.from_string(spec)
                if tok_enum is not None:
                    tok_list.append(MatchToken(tok_enum))
                elif spec in MAP_SYMBOLS:
                    tok_list.append(MatchToken(MAP_SYMBOLS[spec]))
                else:
                    errors.GrammarError(
                        "InvalidSeparatorTokenName",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        f"El nombre '{spec}' no corresponde a ningún Token válido en {self.type()}.",
                        "Pase miembros del enum Token o combinadores Ref(nodeable=True) en 'values'.",
                    ).raise_error()
            else:
                errors.GrammarError(
                    "UnsupportedSeparatorValue",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"Valor no permitido en la configuración de Separator: {spec!r} ({type(spec).__name__}).",
                    "Separator solo admite miembros de Token, reglas RuleItem(nodeable=True) y combinadores Ref(..., name='...').",
                ).raise_error()

        self.values: tuple[Combinator, ...] = tuple(ref_list + tok_list)
        self.sep: Combinator = _normalize_sep(sep)
        self.min: int = min
        self.max: int | None = max
        self.allow_trailing: bool = allow_trailing

    def _match_val(self, analyzer: ASTAnalyzer) -> Any:
        """Attempt to match the current token position against any candidate in `self.values`."""
        parser = analyzer.parser
        saved = parser.savepoint("SEP-Value")

        for idx, val_comb in enumerate(self.values):
            if idx > 0:
                parser.restore(saved)
            try:
                with analyzer.safe_mode():
                    res = analyzer.visitor(val_comb)
            except errors.Error:
                res = None

            if res is not None:
                analyzer.discard_staged_failure(min_weight=parser.pos)
                return res

        parser.restore(saved)
        return None

    def parse(self, analyzer: ASTAnalyzer) -> SeparatorResult | None:
        """
        Parse a sequence of elements separated by `self.sep`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            SeparatorResult | None: `SeparatorResult` containing matched elements,
            or `None` if fewer than `self.min` elements were matched.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingSeparator", "Procesando separador", set_target=True
        )
        father.note("Iniciando evaluación de Separator", "normal")

        initial_checkpoint = parser.savepoint("SEP-Analysis")
        items: list[Any] = []
        trailing_sep = False

        try:
            first_val = self._match_val(analyzer)
            if first_val is None:
                parser.restore(initial_checkpoint)
                if self.min > 0:
                    curr_tok = parser.peek() if not parser.empty() else None
                    tok_info = (
                        f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                        if curr_tok is not None
                        else ""
                    )
                    fallback = errors.GrammarError(
                        "InsufficientSeparatorElements",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        f"Separator requería al menos {self.min} elemento(s), pero no se encontró ninguno{tok_info}.",
                        "Proporcione al menos la cantidad mínima de elementos separados requerida.",
                    )
                    if analyzer.safe_flag:
                        analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)
                    else:
                        analyzer.flush_failure(fallback=fallback)
                    return None
                return SeparatorResult([], trailing_separator=False)

            items.append(first_val)

            while True:
                if self.max is not None and len(items) >= self.max:
                    break
                if parser.empty():
                    break

                sep_checkpoint = parser.savepoint("SEP-Separator")
                try:
                    with analyzer.safe_mode():
                        sep_res = analyzer.visitor(self.sep)
                except (SkipFlowSignal, BreakFlowSignal):
                    parser.restore(sep_checkpoint)
                    break
                except errors.Error:
                    sep_res = None

                if sep_res is None:
                    parser.restore(sep_checkpoint)
                    break

                if parser.empty():
                    if self.allow_trailing:
                        trailing_sep = True
                        break
                    parser.restore(sep_checkpoint)
                    break

                val_checkpoint = parser.savepoint("SEP-NextValue")
                val_res = self._match_val(analyzer)

                if val_res is not None:
                    items.append(val_res)
                    trailing_sep = False
                else:
                    if self.allow_trailing:
                        parser.restore(val_checkpoint)
                        trailing_sep = True
                        break
                    parser.restore(sep_checkpoint)
                    if analyzer.staged_weight > val_checkpoint.pos and not analyzer.safe_flag:
                        analyzer.flush_failure()
                    break

            if len(items) < self.min:
                parser.restore(initial_checkpoint)
                fallback = errors.GrammarError(
                    "InsufficientSeparatorElements",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Se requerían al menos {self.min} elementos en Separator, pero se obtuvieron {len(items)}.",
                    "Asegúrese de completar la lista de elementos separados.",
                )
                if analyzer.safe_flag:
                    analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)
                else:
                    analyzer.flush_failure(fallback=fallback)
                return None

            father.note(
                f"Separator completado: {len(items)} elemento(s), trailing={trailing_sep}",
                "success",
            )
            return SeparatorResult(items, trailing_separator=trailing_sep)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Separator(values={self.values!r}, sep={self.sep!r})"


Sep = Separator

__all__ = ["Sep", "Separator", "SeparatorResult"]