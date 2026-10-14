"""
Item and Literal Combinators (`gram.core.combinators.item`).
============================================================
Provides the `Item` combinator for grouping atomic sequences of fixed match
combinators and the `Literal` combinator for validating primitive token values.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer

_ANY_LITERAL = object()


class ItemNode(list[TokenType]):
    """AST token sequence fragment produced by `Item`."""

    def __init__(self, items: Iterable[TokenType] = ()) -> None:
        super().__init__(items)

    def __repr__(self) -> str:
        return f"ItemNode({super().__repr__()})"


class LiteralNode(list[TokenType]):
    """AST token fragment produced by `Literal`, containing its matched token."""


class Item(Combinator):
    """
    Combinator grouping child match combinators into an atomic sequential unit.

    If any element in the sequence fails to match, the parser state is completely
    rewound to the initial checkpoint while preserving the deepest failure candidate.
    """

    def __init__(self, *matchs: Combinator) -> None:
        """
        Initialize the atomic `Item` sequence.

        Args:
            *matchs (Combinator): Child combinators that must match in exact sequence.
        """
        super().__init__()
        self.matchs: tuple[Combinator, ...] = matchs
        self.combinators: tuple[Combinator, ...] = matchs

    def items(self) -> tuple[Combinator, ...]:
        """Return the tuple of configured child combinators."""
        return self.matchs

    def __iter__(self) -> Iterator[Combinator]:
        return iter(self.matchs)

    def __len__(self) -> int:
        return len(self.matchs)

    def parse(self, analyzer: ASTAnalyzer) -> ItemNode | None:
        """
        Execute atomic evaluation of the configured match sequence.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            ItemNode | None: `ItemNode` containing all matched tokens, or `None` on failure.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingItem", "Procesando item atómico", set_target=True
        )
        father.note(f"Item iniciado con {len(self.matchs)} elementos", "normal")

        try:
            if not self.matchs:
                return ItemNode()

            checkpoint = parser.savepoint("ITEM-Analysis")
            tokens: list[TokenType] = []

            for idx, match_comb in enumerate(self.matchs, start=1):
                with analyzer.safe_mode():
                    res = analyzer.visitor(match_comb)

                if res is None:
                    failed_pos = parser.pos
                    curr_tok = parser.peek() if not parser.empty() else None
                    tok_info = (
                        f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                        if curr_tok is not None
                        else ""
                    )
                    parser.restore(checkpoint)
                    fallback = errors.GrammarError(
                        "IncompleteItemSequence",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        f"Fallo en el componente {idx} de Item({match_comb!r}){tok_info}.",
                        "Asegúrese de que todos los elementos de la secuencia Item coincidan.",
                    )
                    if analyzer.safe_flag:
                        analyzer.report_error(fallback, pos=failed_pos)
                    else:
                        analyzer.flush_failure(fallback=fallback)
                    return None

                try:
                    self._collect_tokens(res, tokens)
                except TypeError:
                    failed_pos = parser.pos
                    parser.restore(checkpoint)
                    analyzer.report_error(
                        errors.GrammarError(
                            "InvalidItemElementType",
                            errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                            f"Item solo puede agrupar resultados de tokens; "
                            f"{match_comb!r} devolvió '{type(res).__name__}'.",
                            "Utilice únicamente combinadores que produzcan tokens dentro de Item(...).",
                        ),
                        pos=failed_pos,
                    )
                    return None

            analyzer.discard_staged_failure(min_weight=parser.pos)
            father.note(
                f"Item completado con éxito ({len(tokens)} tokens)", "success"
            )
            return ItemNode(tokens)
        finally:
            parser.down()

    def _collect_tokens(self, item: Any, out: list[TokenType]) -> None:
        """Recursively flatten token results into `out`."""
        if isinstance(item, TokenType):
            out.append(item)
        elif isinstance(item, (ItemNode, LiteralNode, list, tuple)):
            for sub in item:
                self._collect_tokens(sub, out)
        elif hasattr(item, "token") and isinstance(item.token, TokenType):
            out.append(item.token)
        else:
            raise TypeError

    def __repr__(self) -> str:
        items = ", ".join(repr(m) for m in self.matchs)
        return f"Item({items})"


class Literal(Combinator):
    """
    Combinator matching the literal primitive value of the current token
    against an expected value (or any non-keyword literal if omitted).
    Reserved keywords (`Token.KEYWORD`) never match `Literal`.
    """

    def __init__(self, literal: Any = _ANY_LITERAL) -> None:
        """
        Initialize the literal value matcher.

        Args:
            literal (Any): Target primitive value to match, or wildcard if omitted.
        """
        super().__init__()
        self.literal: Any = literal

    def parse(self, analyzer: ASTAnalyzer) -> LiteralNode | None:
        """
        Check whether the current token matches `self.literal` and is not a keyword.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            LiteralNode | None: `LiteralNode` wrapping the matched token, or `None` on mismatch.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingLiteral", "Procesando literal", set_target=True
        )
        father.note(f"Procesando Literal: {self.literal!r}", "normal")

        try:
            if parser.empty():
                father.note("Error: se esperaba Literal pero se alcanzó EOF", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "LiteralUnexpectedEOF",
                        errors.PARSER_EARLY_EOF,
                        "Se esperaba un valor literal, pero se alcanzó el final del archivo (EOF).",
                        "Proporcione un literal válido en la expresión.",
                    ),
                    pos=parser.pos,
                )
                return None

            tok = parser.peek()
            if tok is None:
                return None

            if tok.token == Token.KEYWORD or tok.token.name == "KEYWORD":
                father.note(f"Literal no admite KEYWORD: {tok.value!r}", "error")
                analyzer.report_error(
                    errors.ParserError(
                        "KeywordNotAllowedInLiteral",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"Literal no puede coincidir con una palabra reservada (KEYWORD): "
                        f"{tok.value!r} en línea {tok.line}, columna {tok.col}.",
                        "Use un literal válido (número, cadena o identificador no reservado).",
                    ),
                    pos=parser.pos,
                )
                return None

            if not self._match_value(tok.value):
                father.note(
                    f"Literal rechazado: se esperaba {self.literal!r}, se recibió {tok.value!r}",
                    "warn",
                )
                analyzer.report_error(
                    errors.ParserError(
                        "LiteralValueMismatch",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        f"Literal incorrecto en línea {tok.line}, columna {tok.col}: "
                        f"se esperaba {self.literal!r}, pero se recibió {tok.value!r}.",
                        "Verifique el valor literal esperado por la regla.",
                    ),
                    pos=parser.pos,
                )
                return None

            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            father.note(f"Literal aceptado: {tok.value!r}", "success")
            return LiteralNode([tok])
        finally:
            parser.down()

    def _match_value(self, token_value: Any) -> bool:
        """Return True if `token_value` matches `self.literal`."""
        if self.literal is _ANY_LITERAL:
            return True
        if token_value == self.literal:
            return True
        if isinstance(self.literal, (int, float)) and isinstance(
            token_value, (int, float)
        ):
            return self.literal == token_value
        return False

    def __repr__(self) -> str:
        if self.literal is _ANY_LITERAL:
            return "Literal()"
        return f"Literal({self.literal!r})"


__all__ = [
    "Item",
    "ItemNode",
    "Literal",
    "LiteralNode",
]