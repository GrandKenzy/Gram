"""
Save Combinator (`gram.core.combinators.save`) [BETA].
======================================================
BETA FEATURE: Captures and stores the current `TokenType` under the parser
cursor into `parser.storage` or an optional caller-owned storage mapping. When
a `matcher` combinator is provided and `consume=True` (the default), delegates
token consumption and AST node construction directly to the `matcher`.
"""
from __future__ import annotations

from collections.abc import MutableMapping
from typing import ClassVar, TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer import TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Save(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.SAVE
    """
    [BETA] Combinator that stores the current `TokenType` at `parser.pos`
    into `parser.storage[name]`.

    Consumption Rules:
    - If `matcher` is `None`: Never consumes (zero-width); stores and returns
      the current `TokenType`.
    - If `matcher` is provided and `consume=True` (default): Evaluates `matcher`
      normally (allowing it to consume the token and produce an AST node),
      stores the captured `TokenType` in `parser.storage[name]`, and returns
      the matcher's result.
    - If `matcher` is provided and `consume=False`: Evaluates `matcher` as a
      zero-width lookahead, restores the parser checkpoint, stores the token,
      and returns the `TokenType`.
    """

    def __init__(
        self,
        name: str,
        matcher: Combinator | None = None,
        *,
        consume: bool = True,
        storage: MutableMapping[str, TokenType] | None = None,
    ) -> None:
        """
        Initialize the `Save` combinator [BETA].

        Args:
            name (str): Storage key under which the current `TokenType` will be saved.
            matcher (Combinator | None): Optional combinator to validate (and by
                default consume) the current token.
            consume (bool): Defaults to `True`. Only takes effect when `matcher`
                is provided; if `False`, rewinds the cursor after `matcher` succeeds.
            storage (MutableMapping | None): Optional isolated destination. If
                omitted, uses `parser.storage`; when provided, the mapping is
                tracked by parser checkpoints.
        """
        super().__init__()
        self.name: str = name
        self.matcher: Combinator | None = matcher
        self.consume: bool = consume
        self.storage: MutableMapping[str, TokenType] | None = storage

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Capture the current token into `parser.storage[self.name]`, delegating
        validation and consumption to `self.matcher` when present.
        """
        parser = analyzer.parser
        destination = parser.storage if self.storage is None else self.storage
        if self.storage is not None:
            parser.track_external_storage(destination)
        should_consume = self.matcher is not None and self.consume
        father = parser.node(
            "ProcessingSave",
            f"[BETA] Guardando token en '{self.name}' (consume={should_consume})",
            set_target=True,
        )

        try:
            if parser.empty():
                father.note("Save falló: flujo de tokens en EOF.", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "SaveUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        f"No se pudo guardar '{self.name}' porque se alcanzó el final del archivo (EOF).",
                        "Asegúrese de que exista un token bajo el cursor antes de invocar Save.",
                    ),
                    pos=parser.pos,
                )
                return None

            current = parser.peek()
            if current is None:
                return None

            # Case 1: Matcher is provided
            if self.matcher is not None:
                chk = parser.savepoint("SAVE-Matcher")
                with analyzer.safe_mode():
                    matched_node = analyzer.visitor(self.matcher)

                if matched_node is None:
                    parser.restore(chk)
                    father.note(
                        f"El token '{current.value}' no pasó el matcher de Save('{self.name}').",
                        "warn",
                    )
                    analyzer.report_error(
                        errors.GrammarError(
                            "SaveMatcherFailed",
                            errors.GRAMMAR_COMBINATOR_FAILED,
                            f"El token actual '{current.value}' (línea {current.line}, columna {current.col}) "
                            f"no cumple el criterio de {self.matcher!r} en Save('{self.name}').",
                            "Verifique el tipo o valor del token esperado por Save.",
                        ),
                        pos=parser.pos,
                    )
                    return None

                if not self.consume:
                    parser.restore(chk)
                    destination[self.name] = current
                    father.note(
                        f"Token '{current.value}' validado y guardado en storage['{self.name}'] sin consumir.",
                        "success",
                    )
                    return current

                destination[self.name] = current
                analyzer.discard_staged_failure(min_weight=parser.pos)
                father.note(
                    f"Token '{current.value}' guardado en storage['{self.name}'] y consumido por {self.matcher!r}.",
                    "success",
                )
                return matched_node

            # Case 2: No matcher provided -> zero-width capture (never consumes)
            destination[self.name] = current
            father.note(
                f"Token '{current.value}' almacenado en storage['{self.name}'] (sin matcher, sin consumir).",
                "success",
            )
            return current
        finally:
            parser.down()

    def __repr__(self) -> str:
        parts = [repr(self.name)]
        if self.matcher is not None:
            parts.append(f"matcher={self.matcher!r}")
        if not self.consume:
            parts.append("consume=False")
        if self.storage is not None:
            parts.append("storage=external")
        return f"Save({', '.join(parts)})"


__all__ = ["Save"]
