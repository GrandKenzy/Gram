"""Static predictability analysis for ordered alternatives.

The analyzer in this module never executes a combinator.  It computes only
conservative token-consumption metadata so ``Alt(audit=True)`` can reuse a
compiled order without changing the default ordered-choice semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from gram.core.combinators.base import Combinator

FirstAtom = tuple[str, str]
Certainty = Literal["exact", "partial", "unknown"]
EffectKind = Literal["pure", "checkpointed", "opaque"]


@dataclass(frozen=True, slots=True)
class PredictiveProfile:
    """Conservative static profile for one combinator.

    ``None`` denotes an unknown bound or property.  ``max_tokens=None`` also
    covers unbounded repetition; callers must inspect ``certainty`` before
    treating a profile as exact.
    """

    min_tokens: int | None
    max_tokens: int | None
    nullable: bool | None
    first_set: frozenset[FirstAtom] | None
    certainty: Certainty = "unknown"
    effects: EffectKind = "opaque"
    has_cut: bool = False
    reasons: tuple[str, ...] = ()

    @property
    def reorderable(self) -> bool:
        """Return whether this profile is safe for audited reordering."""
        return (
            self.certainty == "exact"
            and self.effects == "pure"
            and not self.has_cut
            and self.min_tokens is not None
            and self.max_tokens is not None
            and self.nullable is False
            and self.first_set is not None
        )


@dataclass(frozen=True, slots=True)
class PredictivePlan:
    """Compiled order and profiles for one ``Alt`` instance."""

    order: tuple[int, ...]
    profiles: tuple[PredictiveProfile, ...]
    warnings: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether the compiled order differs from declaration order."""
        return self.order != tuple(range(len(self.profiles)))


def _unknown(reason: str) -> PredictiveProfile:
    return PredictiveProfile(
        min_tokens=None,
        max_tokens=None,
        nullable=None,
        first_set=None,
        certainty="unknown",
        effects="opaque",
        reasons=(reason,),
    )


def _zero(
    *,
    first_set: frozenset[FirstAtom] | None = frozenset(),
    certainty: Certainty = "exact",
    effects: EffectKind = "pure",
    reasons: tuple[str, ...] = (),
) -> PredictiveProfile:
    return PredictiveProfile(
        min_tokens=0,
        max_tokens=0,
        nullable=True,
        first_set=first_set,
        certainty=certainty,
        effects=effects,
        reasons=reasons,
    )


def _atomic(
    first_set: frozenset[FirstAtom] | None,
    *,
    certainty: Certainty = "exact",
    effects: EffectKind = "pure",
    reasons: tuple[str, ...] = (),
) -> PredictiveProfile:
    return PredictiveProfile(
        min_tokens=1,
        max_tokens=1,
        nullable=False,
        first_set=first_set,
        certainty=certainty,
        effects=effects,
        reasons=reasons,
    )


def _effect_kind(profiles: Iterable[PredictiveProfile]) -> EffectKind:
    effects = {profile.effects for profile in profiles}
    if "opaque" in effects:
        return "opaque"
    if "checkpointed" in effects:
        return "checkpointed"
    return "pure"


def _certainty(profiles: Iterable[PredictiveProfile]) -> Certainty:
    values = {profile.certainty for profile in profiles}
    if "unknown" in values:
        return "unknown"
    if "partial" in values:
        return "partial"
    return "exact"


def _reasons(profiles: Iterable[PredictiveProfile]) -> tuple[str, ...]:
    values: list[str] = []
    for profile in profiles:
        for reason in profile.reasons:
            if reason not in values:
                values.append(reason)
    return tuple(values)


