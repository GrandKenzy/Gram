"""
Lexical WordGroup Matching Combinator (`gram.core.combinators.match.match_group`).
==================================================================================
Validates whether the token currently under the parser cursor belongs to a
registered semantic `WordGroup` in `gram.core.lexer.words` (e.g., `'$TYPES'`,
`'$MODIFIERS'`), supporting optional allow/deny value filters.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer import words
from gram.core.lexer.words import WordGroup

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class MatchGroup(Combinator):
    """
    Combinator that evaluates whether the current token belongs to a lexical
    `WordGroup`, with optional `'allow'` or `'deny'` filtering over specific values.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.TERMINAL_GROUP

    def __init__(
        self,
        group: str | WordGroup,
        values: Iterable[str] | None = None,
        behavior_values: Literal["allow", "deny", "none"] = "none",
    ) -> None:
        """
        Initialize the lexical group matcher.

        Args:
            group (str | WordGroup): Target group name or `WordGroup` instance.
            values (Iterable[str] | None): Optional collection of token values to
                filter according to `behavior_values`.
            behavior_values (Literal['allow', 'deny', 'none']): Filter mode:
                - `'none'`: Accept any member of `group`.
                - `'allow'`: Only accept group members present in `values`.
                - `'deny'`: Reject group members present in `values`.
        """
        super().__init__()
        self.group: str = group.name if isinstance(group, WordGroup) else str(group)
        self.values: frozenset[str] = (
            frozenset(values) if values is not None else frozenset()
        )
        self.behavior_values: Literal["allow", "deny", "none"] = behavior_values

    def parse(self, analyzer: ASTAnalyzer) -> Any | None:
        """
        Evaluate whether the current token belongs to `self.group` and satisfies
        the configured `behavior_values` filter.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any | None: Delegated AST node if matched, or `None` on mismatch.
        """
        parser = analyzer.parser
        parser.node("ProcessingMatchGroup", "Procesando Match Grupal", set_target=True)
        parser.debug(f"MatchGroup: buscando pertenencia al grupo {self.group!r}")
        try:
            if parser.empty():
                parser.error("Salida inesperada. No se encontró ningún Token.")
                analyzer.report_error(
                    errors.ParserError(
                        "EmptyTokenStream",
                        errors.PARSER_EARLY_EOF,
                        f"Salida inesperada (EOF) al buscar un elemento del grupo {self.group!r}.",
                        "Verifique que la expresión no esté incompleta.",
                    ),
                    pos=parser.pos,
                )
                return None

            current = parser.peek()

            if current is None:
                return None

        
            session = self.get_session(analyzer)
            in_group = (
                session.exists_in_group(current.value, self.group)
                if session is not None
                else words.exists_in_group(current.value, self.group)
            )
            group_exists = (
                session.group_exists(self.group)
                if session is not None
                else words.group_exists(self.group)
            )
            if not in_group:
                if not group_exists:
                    parser.error(f"El grupo {self.group} no existe.")
                    analyzer.report_error(
                        errors.LexerError(
                            "WordGroupNotFound",
                            errors.LEXER_WORDGROUP_NOT_FOUND,
                            f"El grupo léxico {self.group!r} no existe en el registro.",
                            f"Line: {current.line}, Col: {current.col}",
                        ),
                        pos=parser.pos,
                    )
                else:
                    parser.error(
                        f"La keyword {current.value} no existe en el grupo {self.group}."
                    )
                    analyzer.report_error(
                        errors.ParserError(
                            "GroupMismatch",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"El valor {current.value!r} no pertenece al grupo {self.group!r}.",
                            f"Line: {current.line}, Col: {current.col}",
                        ),
                        pos=parser.pos,
                    )
                return None

            if self.behavior_values == "allow" and current.value not in self.values:
                parser.error(
                    f"El valor {current.value!r} no está en la lista permitida de MatchGroup({self.group!r})."
                )
                analyzer.report_error(
                    errors.ParserError(
                        "GroupValueNotAllowed",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"El valor {current.value!r} pertenece a {self.group!r}, pero no está entre los valores permitidos.",
                        f"Line: {current.line}, Col: {current.col}",
                    ),
                    pos=parser.pos,
                )
                return None

            if self.behavior_values == "deny" and current.value in self.values:
                parser.error(
                    f"El valor {current.value!r} está explícitamente excluido en MatchGroup({self.group!r})."
                )
                analyzer.report_error(
                    errors.ParserError(
                        "GroupValueDenied",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"El valor {current.value!r} está excluido para esta regla del grupo {self.group!r}.",
                        f"Line: {current.line}, Col: {current.col}",
                    ),
                    pos=parser.pos,
                )
                return None
            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return analyzer.delegate_return_node(current)
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"MatchGroup({self.group!r})"


__all__ = ["MatchGroup"]
