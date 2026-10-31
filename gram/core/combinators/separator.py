"""
Separator Combinator (`gram.core.combinators.separator`).
=========================================================
Provides the `Separator` combinator for parsing delimited element sequences
(such as comma-separated arguments or semicolon-separated statements)
with configurable minimum/maximum bounds and trailing separator support,
returning an `ArrayNode`.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, TYPE_CHECKING, Any

from gram import errors
from gram.core.ast.nodes import ASTNode, ArrayNode
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.kinds import CombinatorKind
from gram.core.combinators.match import MatchSeqSymbol, MatchToken
from gram.core.combinators.reference import Ref
from gram.core.combinators.signals import BreakFlowSignal, SkipFlowSignal
from gram.core.lexer.tokens import MAP_SYMBOLS, Token

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


def _normalize_sep(sep: Combinator | Token | str) -> Combinator:
    """Normalize the delimiter argument into a valid Combinator instance."""
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
        return MatchSeqSymbol(sep)

    errors.GrammarError(
        "UnsupportedSeparatorDelimiter",
        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
        f"Delimitador no permitido en Separator: {sep!r} ({type(sep).__name__}).",
        "Pase un Token, cadena o Combinator como delimitador.",
    ).raise_error()


def _normalize_values(
    combinator_name: str,
    values: Sequence[Any] | Combinator | Token | type[RuleItem] | str,
) -> tuple[Combinator, ...]:
    """Normalize candidate element specifications into a tuple of Combinator instances."""
    flattened: list[Any] = []
    if isinstance(values, (list, tuple, set, frozenset)):
        for item in values:
            if isinstance(item, (list, tuple, set, frozenset)):
                flattened.extend(item)
            else:
                flattened.append(item)
    else:
        flattened.append(values)

    normalized: list[Combinator] = []
    for spec in flattened:
        if isinstance(spec, type) and issubclass(spec, RuleItem):
            spec = Ref(spec)

        if isinstance(spec, Ref):
            if not spec.name or not spec.name.strip():
                errors.GrammarError(
                    "UnnamedRefInSeparator",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"El combinador {combinator_name} recibió un Ref({spec.rule_name!r}) que no genera nodo ASTRef (name=None y nodeable=False).",
                    f"Active 'nodeable = True' en la regla {spec.rule_name!r} o pase un nombre explícito: Ref({spec.rule_name}, name='alias').",
                ).raise_error()
            normalized.append(spec)
        elif isinstance(spec, MatchToken):
            normalized.append(spec)
        elif isinstance(spec, Token):
            normalized.append(MatchToken(spec))
        elif isinstance(spec, Combinator):
            normalized.append(spec)
        elif isinstance(spec, str):
            tok_enum = Token.from_string(spec)
            if tok_enum is not None:
                normalized.append(MatchToken(tok_enum))
            elif spec in MAP_SYMBOLS:
                normalized.append(MatchToken(MAP_SYMBOLS[spec]))
            else:
                errors.GrammarError(
                    "InvalidSeparatorTokenName",
                    errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                    f"El nombre '{spec}' no corresponde a ningún Token válido en {combinator_name}.",
                    "Pase miembros del enum Token o combinadores Ref(nodeable=True) en 'values'.",
                ).raise_error()
        else:
            errors.GrammarError(
                "UnsupportedSeparatorValue",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"Valor no permitido en la configuración de Separator: {spec!r} ({type(spec).__name__}).",
                "Separator solo admite miembros de Token, reglas RuleItem(nodeable=True) y combinadores Ref(..., name='...').",
            ).raise_error()

    return tuple(normalized)


class Separator(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.SEPARATOR
    """
    Delimited repetition combinator matching elements separated by a delimiter.

    Supports minimum and maximum occurrence constraints as well as optional
    trailing delimiters, returning an `ArrayNode` on success.
    """

    header_class: bool = True

    def __init__(
        self,
        values: Sequence[Any] | Combinator | Token | type[RuleItem] | str,
        sep: Combinator | Token | str = Token.COMMA,
        min: int = 0,
        max: int | None = None,
        allow_trailing: bool = True,
    ) -> None:
        """
        Initialize the delimited repetition combinator.

        Args:
            values: Allowed element combinator(s), rule(s), or token(s).
            sep: Delimiter combinator, token, or string (defaults to `Token.COMMA`).
            min: Minimum required number of matched elements.
            max: Maximum allowed number of matched elements (`None` for unbounded).
            allow_trailing: If True, permits a trailing delimiter after the final element.
        """
        super().__init__()
        self.values: tuple[Combinator, ...] = _normalize_values(self.type(), values)
        self.sep: Combinator = _normalize_sep(sep)
        self.min: int = min
        self.max: int | None = max
        self.allow_trailing: bool = allow_trailing

    def _match_val(self, analyzer: ASTAnalyzer) -> Any:
        """Attempt to match the current token position against any candidate in `self.values`."""
        parser = analyzer.parser
        saved = parser.savepoint("SEP-Value")
        best_failure = None

        for idx, val_comb in enumerate(self.values):
            if idx > 0:
                parser.restore(saved)
            try:
                with analyzer.failure_scope() as attempt:
                    res = analyzer.visitor(val_comb)
            except errors.Error:
                res = None

            if res is not None:
                if attempt.candidate is not None and attempt.candidate[0] > parser.pos:
                    weight, err = attempt.candidate
                    analyzer.stage_failure(err, weight=weight)
                return res
            if attempt.candidate is not None and (
                best_failure is None or attempt.candidate[0] > best_failure[0]
            ):
                best_failure = attempt.candidate

        parser.restore(saved)
        if best_failure is not None:
            weight, err = best_failure
            analyzer.stage_failure(err, weight=weight)
        return None

    def parse(self, analyzer: ASTAnalyzer) -> ArrayNode | None:
        """
        Parse a sequence of elements separated by `self.sep`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            ArrayNode | None: `ArrayNode` containing matched elements and trailing flag,
            or `None` if fewer than `self.min` elements were matched.
        """
        with analyzer.failure_scope() as scope:
            result, publish_failure = self._parse_items(analyzer)

        if scope.candidate is not None:
            weight, err = scope.candidate
            if publish_failure and not analyzer.in_failure_context:
                with analyzer.failure_scope():
                    analyzer.stage_failure(err, weight=weight)
                    analyzer.flush_failure()
            else:
                analyzer.stage_failure(err, weight=weight)
        return result

    def _parse_items(self, analyzer: ASTAnalyzer) -> tuple[ArrayNode | None, bool]:
        """Match a list while keeping candidate and delimiter attempts isolated."""
        parser = analyzer.parser
        father = parser.node(
            "ProcessingSeparator", "Procesando separador", set_target=True
        )
        father.note("Iniciando evaluación de Separator", "normal")

        initial_checkpoint = parser.savepoint("SEP-Analysis")
        items: list[Any] = []
        trailing_sep = False
        publish_failure = False

        try:
            # 1. Attempt to match the first value
            with analyzer.failure_scope() as first_attempt:
                first_val = self._match_val(analyzer)
            if first_val is None:
                parser.restore(initial_checkpoint)
                if first_attempt.candidate is not None:
                    weight, err = first_attempt.candidate
                    analyzer.stage_failure(err, weight=weight)
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
                    analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)
                    return None, True

                analyzer.discard_staged_failure(min_weight=parser.pos)
                return ArrayNode([], trailing=False), False

            items.append(first_val)
            if first_attempt.candidate is not None and first_attempt.candidate[0] > parser.pos:
                weight, err = first_attempt.candidate
                analyzer.stage_failure(err, weight=weight)

            # 2. Match subsequent delimiter + value pairs
            while True:
                if self.max is not None and len(items) >= self.max:
                    break
                if parser.empty():
                    break

                sep_checkpoint = parser.savepoint("SEP-Separator")
                try:
                    with analyzer.failure_scope() as sep_attempt:
                        sep_res = analyzer.visitor(self.sep)
                except (SkipFlowSignal, BreakFlowSignal):
                    parser.restore(sep_checkpoint)
                    break
                except errors.Error:
                    sep_res = None

                if sep_res is None:
                    parser.restore(sep_checkpoint)
                    if sep_attempt.candidate is not None:
                        weight, err = sep_attempt.candidate
                        analyzer.stage_failure(err, weight=weight)
                    break

                if parser.empty():
                    if self.allow_trailing:
                        trailing_sep = True
                        if sep_attempt.candidate is not None and sep_attempt.candidate[0] > parser.pos:
                            weight, err = sep_attempt.candidate
                            analyzer.stage_failure(err, weight=weight)
                        break
                    parser.restore(sep_checkpoint)
                    if sep_attempt.candidate is not None:
                        weight, err = sep_attempt.candidate
                        analyzer.stage_failure(err, weight=weight)
                    break

                val_checkpoint = parser.savepoint("SEP-NextValue")
                with analyzer.failure_scope() as val_attempt:
                    val_res = self._match_val(analyzer)

                if val_res is not None:
                    items.append(val_res)
                    trailing_sep = False
                    for candidate in (sep_attempt.candidate, val_attempt.candidate):
                        if candidate is not None and candidate[0] > parser.pos:
                            weight, err = candidate
                            analyzer.stage_failure(err, weight=weight)
                    analyzer.discard_staged_failure(min_weight=parser.pos)
                else:
                    if self.allow_trailing:
                        parser.restore(val_checkpoint)
                        trailing_sep = True
                        for candidate in (sep_attempt.candidate, val_attempt.candidate):
                            if candidate is not None and candidate[0] > parser.pos:
                                weight, err = candidate
                                analyzer.stage_failure(err, weight=weight)
                        break
                    parser.restore(sep_checkpoint)
                    for candidate in (sep_attempt.candidate, val_attempt.candidate):
                        if candidate is not None:
                            weight, err = candidate
                            analyzer.stage_failure(err, weight=weight)
                            publish_failure |= weight > val_checkpoint.pos
                    break

            if len(items) < self.min:
                parser.restore(initial_checkpoint)
                fallback = errors.GrammarError(
                    "InsufficientSeparatorElements",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Se requerían al menos {self.min} elementos en Separator, pero se obtuvieron {len(items)}.",
                    "Asegúrese de completar la lista de elementos separados.",
                )
                analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)
                return None, True

            father.note(
                f"Separator completado: {len(items)} elemento(s), trailing={trailing_sep}",
                "success",
            )
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return ArrayNode(items, trailing=trailing_sep), publish_failure
        finally:
            parser.down()

    def __repr__(self) -> str:
        return (
            f"Separator(values={self.values!r}, sep={self.sep!r}, "
            f"min={self.min}, max={self.max}, allow_trailing={self.allow_trailing})"
        )


__all__ = ["ArrayNode", "Separator"]