def _seq_profile(profiles: tuple[PredictiveProfile, ...]) -> PredictiveProfile:
    if not profiles:
        return _zero()

    min_tokens: int | None = 0
    max_tokens: int | None = 0
    for profile in profiles:
        if min_tokens is None or profile.min_tokens is None:
            min_tokens = None
        else:
            min_tokens += profile.min_tokens
        if max_tokens is None or profile.max_tokens is None:
            max_tokens = None
        else:
            max_tokens += profile.max_tokens

    nullable: bool | None = True
    first: set[FirstAtom] | None = set()
    for profile in profiles:
        if nullable is not True:
            break
        if profile.first_set is None:
            first = None
        elif first is not None:
            first.update(profile.first_set)
        if profile.nullable is False:
            nullable = False
        elif profile.nullable is None:
            nullable = None

    if all(profile.nullable is True for profile in profiles):
        nullable = True

    return PredictiveProfile(
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        nullable=nullable,
        first_set=None if first is None else frozenset(first),
        certainty=_certainty(profiles),
        effects=_effect_kind(profiles),
        has_cut=any(profile.has_cut for profile in profiles),
        reasons=_reasons(profiles),
    )


def _alt_profile(profiles: tuple[PredictiveProfile, ...]) -> PredictiveProfile:
    if not profiles:
        return _unknown("empty alternative set")

    min_values = [profile.min_tokens for profile in profiles]
    max_values = [profile.max_tokens for profile in profiles]
    min_tokens = min(min_values) if all(value is not None for value in min_values) else None
    max_tokens = max(max_values) if all(value is not None for value in max_values) else None

    if any(profile.nullable is True for profile in profiles):
        nullable: bool | None = True
    elif any(profile.nullable is None for profile in profiles):
        nullable = None
    else:
        nullable = False

    first: set[FirstAtom] | None = set()
    for profile in profiles:
        if profile.first_set is None:
            first = None
            break
        first.update(profile.first_set)

    return PredictiveProfile(
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        nullable=nullable,
        first_set=None if first is None else frozenset(first),
        certainty=_certainty(profiles),
        effects=_effect_kind(profiles),
        has_cut=any(profile.has_cut for profile in profiles),
        reasons=_reasons(profiles),
    )


