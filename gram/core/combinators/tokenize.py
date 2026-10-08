"""
Combinador Tokenize (`gram.core.combinators.tokenize`).
======================================================
Proporciona el combinador `Tokenize` para agrupar secuencias sintácticas
y fusionar los tokens coincidentes en un único `TokenType` con `CustomToken`,
permitiendo sintetizar literales compuestos (como prefijos, sufijos o identificadores extendidos).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.optional import OptResult
from gram.core.combinators.sequence import Seq
from gram.core.lexer.tokens import CustomToken, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class Tokenize(Combinator):
    """
    ES:
        Combinador que ejecuta una secuencia y consolida todos los tokens
        coincidentes en un único TokenType de tipo CustomToken.
        Evita que sub-reglas léxicas compuestas se conviertan en ramas hijas separadas en el AST.

    EN:
        Combinator fusing tokens matched by an inner sequence into a single CustomToken TokenType.
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
        Inicializa el sintetizador de token combinado.

        Args:
            *combinators: Combinadores cuya secuencia producirá los componentes léxicos.
            token_name: Nombre del token personalizado sintetizado.
            name: Sobrescritura opcional de token_name.
            join_char: Carácter de unión entre los valores textuales de los tokens (por defecto "").

        Raises:
            ParserError: Si no se proporciona al menos un combinador.
        """
        self.header_class: bool = True
        if not combinators:
            error.ParserError(
                "Tokenize requiere al menos un combinador.",
                errors.TOKENIZE_EMPTY_COMBINATORS,
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = combinators
        self.token_name: str = name if name is not None else token_name
        self.join_char: str = join_char
        self._seq: Seq = Seq(*combinators)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Ejecuta la secuencia y fusiona los tokens resultantes en un único TokenType.

        Args:
            analyzer: Analizador sintáctico o parser activo.
            current: Token actual posicionado o None.
            ignore_errors: Si True, suprime errores sintácticos.

        Returns:
            TokenType whose token is a CustomToken, or None if the sequence failed.
            TokenType cuyo tipo es CustomToken, o None si falló la secuencia.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"Tokenize iniciado con {len(self.combinators)} combinadores para {self.token_name}",
                "normal",
            )

        checkpoint = parser.savepoint(node=target_node)

        try:
            result = self._seq.parse(
                analyzer,
                current,
                ignore_errors=ignore_errors,
            )
        except error.ParserError:
            parser.restore(checkpoint, node=target_node)
            raise

        if result is None:
            parser.restore(checkpoint, node=target_node)
            return None

        tokens: list[TokenType] = []
        try:
            self._collect_tokens(result, tokens)
        except TypeError:
            parser.restore(checkpoint, node=target_node)
            raise

        if not tokens:
            parser.restore(checkpoint, node=target_node)
            return None

        parts: list[str] = []
        for t in tokens:
            if t.value is not None:
                parts.append(str(t.value))
            else:
                parts.append(str(t.token.name))

        combined_value = self.join_char.join(parts)
        first_tok = tokens[0]

        custom_type = CustomToken(name=self.token_name, value=combined_value)
        tok_line = max(0, first_tok.line - 1) if first_tok.line > 0 else 0
        tok_col = first_tok.col

        token_result = TokenType(
            token=custom_type,
            value=combined_value,
            line=tok_line,
            col=tok_col,
        )

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"Tokenize ({self.token_name}) exitoso -> valor={combined_value!r}",
                "success",
            )

        return token_result

    def _collect_tokens(self, item: Any, out: list[TokenType]) -> None:
        """Collect tokens from the explicit result types supported by Tokenize."""
        if item is None:
            return
        if isinstance(item, TokenType):
            out.append(item)
        elif isinstance(item, OptResult):
            if item.matched:
                self._collect_tokens(item.value, out)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                self._collect_tokens(sub, out)
        else:
            from gram.core.ast.nodes import ASTNode

            if isinstance(item, ASTNode):
                out.extend(item.collect_tokens())
                return
            raise TypeError(
                f"Tokenize solo puede fusionar resultados de tokens; "
                f"recibió {type(item).__name__}."
            )

    def __repr__(self) -> str:
        inner = ", ".join(repr(c) for c in self.combinators)
        return f"Tokenize({inner}, token_name={self.token_name!r})"


__all__ = ["Tokenize"]
