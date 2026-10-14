"""
Token Tagging Combinator (`gram.core.combinators.tag`) [BETA].
==============================================================
BETA FEATURE: Attaches, removes, or queries semantic tags on the current token
position inside the checkpoint-safe `parser.tk_tags` dictionary without creating
extra AST nodes or advancing the cursor.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer

TagMode = Literal["add", "remove", "exists", "not_exists"]


class Tag(Combinator):
    """
    [BETA] Zero-width combinator that manages semantic tags associated with the
    current token index (`parser.pos`) inside `parser.tk_tags`:

    - `'add'`: Adds `self.tag` to `parser.tk_tags[parser.pos]`.
    - `'remove'`: Removes `self.tag` from `parser.tk_tags[parser.pos]`.
    - `'exists'`: Succeeds only if `self.tag` is present on the current token.
    - `'not_exists'`: Succeeds only if `self.tag` is NOT present on the current token.
    """

    def __init__(
        self,
        tag: str,
        mode: TagMode = "add",
    ) -> None:
        """
        Initialize the `Tag` combinator [BETA].

        Args:
            tag (str): Semantic tag name to add, remove, or query.
            mode (TagMode): Operation mode (`'add'`, `'remove'`, `'exists'`, `'not_exists'`).
        """
        super().__init__()
        self.tag: str = tag
        self.mode: TagMode = mode

    # ==========================================================================
    # FLUENT BUILDERS / CONSTRUCTORS
    # ==========================================================================

    @classmethod
    def add(cls, tag: str) -> Tag:
        """Create a `Tag` combinator that adds `tag` to the current token."""
        return cls(tag, mode="add")

    @classmethod
    def remove(cls, tag: str) -> Tag:
        """Create a `Tag` combinator that removes `tag` from the current token."""
        return cls(tag, mode="remove")

    @classmethod
    def exists(cls, tag: str) -> Tag:
        """Create a `Tag` combinator that asserts `tag` exists on the current token."""
        return cls(tag, mode="exists")

    @classmethod
    def not_exists(cls, tag: str) -> Tag:
        """Create a `Tag` combinator that asserts `tag` does NOT exist on the current token."""
        return cls(tag, mode="not_exists")

    # Alias for antonym of exists
    unexists = not_exists

    def parse(self, analyzer: ASTAnalyzer) -> TokenType | None:
        """
        Execute the tag operation (`add`, `remove`, `exists`, or `not_exists`)
        at `parser.pos` without consuming the token.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingTag",
            f"[BETA] Ejecutando Tag('{self.tag}', mode='{self.mode}')",
            set_target=True,
        )

        try:
            if parser.empty():
                analyzer.report_error(
                    errors.ParserError(
                        "TagUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        f"Fin de archivo (EOF) al intentar ejecutar Tag('{self.tag}', mode='{self.mode}').",
                        "Verifique que exista un token bajo el cursor.",
                    ),
                    pos=parser.pos,
                )
                return None

            current = parser.peek()
            if current is None:
                return None

            pos = parser.pos
            current_tags = parser.tk_tags.get(pos, frozenset())

            if self.mode == "add":
                parser.tk_tags[pos] = current_tags | {self.tag}
                father.note(
                    f"Etiqueta '{self.tag}' añadida al token en pos={pos} ({current.value!r}).",
                    "success",
                )
                return current

            if self.mode == "remove":
                updated = current_tags - {self.tag}
                if updated:
                    parser.tk_tags[pos] = updated
                else:
                    parser.tk_tags.pop(pos, None)
                father.note(
                    f"Etiqueta '{self.tag}' eliminada del token en pos={pos}.",
                    "success",
                )
                return current

            if self.mode == "exists":
                if self.tag not in current_tags:
                    father.note(
                        f"Tag.exists('{self.tag}') falló en pos={pos}.", "warn"
                    )
                    analyzer.report_error(
                        errors.GrammarError(
                            "RequiredTagMissing",
                            errors.GRAMMAR_COMBINATOR_FAILED,
                            f"El token '{current.value}' en línea {current.line}, columna {current.col} "
                            f"no posee la etiqueta requerida '{self.tag}'.",
                            f"Asegúrese de que el token haya sido etiquetado previamente con Tag.add('{self.tag}').",
                        ),
                        pos=pos,
                    )
                    return None
                father.note(
                    f"Tag.exists('{self.tag}') verificado en pos={pos}.", "success"
                )
                return current

            if self.mode == "not_exists":
                if self.tag in current_tags:
                    father.note(
                        f"Tag.not_exists('{self.tag}') falló: la etiqueta sí existe en pos={pos}.",
                        "warn",
                    )
                    analyzer.report_error(
                        errors.GrammarError(
                            "ForbiddenTagPresent",
                            errors.GRAMMAR_COMBINATOR_FAILED,
                            f"El token '{current.value}' en línea {current.line}, columna {current.col} "
                            f"posee la etiqueta prohibida '{self.tag}'.",
                            f"El token en esta posición no debe tener activa la etiqueta '{self.tag}'.",
                        ),
                        pos=pos,
                    )
                    return None
                father.note(
                    f"Tag.not_exists('{self.tag}') verificado en pos={pos}.",
                    "success",
                )
                return current

            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Tag({self.tag!r}, mode={self.mode!r})"


__all__ = ["Tag", "TagMode"]