class _Analyzer:
    """Memoized, cycle-safe implementation of the static analyzer."""

    def __init__(self) -> None:
        self.memo: dict[int, PredictiveProfile] = {}
        self.active: set[int] = set()

    def visit(self, combinator: Combinator) -> PredictiveProfile:
        if not isinstance(combinator, Combinator):
            return _unknown("non-combinator child")

        key = id(combinator)
        if key in self.memo:
            return self.memo[key]
        if key in self.active:
            return _unknown(f"recursive reference through {combinator.type()}")

        self.active.add(key)
        try:
            profile = self._visit(combinator)
        finally:
            self.active.remove(key)
        self.memo[key] = profile
        return profile

    def _visit(self, combinator: Combinator) -> PredictiveProfile:
        # Imports are intentionally local: the combinator package imports Alt,
        # while Alt imports this module for its lazy audit plan.
        from gram.core.combinators.alternative import Alt
        from gram.core.combinators.convert import Convert
        from gram.core.combinators.enclosed import Enclosed
        from gram.core.combinators.error_combinator import ErrorCombinator
        from gram.core.combinators.expected import Expected
        from gram.core.combinators.item import Item
        from gram.core.combinators.load import Load
        from gram.core.combinators.many import Many
        from gram.core.combinators.match import (
            MatchGroup,
            MatchKeyword,
            MatchSeqSymbol,
            MatchToken,
        )
        from gram.core.combinators.negation import Not
        from gram.core.combinators.optional import Opt
        from gram.core.combinators.peek import Peek
        from gram.core.combinators.preprocess import Preprocess
        from gram.core.combinators.reference import Ref
        from gram.core.combinators.req import Req
        from gram.core.combinators.save import Save
        from gram.core.combinators.separator import Separator
        from gram.core.combinators.sequence import Seq
        from gram.core.combinators.signals import CutFlowSignal
        from gram.core.combinators.skip import Skip
        from gram.core.combinators.some import Some
        from gram.core.combinators.tag import Tag
        from gram.core.combinators.tokenize import Tokenize
        from gram.core.combinators.until import Until
        from gram.core.combinators.until_indent import UntilIndent

        if isinstance(combinator, MatchKeyword):
            return _atomic(frozenset({("keyword", combinator.keyword)}))

        if isinstance(combinator, MatchToken):
            token = combinator.token
            name = getattr(token, "name", str(token))
            return _atomic(frozenset({("token", str(name))}))

        if isinstance(combinator, MatchGroup):
            return _atomic(
                None,
                certainty="partial",
                reasons=("lexical group membership is session-dependent",),
            )

        if isinstance(combinator, MatchSeqSymbol):
            effects: EffectKind = (
                "checkpointed" if combinator.custom_token_name else "pure"
            )
            return _atomic(
                None,
                certainty="partial",
                effects=effects,
                reasons=("symbol pattern has no static first-token set",),
            )

        if isinstance(combinator, Req):
            first = frozenset({("token", combinator.target_token)})
            if combinator._operations:
                return _atomic(
                    first,
                    certainty="partial",
                    effects="opaque",
                    reasons=("Req contains user-defined validation or transformation",),
                )
            return _atomic(first)

        if isinstance(combinator, Ref):
            entrypoint = getattr(combinator.rule, "entrypoint", None)
            if entrypoint is None:
                return _unknown("reference has no entrypoint")
            return self.visit(entrypoint)

        if isinstance(combinator, (Seq, Item)):
            children = (
                combinator.combinators
                if isinstance(combinator, Seq)
                else combinator.matchs
            )
            return _seq_profile(tuple(self.visit(child) for child in children))

        if isinstance(combinator, Tokenize):
            return _seq_profile(tuple(self.visit(child) for child in combinator.combinators))

        if isinstance(combinator, Alt):
            return _alt_profile(tuple(self.visit(child) for child in combinator.combinators))

        if isinstance(combinator, Enclosed):
            inner = self.visit(combinator.content)
            first = frozenset({("token", combinator.open_token.name)})
            min_tokens = None if inner.min_tokens is None else inner.min_tokens + 2
            max_tokens = None if inner.max_tokens is None else inner.max_tokens + 2
            return PredictiveProfile(
                min_tokens=min_tokens,
                max_tokens=max_tokens,
                nullable=False,
                first_set=first,
                certainty=inner.certainty,
                effects="checkpointed",
                has_cut=inner.has_cut,
                reasons=inner.reasons,
            )

        if isinstance(combinator, Opt):
            inner = self.visit(combinator.combinator)
            return PredictiveProfile(
                min_tokens=0,
                max_tokens=inner.max_tokens,
                nullable=True,
                first_set=inner.first_set,
                certainty="partial" if inner.certainty == "exact" else inner.certainty,
                effects="opaque",
                has_cut=inner.has_cut,
                reasons=inner.reasons + ("optional branch can succeed without consuming",),
            )

        if isinstance(combinator, Many):
            inner = self.visit(combinator.combinator)
            return PredictiveProfile(
                min_tokens=0,
                max_tokens=None,
                nullable=True,
                first_set=inner.first_set,
                certainty="partial" if inner.certainty == "exact" else inner.certainty,
                effects="opaque",
                has_cut=inner.has_cut,
                reasons=inner.reasons + ("repetition is unbounded",),
            )

        if isinstance(combinator, Some):
            inner = self.visit(combinator.combinator)
            return PredictiveProfile(
                min_tokens=inner.min_tokens,
                max_tokens=None,
                nullable=inner.nullable,
                first_set=inner.first_set,
                certainty="partial" if inner.certainty == "exact" else inner.certainty,
                effects="opaque",
                has_cut=inner.has_cut,
                reasons=inner.reasons + ("repetition is unbounded",),
            )

        if isinstance(combinator, (Peek, Not)):
            inner = self.visit(combinator.combinator)
            return _zero(
                first_set=inner.first_set,
                certainty="partial" if inner.certainty == "exact" else inner.certainty,
                effects="opaque",
                reasons=inner.reasons + ("lookahead does not consume tokens",),
            )

        if isinstance(combinator, Expected):
            return _zero(
                first_set=None,
                certainty="partial",
                reasons=("Expected inspects parser state without consuming",),
            )

        if isinstance(combinator, Save):
            if combinator.matcher is not None and combinator.consume:
                inner = self.visit(combinator.matcher)
                return PredictiveProfile(
                    min_tokens=inner.min_tokens,
                    max_tokens=inner.max_tokens,
                    nullable=inner.nullable,
                    first_set=inner.first_set,
                    certainty="partial",
                    effects="opaque",
                    has_cut=inner.has_cut,
                    reasons=inner.reasons + ("Save mutates parser storage",),
                )
            return _zero(
                first_set=None,
                certainty="partial",
                effects="opaque",
                reasons=("Save mutates parser storage without consuming",),
            )

        if isinstance(combinator, Load):
            return _unknown("Load can read or mutate parser storage")

        if isinstance(combinator, (Convert, Tag, Preprocess, ErrorCombinator)):
            return _zero(
                first_set=None,
                certainty="partial",
                effects="opaque",
                reasons=(f"{combinator.type()} has parser or user side effects",),
            )

        if isinstance(combinator, Skip):
            has_cut = combinator.signal is CutFlowSignal
            return PredictiveProfile(
                min_tokens=0,
                max_tokens=0,
                nullable=True,
                first_set=None,
                certainty="partial",
                effects="opaque",
                has_cut=has_cut,
                reasons=("flow-control signal changes alternative semantics",),
            )

        if isinstance(combinator, (Separator, Until, UntilIndent)):
            return _unknown(f"{combinator.type()} has variable consumption")

        return _unknown(f"unsupported combinator type: {combinator.type()}")


