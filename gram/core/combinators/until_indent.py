"""
Until Indentation Combinator (`gram.core.combinators.until_indent`).
===================================================================
Provides the `UntilIndent` combinator, which sequentially consumes tokens until
an indentation change matching a target level (absolute or relative) is reached.
"""
from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer import Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.control import ParseState


class UntilIndent(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.UNTIL_INDENT
    """
    Combinator that sequentially consumes tokens until an indentation transition
    matches the specified target level or relative direction.

    Modes:
        - `UntilIndent(N: int)`: Consumes until reaching indentation level `N` (e.g. `0`).
        - `UntilIndent("back")`: Consumes until reaching any indentation lower than the
          current level (dedentation / `DEDENT`).
        - `UntilIndent("front")`: Consumes until reaching any indentation higher than the
          current level (indentation / `INDENT`).

    Args:
        target (int | Literal["back", "front"] | str): Target level integer (>= 0) or
            relative direction ("back" / "front").
        consume_target (bool): If True, consumes and includes the target INDENT/DEDENT
            token in the result. If False (default), leaves it in the parser cursor.
        allow_eof (bool): If True, reaching EOF without encountering the target
            is treated as successfully closing the block.
        max_tokens (int | None): Optional upper limit on tokens consumed.
    """

    header_class: bool = True

    def __init__(
        self,
        target: int | Literal["back", "front"] | str,
        *,
        consume_target: bool = False,
        allow_eof: bool = False,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__()
        if isinstance(target, str):
            target_clean = target.lower().strip()
            if target_clean not in ("back", "front"):
                raise errors.GrammarError(
                    "InvalidUntilIndentTarget",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"El modo relativo de UntilIndent debe ser 'back' o 'front', se recibió '{target}'.",
                    "Especifique un número entero >= 0 o una de las opciones relativas: 'back', 'front'.",
                )
            self.target: int | str = target_clean
        elif isinstance(target, int):
            if target < 0:
                raise errors.GrammarError(
                    "InvalidUntilIndentTarget",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"El nivel de indentación en UntilIndent debe ser >= 0, se recibió {target}.",
                    "Especifique un nivel entero no negativo (ej. 0, 4, 8) o 'back' / 'front'.",
                )
            self.target = target
        else:
            raise errors.GrammarError(
                "InvalidUntilIndentTarget",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"Tipo de objetivo inválido para UntilIndent: {type(target).__name__}.",
                "UntilIndent acepta un entero (ej. 0) o un modo relativo ('back', 'front').",
            )

        self.consume_target: bool = consume_target
        self.allow_eof: bool = allow_eof
        self.max_tokens: int | None = max_tokens

    @staticmethod
    def _get_current_indent_level(parser: ParseState) -> int:
        """
        Determine the active indentation level at the current parser cursor
        by scanning backwards for the most recent INDENT or DEDENT token.
        """
        return parser.current_indent_level()

    def _matches_condition(self, tok: TokenType, initial_level: int) -> bool:
        """Evaluate if candidate token `tok` fulfills the indentation stopping condition."""
        if self.target == "back":
            return tok.token == Token.DEDENT and (
                tok.value is None or tok.value < initial_level
            )

        if self.target == "front":
            return tok.token == Token.INDENT and (
                tok.value is None or tok.value > initial_level
            )

        if isinstance(self.target, int):
            if tok.token == Token.DEDENT:
                return tok.value == self.target or (
                    initial_level > self.target and tok.value <= self.target
                )
            if tok.token == Token.INDENT:
                return tok.value == self.target or (
                    initial_level < self.target and tok.value >= self.target
                )

        return False

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Consume tokens sequentially until an indentation event matches `self.target`.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingUntilIndent", "Procesando consumo UntilIndent", set_target=True
        )
        initial_checkpoint = parser.savepoint("UNTILINDENT-Analysis")
        collected: list[Any] = []
        initial_level = self._get_current_indent_level(parser)

        try:
            while not parser.is_eof():
                tok = parser.peek()
                if tok is None or tok.token == Token.EOF:
                    break

                if self._matches_condition(tok, initial_level):
                    if self.consume_target:
                        consumed_tok = parser.consume()
                        if consumed_tok is not None:
                            node = analyzer.delegate_return_node(consumed_tok)
                            if node is not None:
                                collected.append(node)

                    father.note(
                        f"UntilIndent({self.target!r}) encontró indentación objetivo tras {len(collected)} elementos.",
                        "success",
                    )
                    return collected

                if self.max_tokens is not None and len(collected) >= self.max_tokens:
                    break

                consumed = parser.consume()
                if consumed is None:
                    break
                node = analyzer.delegate_return_node(consumed)
                if node is not None:
                    collected.append(node)

            # EOF reached without explicit indent match
            if self.allow_eof and parser.is_eof():
                father.note(
                    f"UntilIndent({self.target!r}) alcanzó EOF con allow_eof=True.",
                    "success",
                )
                return collected

            failed_pos = parser.pos
            parser.restore(initial_checkpoint)
            father.note(
                f"UntilIndent({self.target!r}) alcanzó el límite o EOF sin encontrar el objetivo.",
                "error",
            )
            analyzer.report_error(
                errors.GrammarError(
                    "UntilIndentTargetNotFound",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"UntilIndent({self.target!r}) alcanzó el final sin encontrar el nivel de indentación esperado.",
                    "Asegúrese de que el bloque termine con la indentación o dedentación esperada.",
                ),
                pos=failed_pos,
            )
            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return (
            f"UntilIndent({self.target!r}, "
            f"consume_target={self.consume_target}, allow_eof={self.allow_eof})"
        )


__all__ = ["UntilIndent"]
