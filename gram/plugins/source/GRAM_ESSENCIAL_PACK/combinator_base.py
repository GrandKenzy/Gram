"""
Clase base SimpleCombinator para creación intuitiva y segura de combinadores.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.core.ast.analyzer import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType

from gram import config
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.utilities.error.codes import CodeError
from gram.utilities import error


class SimpleCombinator(Combinator):
    """
    Clase base simplificada para crear combinadores con lógica de validación personalizada.

    Permite a los desarrolladores de plugins definir filtros o reglas de coincidencia
    sintáctica sobre tokens individuales sin necesidad de manipular cursores del parser,
    gestionar pilas de llamadas ni manejar manualmente el backtracking o errores.

    Ciclo de vida y funcionamiento:
    ================================
    1. El Parser de Gram invoca parse(analyzer, current, ignore_errors).
    2. evaluate(current) inspecciona el token actual (TokenType) y DEBE retornar un bool.
    3. Si evaluate retorna True:
       - Indica que el token coincide exitosamente con el criterio del combinador.
       - Gram consume automáticamente el token actual y avanza el cursor del parser.
       - El combinador retorna el token consumido (current).
    4. Si evaluate retorna False:
       - Si ignore_errors es True (dentro de Alt u Opt): retorna None para permitir backtracking seguro.
       - Si ignore_errors es False: invoca get_error(current) y lanza un ParserError formal.
    """

    def evaluate(self, current: TokenType) -> bool:
        """
        Evalúa si el token actual (current) satisface las condiciones del combinador.
        Debe ser sobrescrito por la subclase.
        """
        raise NotImplementedError("Debes implementar el método evaluate().")

    def get_error(self, current: TokenType) -> tuple[Any, str]:
        """
        Genera el código de error y mensaje descriptivo cuando evaluate retorna False.
        """
        err_code = errors.COMBINATOR_FAILED
        tok_name = getattr(current.token, "name", str(current.token))
        return err_code, f"Token inesperado '{tok_name}' ({current.value}) en combinador de plugin."

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        Método de ejecución del combinador en el pipeline de análisis de Gram.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        active_token = current if current is not None else parser.consume(node=target_node)
        if active_token is None:
            if ignore_errors:
                return None
            err_code = errors.PARSER_EARLY_EOF
            error.ParserError(
                "Fin de archivo inesperado en combinador de plugin.",
                err_code,
            ).raise_error()

        if self.evaluate(active_token):
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(f"SimpleCombinator '{self.__class__.__name__}' acertó.", "Success")
            return active_token

        if ignore_errors:
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note("SimpleCombinator falló de forma segura.", "Advice")
            return None

        code_err, msg = self.get_error(active_token)
        if target_node and getattr(config, "PARSER_ADD_ERROR", True):
            target_node.note(msg, "Error")

        error.ParserError(
            msg,
            code_err,
            f"Encontrado en línea {active_token.line}, columna {active_token.col}.",
        ).raise_error()


CombinatorAdditionalStack.register(SimpleCombinator)

__all__ = ["SimpleCombinator"]