def analyze_predictability(combinator: Combinator) -> PredictiveProfile:
    """Return a conservative static profile without executing ``parse``."""
    return _Analyzer().visit(combinator)


def compile_predictive_plan(
    combinators: Iterable[Combinator],
) -> PredictivePlan:
    """Compile a stable, conservative order for an alternative set.

    Only contiguous exact, non-nullable, side-effect-free branches are sorted.
    Every other branch remains in its declared position relative to opaque
    branches, preserving the historical ordered-choice behavior.
    """
    children = tuple(combinators)
    analyzer = _Analyzer()
    profiles = tuple(analyzer.visit(child) for child in children)
    order = list(range(len(children)))
    warnings: list[str] = []

    run: list[int] = []

    def flush() -> None:
        if len(run) > 1:
            ordered = sorted(
                run,
                key=lambda index: (
                    -(profiles[index].min_tokens or 0),
                    len(profiles[index].first_set or ()),
                    index,
                ),
            )
            for destination, source in zip(run, ordered):
                order[destination] = source
        run.clear()

    for index, profile in enumerate(profiles):
        if profile.reorderable:
            run.append(index)
        else:
            flush()
            reason = profile.reasons[0] if profile.reasons else "profile is not exact"
            warnings.append(f"alternative {index} kept in declaration order: {reason}")
    flush()

    if order != list(range(len(children))):
        warnings.append(f"audited order: {tuple(order)!r}")

    return PredictivePlan(tuple(order), profiles, tuple(warnings))


def audit_alternatives(combinators: object) -> PredictivePlan:
    """Analyze an ``Alt`` instance or an iterable of alternative combinators."""
    children = getattr(combinators, "combinators", combinators)
    return compile_predictive_plan(children)  # type: ignore[arg-type]


__all__ = [
    "FirstAtom",
    "PredictivePlan",
    "PredictiveProfile",
    "analyze_predictability",
    "audit_alternatives",
    "compile_predictive_plan",
]
