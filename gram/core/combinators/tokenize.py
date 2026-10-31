"""
Tokenize Combinator (`gram.core.combinators.tokenize`).
=======================================================
Provides the `Tokenize` combinator to evaluate an ordered sequence of child
combinators and fuse all matched tokens into a single `TokenType` backed by
a `CustomToken` instance.
"""
from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.combinators.sequence import Seq
from gram.core.lexer.tokens import CustomToken, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Tokenize(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.TOKENIZE
    """
    Combinator that evaluates a child sequence and consolidates all matched
    tokens into a single `TokenType` with a synthesized `CustomToken`.

    Prevents composite lexical sub-rules (such as prefixed literals or
    multi-symbol operators) from expanding into separate child branches in the AST.
    """

    header_class: bool = True

    def __init__(
        self,
        *combinators: Combinator,
        token_name: str = "CustomToken",
        name: str | None = None,
        join_char: str = "",
    ) -> None:
        """
        Initialize the composite token synthesizer.

        Args:
            *combinators (Combinator): Sequence of combinators producing lexical tokens.
            token_name (str): Default name for the synthesized `CustomToken`.
            name (str | None): Optional override for `token_name`.
            join_char (str): Delimiter string used to join matched token lexemes.
        """
        super().__init__()
        if not combinators:
            errors.GrammarError(
                "EmptyTokenizeCombinators",
                errors.GRAMMAR_TOKENIZE_EMPTY_COMBINATORS,
                "El combinador Tokenize requiere al menos un combinador hijo.",
                "Proporcione uno o más combinadores dentro de Tokenize(...).",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)
        self.token_name: str = name if name is not None else token_name
        self.join_char: str = join_char
        self._seq: Seq = Seq(*combinators)

    def parse(self, analyzer: ASTAnalyzer) -> TokenType | None:
        """
        Evaluate the internal sequence and merge all resulting tokens into
        a single `TokenType`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            TokenType | None: Synthesized `TokenType` with a `CustomToken` type,
            or `None` if the underlying sequence fails to match.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingTokenize", "Procesando tokenize", set_target=True
        )
        father.note(
            f"Tokenize iniciado con {len(self.combinators)} combinadores para {self.token_name}",
            "normal",
        )

        checkpoint = parser.savepoint("TOKENIZE-Analysis")

        try:
            try:
                result = analyzer.visitor(self._seq)
            except errors.Error:
                parser.restore(checkpoint)
                raise

            if result is None:
                parser.restore(checkpoint)
                return None

            tokens: list[TokenType] = []
            try:
                self._collect_tokens(result, tokens)
            except TypeError as exc:
                parser.restore(checkpoint)
                analyzer.report_error(
                    errors.GrammarError(
                        "InvalidTokenizeElement",
                        errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                        str(exc),
                        "Asegúrese de que todos los combinadores dentro de Tokenize devuelvan tokens.",
                    )
                )
                return None

            if not tokens:
                parser.restore(checkpoint)
                return None

            parts: list[str] = [
                str(t.value) if t.value is not None else str(t.token.name)
                for t in tokens
            ]
            combined_value = self.join_char.join(parts)
            first_tok = tokens[0]

            custom_type = CustomToken(name=self.token_name, value=combined_value)
            token_result = TokenType(
                token=custom_type,
                value=combined_value,
                line=first_tok.line,
                col=first_tok.col,
            )

            father.note(
                f"Tokenize ({self.token_name}) exitoso -> valor={combined_value!r}",
                "success",
            )
            return token_result
        finally:
            parser.down()

    def _collect_tokens(self, item: Any, out: list[TokenType]) -> None:
        """Recursively extract `TokenType` instances from nested sequence results."""
        if item is None:
            return
        if isinstance(item, TokenType):
            out.append(item)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                self._collect_tokens(sub, out)
        elif hasattr(item, "token") and isinstance(item.token, TokenType):
            out.append(item.token)
        else:
            raise TypeError(
                f"Tokenize solo puede fusionar resultados de tokens; "
                f"se recibió '{type(item).__name__}'."
            )

    def __repr__(self) -> str:
        inner = ", ".join(repr(c) for c in self.combinators)
        return f"Tokenize({inner}, token_name={self.token_name!r})"


__all__ = ["Tokenize"]