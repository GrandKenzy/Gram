"""
Gram Syntactic Parser (`gram.core.parser.core`).
================================================
EN:
    Implements a decoupled, clean, and ergonomic parser engine focused on
    validated token consumption and grammar execution, delegating navigation,
    transactions, backtracking, lookahead, and telemetry to `ParseControl`.

ES:
    Implementa el motor de análisis sintáctico desacoplado, limpio y enfocado
    en el consumo validado de tokens, delegando la navegación, transacciones,
    backtracking, lookahead y reporte de telemetría a una instancia de `ParseControl`.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from gram import config, errors
from gram.core.parser.control import ParseControl

if TYPE_CHECKING:
    from gram.codes import CodeError
    from gram.core.lexer.items import TokenStream
    from gram.core.lexer.tokens import Token, TokenType
    from gram.core.parser.checkpoint import Checkpoint
    from gram.utilities import error
    from gram.utilities.info import Node as InfoNode, StackInfo


class Parser:
    """
    EN:
        Main parser for the Gram Framework.
        Provides an ergonomic interface for token consumption and grammar parsing,
        modularly delegating cursors, lookahead, backtracking, and telemetry
        to its `ParseControl` component.

    ES:
        Analizador sintáctico principal de Gram Framework.
        Proporciona una interfaz ergonómica para el consumo de tokens y análisis de reglas,
        delegando de forma modular la lógica de cursores, lookahead, backtracking
        y enrutamiento de telemetría a su componente `ParseControl`.
    """

    def __init__(
        self,
        tokens: Sequence[TokenType] | TokenStream | None = None,
        control: ParseControl | None = None,
        node: InfoNode | StackInfo | None = None,
        stack: StackInfo | InfoNode | None = None,
    ) -> None:
        """
        EN: Initializes the syntactic parser with tokens, optional control, and telemetry node.
        ES: Inicializa el analizador sintáctico con tokens, controlador opcional y nodo de telemetría.

        Args:
            tokens: Sequence of tokens or TokenStream to parse.
            control: Optional custom ParseControl instance.
            node: Optional external telemetry Node or StackInfo.
            stack: Optional external telemetry StackInfo (alias of `node`).
        """
        if control is not None:
            self._control = control
            if tokens is not None:
                self._control.bind_tokens(tokens)
            if node is not None or stack is not None:
                self._control.set_node(node if node is not None else stack)
        else:
            self._control = ParseControl(tokens=tokens, node=node, stack=stack)

    # ==========================================================================
    # CONTROLADOR Y PROPIEDADES DE ACCESO / CONTROLLER & ACCESS PROPERTIES
    # ==========================================================================

    @property
    def control(self) -> ParseControl:
        """
        EN: Navigation, backtracking, and telemetry controller.
        ES: Controlador de navegación, backtracking y telemetría.
        """
        return self._control

    @property
    def tokens(self) -> list[TokenType]:
        """
        EN: Analyzed token stream list.
        ES: Flujo de tokens analizado.
        """
        return self._control.tokens

    @tokens.setter
    def tokens(self, value: Sequence[TokenType] | TokenStream) -> None:
        self._control.tokens = value

    @property
    def pos(self) -> int:
        """
        EN: Current physical cursor index.
        ES: Posición actual del cursor físico.
        """
        return self._control.pos

    @pos.setter
    def pos(self, value: int) -> None:
        self._control.pos = value

    @property
    def virtual_pos(self) -> int:
        """
        EN: Current virtual speculative cursor index.
        ES: Posición actual del cursor virtual.
        """
        return self._control.virtual_pos

    @virtual_pos.setter
    def virtual_pos(self, value: int) -> None:
        self._control.virtual_pos = value

    @property
    def node(self) -> InfoNode:
        """
        EN: Active telemetry node in the controller.
        ES: Nodo de telemetría activo en el controlador.
        """
        return self._control.node

    @property
    def stack(self) -> StackInfo | None:
        """
        EN: Active telemetry and error stack (StackInfo).
        ES: Pila (StackInfo) de telemetría y errores activa en el analizador sintáctico.
        """
        return self._control.stack

    @stack.setter
    def stack(self, value: StackInfo | None) -> None:
        self._control.stack = value

    @property
    def errors(self) -> list[error.ParserError]:
        """
        EN: History of syntactic errors collected by the parser.
        ES: Historial de errores sintácticos recolectados por el parser.
        """
        return self._control.errors

    @property
    def watcher(self) -> Any:
        """
        EN: Connected debugging/execution watcher.
        ES: Observador/depurador conectado.
        """
        return self._control.watcher

    @watcher.setter
    def watcher(self, value: Any) -> None:
        self._control.watcher = value

    # ==========================================================================
    # GESTIÓN Y REDIRECCIÓN DE TELEMETRÍA / TELEMETRY ROUTING
    # ==========================================================================

    def set_node(self, node: InfoNode | StackInfo | None) -> None:
        """
        EN: Redirects log and error destinations to the specified node or stack.
        ES: Redirige el destino de logs y errores al nodo o stack especificado.
        """
        self._control.set_node(node)

    def reset_node(self) -> None:
        """
        EN: Resets telemetry routing back to the default root node.
        ES: Restablece el nodo de telemetría al nodo raíz por defecto.
        """
        self._control.reset_node()

    def use_node(self, node: InfoNode | StackInfo) -> Iterator[InfoNode]:
        """
        EN: Context manager temporarily redirecting logs to a specific node.
        ES: Context manager para enviar logs a un nodo o stack específico temporalmente.
        """
        return self._control.scoped_node(node)

    def note(
        self,
        message: str,
        note_type: str = 'normal',
        priority: int = 1,
        node: InfoNode | StackInfo | None = None,
    ) -> None:
        """
        EN: Emits a diagnostic telemetry note through the controller.
        ES: Emite una nota de telemetría a través del controlador.
        """
        self._control.note(message, note_type=note_type, priority=priority, node=node)

    def fail(
        self,
        message: str,
        code: CodeError,
        *caution: str,
        node: InfoNode | StackInfo | None = None,
        raise_exception: bool = True,
    ) -> error.ParserError:
        """
        EN: Emits and/or raises a structured syntactic error through the controller.
        ES: Emite y/o levanta un error sintáctico a través del controlador.
        """
        return self._control.fail(
            message,
            code,
            *caution,
            node=node,
            raise_exception=raise_exception,
        )

    # ==========================================================================
    # CONSULTA Y ESTADO DEL FLUJO / STREAM STATUS & INSPECTION
    # ==========================================================================

    def count(self) -> int:
        """
        EN: Total count of tokens in the stream.
        ES: Cantidad total de tokens en el flujo.
        """
        return self._control.count()

    def remaining(self) -> int:
        """
        EN: Number of tokens remaining to be consumed.
        ES: Cantidad de tokens pendientes de consumir.
        """
        return self._control.remaining()

    def not_empty(self) -> bool:
        """
        EN: Indicates whether tokens are available at the physical cursor.
        ES: Indica si hay tokens disponibles en el cursor físico.
        """
        return self._control.not_empty()

    def virtual_not_empty(self) -> bool:
        """
        EN: Indicates whether tokens are available at the virtual cursor.
        ES: Indica si hay tokens disponibles en el cursor virtual.
        """
        return self._control.virtual_not_empty()

    def is_eof(self) -> bool:
        """
        EN: Indicates whether the physical cursor is at or beyond the EOF token.
        ES: Indica si el cursor físico se encuentra en o más allá del token EOF.
        """
        return self._control.is_eof()

    def current(self, node: InfoNode | None = None) -> TokenType:
        """
        EN: Returns the active token under the physical cursor without consuming it.
        ES: Devuelve el token actual bajo el cursor físico sin consumirlo.

        Raises:
            ParserError: If no tokens are available (PARSER_EARLY_EOF).
        """
        if not self.not_empty():
            self._control.fail(
                "Fin inesperado del flujo de tokens",
                errors.PARSER_EARLY_EOF,
                "Se intentó inspeccionar el token actual pero no quedan tokens disponibles.",
                node=node,
            )
        return self._control.tokens[self._control.pos]

    # ==========================================================================
    # CONSUMO DE TOKENS (FÍSICO) / TOKEN CONSUMPTION
    # ==========================================================================

    def consume(
        self,
        expected: Token | str | None = None,
        node: InfoNode | None = None,
    ) -> TokenType:
        """
        EN: Physically consumes the active token and advances the cursor by one position.
            If `expected` is specified, validates that the consumed token matches.
        ES: Consume físicamente el token actual y avanza el cursor real una posición.
            Si se especifica `expected`, valida que el token consumido coincida con el tipo o valor.

        Args:
            expected: Expected Token enum type or string value.
            node: Optional telemetry node.

        Returns:
            TokenType: Consumed token.

        Raises:
            ParserError: If EOF is reached or token does not match expectation.
        """
        if not self.not_empty():
            self._control.fail(
                "Fin prematuro de entrada al intentar consumir token",
                errors.PARSER_EARLY_EOF,
                "Se esperaba consumir un token pero el flujo ha alcanzado el final del archivo.",
                node=node,
            )

        token = self._control.tokens[self._control.pos]

        if expected is not None:
            matches_expected = False
            if hasattr(expected, 'name'):
                matches_expected = (token.token == expected)
            elif isinstance(expected, str):
                matches_expected = (token.token.name == expected or str(token.value) == expected)

            if not matches_expected:
                exp_name = getattr(expected, 'name', str(expected))
                self._control.fail(
                    f"Token inesperado '{token.value}': se esperaba {exp_name}",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Encontrado {token.token.name} ({token.value!r}) en línea {token.line}, columna {token.col}.",
                    node=node,
                )

        if getattr(config, 'PARSER_ADD_INFO', True):
            self._control.note(
                f"Consumiendo [{self._control.pos}]: {token.token.name} = {token.value!r}",
                'normal',
                node=node,
            )

        self._control.advance(1)
        self._control._skip_whitespace()

        if self._control.watcher is not None:
            self._control.watcher.update_token(token)

        if getattr(config, 'PARSER_ADD_INFO', True):
            self._control.note(
                f"Cursor físico avanzado a posición {self._control.pos}",
                'success',
                node=node,
            )

        return token

    def consume_if(
        self,
        *expected: Token | str,
        node: InfoNode | None = None,
    ) -> TokenType | None:
        """
        EN: Consumes current token only if it matches any of the expected types or values.
            Otherwise leaves cursor unmoved and returns None.
        ES: Consume el token actual solo si coincide con alguno de los tipos o valores provistos.
            De lo contrario no mueve el cursor y retorna None.
        """
        if not self.not_empty():
            return None

        curr = self._control.tokens[self._control.pos]
        for exp in expected:
            if hasattr(exp, 'name') and curr.token == exp:
                return self.consume(node=node)
            if isinstance(exp, str) and (curr.token.name == exp or str(curr.value) == exp):
                return self.consume(node=node)

        return None

    def advance(self, steps: int = 1) -> int:
        """
        EN: Advances the physical cursor by the specified step count and returns new position.
        ES: Avanza el cursor físico la cantidad de pasos indicada y retorna la nueva posición.
        """
        return self._control.advance(steps)

    # ==========================================================================
    # GESTIÓN DE DELIMITADORES / BRACKET-AWARE MODE
    # ==========================================================================

    def enter_bracket(self) -> None:
        """
        EN: Enters open delimiter mode (suppresses NEWLINE, INDENT, DEDENT).
        ES: Entra en modo de delimitador abierto (suprime NEWLINE, INDENT, DEDENT).
        """
        self._control.enter_bracket()

    def exit_bracket(self) -> None:
        """
        EN: Exits open delimiter mode.
        ES: Sale del modo de delimitador abierto.
        """
        self._control.exit_bracket()

    @contextmanager
    def bracket_context(self) -> Iterator[None]:
        """
        EN: Context manager for delimited operations (parentheses, brackets, braces).
            Guarantees exit_bracket() is called on block exit.
        ES: Gestor de contexto para operaciones delimitadas (paréntesis, corchetes, llaves).
            Garantiza que exit_bracket() sea invocado al salir del bloque.
        """
        self.enter_bracket()
        try:
            yield
        finally:
            self.exit_bracket()

    # ==========================================================================
    # DELEGACIONES ERGONÓMICAS HACIA PARSECONTROL / ERGONOMIC DELEGATIONS
    # ==========================================================================

    def peek(self, offset: int = 0, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Inspects token at relative offset without moving the physical cursor.
        ES: Inspecciona token a distancia offset sin mover el cursor físico.
        """
        return self._control.peek(offset=offset, node=node)

    def peek_token(self, offset: int = 0, node: InfoNode | None = None) -> Token | None:
        """
        EN: Inspects Token enum type at relative offset.
        ES: Inspecciona tipo de token (Enum) a distancia offset.
        """
        return self._control.peek_token(offset=offset, node=node)

    def lookahead(self, count: int = 1, node: InfoNode | None = None) -> list[TokenType]:
        """
        EN: Retrieves upcoming `count` tokens without consuming them.
        ES: Obtiene los siguientes `count` tokens sin consumirlos.
        """
        return self._control.lookahead(count=count, node=node)

    def matches(
        self,
        *expected: Token | str,
        offset: int = 0,
        node: InfoNode | None = None,
    ) -> bool:
        """
        EN: Checks if token at relative offset matches any of the expected types.
        ES: Verifica si el token en posición relativa coincide con los esperados.
        """
        return self._control.matches(*expected, offset=offset, node=node)

    def slice(self, start: int, end: int) -> list[TokenType]:
        """
        EN: Slices an arbitrary range of tokens without altering parser state.
        ES: Extrae un rango arbitrario de tokens sin alterar el estado.
        """
        return self._control.slice(start=start, end=end)

    def savepoint(self, node: InfoNode | None = None) -> Checkpoint:
        """
        EN: Creates an immutable snapshot checkpoint of the current state.
        ES: Crea una instantánea inmutable del estado actual.
        """
        return self._control.savepoint(node=node)

    def restore(
        self,
        checkpoint: Checkpoint | int,
        node: InfoNode | None = None,
    ) -> None:
        """
        EN: Restores cursors to the given savepoint checkpoint or integer index.
        ES: Restaura los cursores al punto de guardado o posición indicada.
        """
        self._control.restore(checkpoint=checkpoint, node=node)

    def transaction(self, node: InfoNode | None = None) -> Iterator[Checkpoint]:
        """
        EN: Context manager for atomic operations with automatic rollback on failure.
        ES: Context manager para operaciones atómicas con rollback automático ante fallo.
        """
        return self._control.transaction(node=node)

    def future(self, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Reads token under virtual cursor and advances virtual cursor.
        ES: Obtiene token bajo cursor virtual y avanza cursor virtual.
        """
        return self._control.future(node=node)

    def peek_virtual(self, offset: int = 0, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Inspects token relative to the virtual cursor without moving it.
        ES: Inspecciona relativo al cursor virtual sin moverlo.
        """
        return self._control.peek_virtual(offset=offset, node=node)

    def set_virtual_token(self, pos: int, node: InfoNode | None = None) -> int:
        """
        EN: Manually positions the virtual speculative cursor.
        ES: Ajusta manualmente la posición del cursor virtual.
        """
        return self._control.set_virtual_token(pos=pos, node=node)

    def reset_virtual(self, node: InfoNode | None = None) -> None:
        """
        EN: Resets virtual cursor, resynchronizing it with the physical cursor.
        ES: Restablece el cursor virtual sincronizándolo con el físico.
        """
        self._control.reset_virtual(node=node)

    def rollback(self, node: InfoNode | None = None) -> None:
        """
        EN: Alias to discard virtual speculative exploration.
        ES: Alias para descartar la exploración virtual.
        """
        self._control.rollback(node=node)

    def commit(self, node: InfoNode | None = None) -> list[TokenType]:
        """
        EN: Commits virtual exploration, advancing physical cursor to match virtual.
        ES: Sincroniza cursor físico con virtual consumiendo físicamente los explorados.
        """
        return self._control.commit(node=node)

    def quit(self, tok: Token, node: InfoNode | None = None) -> int:
        """
        EN: Removes tokens of the specified type and readjusts cursors.
        ES: Elimina tokens del tipo especificado y reajusta cursores.
        """
        return self._control.quit(tok=tok, node=node)

    def synchronize(
        self,
        sync_tokens: tuple[Token, ...] | None = None,
        node: InfoNode | None = None,
    ) -> list[TokenType]:
        """
        EN: Discards tokens until encountering a designated synchronization barrier token.
        ES: Descarta tokens hasta un delimitador de sincronización seguro.
        """
        return self._control.synchronize(sync_tokens=sync_tokens, node=node)

    # ==========================================================================
    # EJECUCIÓN PRINCIPAL DE PARSING / MAIN PARSE EXECUTION
    # ==========================================================================

    def parse(
        self,
        grammar: Any,
        node: InfoNode | None = None,
    ) -> Any:
        """
        EN: Executes complete syntactic analysis against combinator grammar, delegating to ASTAnalyzer.
        ES: Ejecuta el análisis sintáctico completo contra una gramática de combinadores, delegando en ASTAnalyzer.

        Args:
            grammar: Dictionary of grammatical rules and combinators.
            node: Optional telemetry node.

        Returns:
            ASTProgram: Fully built and structured abstract syntax tree.
        """
        target_node = self._control._get_target_node(node)

        if getattr(config, 'PARSER_ADD_INFO', True):
            self._control.note(
                f"Iniciando análisis sintáctico con gramática {grammar}",
                'normal',
                node=target_node,
            )

        from gram.core.ast.analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer(self, grammar, node=target_node)
        result = analyzer.process()

        if getattr(config, 'PARSER_ADD_INFO', True):
            self._control.note(
                "Análisis sintáctico finalizado con éxito",
                'success',
                node=target_node,
            )

        return result


__all__ = ['Parser']
