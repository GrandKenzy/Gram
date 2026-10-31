"""
Load Combinator (`gram.core.combinators.load`) [BETA].
======================================================
BETA FEATURE: Retrieves or interacts with a `TokenType` previously stored in
`parser.storage` or an optional caller-owned storage mapping using one of five
modes: `'get'`, `'match'`, `'unmatch'`, `'replace'`, or `'change'`. When a
`matcher` is provided, delegates token consumption and AST node creation
directly to the `matcher`.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import ClassVar, TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer import TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer

LoadMode = Literal["get", "match", "unmatch", "replace", "change"]


class Load(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.LOAD
    """
    [BETA] Combinator that operates on a `TokenType` stored in `parser.storage[name]`
    without altering the length of `parser.tokens`:

    - `'get'`: Returns the stored `TokenType` directly without moving the cursor.
    - `'match'`: Requires the current token under the cursor to equal the stored
      token. If `matcher` is provided, delegates consumption to `matcher`.
    - `'unmatch'`: Requires the current token under the cursor to differ from the
      stored token. If `matcher` is provided, delegates consumption to `matcher`.
    - `'replace'`: Replaces the token at `parser.tokens[parser.pos]` in-place with
      the stored `TokenType`. If `matcher` is provided, delegates consumption of
      the replaced token to `matcher`.
    - `'change'`: Swaps the token at `parser.tokens[parser.pos]` with the token in
      `parser.storage[name]`. If `matcher` is provided, delegates consumption of
      the swapped-in token to `matcher`.
    """

    def __init__(
        self,
        name: str,
        mode: LoadMode = "get",
        matcher: Combinator | None = None,
        *,
        storage: Mapping[str, TokenType] | None = None,
    ) -> None:
        """
        Initialize the `Load` combinator [BETA].

        Args:
            name (str): Key of the stored token in `parser.storage`.
            mode (LoadMode): Operation mode (`'get'`, `'match'`, `'unmatch'`,
                `'replace'`, or `'change'`).
            matcher (Combinator | None): Optional combinator that validates and
                automatically consumes the stream token.
            storage (Mapping | None): Optional isolated source mapping. If
                omitted, uses `parser.storage`; `change` requires it to be mutable.
        """
        super().__init__()
        self.name: str = name
        self.mode: LoadMode = mode
        self.matcher: Combinator | None = matcher
        self.storage: Mapping[str, TokenType] | None = storage

    def _consume_with_matcher(
        self,
        analyzer: ASTAnalyzer,
        checkpoint: Any,
        context_token: Any,
    ) -> Any:
        """
        Delegate consumption and AST node construction to `self.matcher`.
        Restores `checkpoint` if `self.matcher` fails.
        """
        parser = analyzer.parser
        assert self.matcher is not None

        with analyzer.safe_mode():
            matched_node = analyzer.visitor(self.matcher)

        if matched_node is None:
            failed_pos = parser.pos
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.GrammarError(
                    "LoadMatcherFailed",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"El token '{context_token.value}' en línea {context_token.line}, columna {context_token.col} "
                    f"no cumplió el matcher {self.matcher!r} en Load('{self.name}', mode='{self.mode}').",
                    "Verifique que el token coincida con el combinador pasado a Load.",
                ),
                pos=failed_pos,
            )
            return None

        analyzer.discard_staged_failure(min_weight=parser.pos)
        return matched_node

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Execute `self.mode` against `parser.storage[self.name]` and delegate
        token consumption to `self.matcher` if configured.
        """
        parser = analyzer.parser
        destination = parser.storage if self.storage is None else self.storage
        if self.mode == "change":
            if not isinstance(destination, MutableMapping):
                analyzer.report_error(
                    errors.GrammarError(
                        "LoadStorageNotMutable",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        "Load(mode='change') requiere un almacenamiento mutable.",
                        "Pase un dict o MutableMapping como storage.",
                    ),
                    pos=parser.pos,
                )
                return None
            parser.track_external_storage(destination)
        father = parser.node(
            "ProcessingLoad",
            f"[BETA] Ejecutando Load('{self.name}', mode='{self.mode}')",
            set_target=True,
        )

        try:
            saved_token = destination.get(self.name)
            if saved_token is None:
                father.note(
                    f"La clave '{self.name}' no existe en parser.storage.", "error"
                )
                analyzer.report_error(
                    errors.GrammarError(
                        "StorageKeyNotFound",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        f"Load('{self.name}') falló: no existe ningún token guardado bajo la clave '{self.name}'.",
                        "Asegúrese de ejecutar Save('{self.name}') antes de invocar Load.",
                    ),
                    pos=parser.pos,
                )
                return None

            # Mode 1: Pure retrieval without touching the stream
            if self.mode == "get":
                father.note(
                    f"Load('get') recuperó {saved_token!r} de '{self.name}'.",
                    "success",
                )
                return saved_token

            # Modes requiring an active token under the cursor
            if parser.empty():
                analyzer.report_error(
                    errors.ParserError(
                        "LoadUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        f"Fin de archivo (EOF) inesperado al ejecutar Load('{self.name}', mode='{self.mode}').",
                        "Verifique que exista un token bajo el cursor.",
                    ),
                    pos=parser.pos,
                )
                return None

            current = parser.peek()
            if current is None:
                return None

            checkpoint = parser.savepoint("LOAD-Operation")

            # Mode 2: Match against stored token
            if self.mode == "match":
                if (
                    current.token != saved_token.token
                    or current.value != saved_token.value
                ):
                    father.note(
                        f"Load('match') falló: actual={current.value!r} != guardado={saved_token.value!r}.",
                        "warn",
                    )
                    analyzer.report_error(
                        errors.ParserError(
                            "LoadMatchFailed",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"Se esperaba el token guardado en '{self.name}' ({saved_token.value!r}), "
                            f"pero se encontró {current.value!r} en línea {current.line}, columna {current.col}.",
                            "Asegúrese de que el token coincida con el valor previamente capturado por Save.",
                        ),
                        pos=parser.pos,
                    )
                    return None

                if self.matcher is not None:
                    res = self._consume_with_matcher(analyzer, checkpoint, current)
                    if res is not None:
                        father.note(
                            f"Load('match') validado y consumido mediante {self.matcher!r}.",
                            "success",
                        )
                    return res

                father.note(
                    f"Load('match') exitoso para '{self.name}' ({current.value!r}) sin consumir.",
                    "success",
                )
                return current

            # Mode 3: Unmatch (negated match) against stored token
            if self.mode == "unmatch":
                if (
                    current.token == saved_token.token
                    and current.value == saved_token.value
                ):
                    father.note(
                        f"Load('unmatch') falló: el token actual es idéntico al guardado ({current.value!r}).",
                        "warn",
                    )
                    analyzer.report_error(
                        errors.ParserError(
                            "LoadUnmatchFailed",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"El token en línea {current.line}, columna {current.col} ({current.value!r}) "
                            f"no debe coincidir con el guardado en '{self.name}'.",
                            f"Use un identificador o valor distinto al almacenado en '{self.name}'.",
                        ),
                        pos=parser.pos,
                    )
                    return None

                if self.matcher is not None:
                    res = self._consume_with_matcher(analyzer, checkpoint, current)
                    if res is not None:
                        father.note(
                            f"Load('unmatch') validado y consumido mediante {self.matcher!r}.",
                            "success",
                        )
                    return res

                father.note(
                    f"Load('unmatch') exitoso: {current.value!r} != {saved_token.value!r} (sin consumir).",
                    "success",
                )
                return current

            # Mode 4: Replace current token at cursor with stored token
            if self.mode == "replace":
                if self.matcher is not None:
                    # Validate current token with matcher before/while consuming,
                    # or replace first so the stream holds saved_token at checkpoint.pos
                    parser.replace_token_at(parser.pos, saved_token)
                    res = self._consume_with_matcher(analyzer, checkpoint, current)
                    if res is not None:
                        father.note(
                            f"Load('replace') reemplazó '{current.value}' por '{saved_token.value}' y lo consumió.",
                            "success",
                        )
                    return res

                parser.replace_token_at(parser.pos, saved_token)
                father.note(
                    f"Load('replace') reemplazó '{current.value}' por '{saved_token.value}' en pos={parser.pos}.",
                    "success",
                )
                return saved_token

            # Mode 5: Swap (change) current token at cursor with stored token
            if self.mode == "change":
                parser.replace_token_at(parser.pos, saved_token)
                destination[self.name] = current

                if self.matcher is not None:
                    res = self._consume_with_matcher(analyzer, checkpoint, saved_token)
                    if res is not None:
                        father.note(
                            f"Load('change') intercambió '{current.value}' <-> '{saved_token.value}' y lo consumió.",
                            "success",
                        )
                    return res

                father.note(
                    f"Load('change') intercambió '{current.value}' <-> '{saved_token.value}' en pos={parser.pos}.",
                    "success",
                )
                return saved_token

            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        suffix = ", storage=external" if self.storage is not None else ""
        if self.matcher is not None:
            return (
                f"Load({self.name!r}, mode={self.mode!r}, "
                f"matcher={self.matcher!r}{suffix})"
            )
        return f"Load({self.name!r}, mode={self.mode!r}{suffix})"


__all__ = ["Load", "LoadMode"]
