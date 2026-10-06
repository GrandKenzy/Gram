"""
EN:
    Parser State, Navigation, and Telemetry Controller (`gram.core.parser.control`).
    ================================================================================
    Centralizes syntax analyzer control logic:
      1. Dynamic telemetry routing (diagnostics/notes) and errors to designated nodes.
      2. Physical and virtual cursor management with non-destructive speculative lookahead.
      3. Atomic syntactic transactions and backtracking mechanisms (savepoint/restore).
      4. Delimited bracket-aware mode with newline and indentation suppression.
      5. Error recovery strategies and stream synchronization delimiters.

ES:
    Controlador de Estado, Navegación y Telemetría del Parser (`gram.core.parser.control`).
    ========================================================================================
    Centraliza la lógica de control del analizador sintáctico:
      1. Enrutamiento dinámico de telemetría (notas) y errores hacia nodos externos o propios.
      2. Gestión de cursores físico y virtual con exploración especulativa no destructiva.
      3. Mecanismos de transacciones sintácticas y backtracking atómico (savepoint/restore).
      4. Modo delimitado (bracket-aware mode) con supresión inteligente de saltos de línea e indentación.
      5. Estrategias de recuperación ante fallos y sincronización de flujo.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from gram import config, errors
from gram.core.parser.checkpoint import Checkpoint
from gram.utilities import error
from gram.utilities.info import Node as InfoNode, StackInfo

if TYPE_CHECKING:
    from gram.codes import CodeError
    from gram.core.lexer.items import TokenStream
    from gram.core.lexer.tokens import Token, TokenType
    from gram.utilities.info import Node


class ParseControl:
    """
    EN:
        State, navigation, backtracking, and telemetry controller for the Parser.
        Enables transparent routing of diagnostics to designated telemetry nodes,
        managing both physical and virtual cursors and atomic transactions.

    ES:
        Controlador de estado, navegación, backtracking y telemetría para el Parser.
        Permite redirigir de forma transparente notas y errores hacia un nodo específico,
        gestionando simultáneamente cursores físico y virtual y transacciones seguras.
    """

    def __init__(
        self,
        tokens: Sequence[TokenType] | TokenStream | None = None,
        node: Node | StackInfo | None = None,
        stack: StackInfo | Node | None = None,
        default_node_name: str = "PARSER-INFO-NODE",
    ) -> None:
        """
        EN: Initialize a ParseControl instance with tokens and optional telemetry target.
        ES: Inicializa una instancia de ParseControl con tokens y nodo de telemetría opcional.

        Args:
            tokens: Token sequence or TokenStream to control.
                    Flujo de tokens o TokenStream a controlar.
            node: Target external telemetry Node or StackInfo.
                  Nodo o StackInfo de telemetría externo de destino.
            stack: Optional external telemetry stack (alias for `node`).
                   Pila de telemetría externa opcional (alias de `node`).
            default_node_name: Name assigned to default node when no external target is given.
                               Nombre asignado al nodo por defecto cuando no se pasa uno externo.
        """
        self._tokens: list[TokenType] = []
        if tokens is not None:
            self._bind_tokens_internal(tokens)

        self._pos: int = 0
        self._virtual_pos: int = 0
        self.watcher: Any = None
        self._errors: list[error.ParserError] = []
        self._bracket_depth: int = 0

        # Gestión de nodos y telemetría
        from gram.core.parser.stack import stack as default_parser_stack

        target_input = node if node is not None else stack

        if target_input is not None:
            if isinstance(target_input, StackInfo):
                self._stack: StackInfo | None = target_input
                self._default_node: InfoNode = target_input.node(
                    default_node_name,
                    f"Control de parsing inicializado ({len(self._tokens)} tokens)",
                    priority=2,
                )
                self._target_node: InfoNode | None = self._default_node
            elif isinstance(target_input, InfoNode):
                self._stack = None
                self._default_node = target_input
                self._target_node = target_input
            elif hasattr(target_input, 'main') and isinstance(target_input.main, InfoNode):
                self._stack = target_input if isinstance(target_input, StackInfo) else None
                self._default_node = target_input.main
                self._target_node = target_input.main
            else:
                self._stack = None
                self._default_node = target_input  # type: ignore
                self._target_node = target_input  # type: ignore
        else:
            default_parser_stack = StackInfo(
                'parser-log',
                'PARSER',
                'Registro y diagnóstico del analizador sintáctico',
                expose_nodes=True,
                generate_log_file=config.INFO_GENERATE_LOGFILE,
                generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR
            )
            self._stack = default_parser_stack
            self._default_node = self._stack.node(
                default_node_name,
                f"Control de parsing inicializado ({len(self._tokens)} tokens)",
                priority=2,
            )
            self._target_node = None

        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"ParseControl inicializado con {len(self._tokens)} tokens",
                "success",
            )

    # ==========================================================================
    # VINCULACIÓN Y FLUJO DE TOKENS
    # ==========================================================================

    def _bind_tokens_internal(self, tokens: Sequence[TokenType] | TokenStream) -> None:
        """
        EN: Extract token list from sequence or TokenStream.
        ES: Extrae la lista de tokens tanto de secuencias como de TokenStream.
        """
        if hasattr(tokens, 'tokens'):
            self._tokens = list(tokens.tokens)
        else:
            self._tokens = list(tokens)

    @property
    def tokens(self) -> list[TokenType]:
        """
        EN: Token stream managed by this controller.
        ES: Flujo de tokens gestionado por este controlador.
        """
        return self._tokens

    @tokens.setter
    def tokens(self, new_tokens: Sequence[TokenType] | TokenStream) -> None:
        self.bind_tokens(new_tokens)

    def bind_tokens(self, tokens: Sequence[TokenType] | TokenStream) -> None:
        """
        EN: Bind a new token stream to the controller and reset cursors.
        ES: Vincula un nuevo flujo de tokens al controlador y reinicia los cursores.

        Args:
            tokens: New token sequence or TokenStream.
                    Nueva secuencia de tokens o TokenStream.
        """
        self._bind_tokens_internal(tokens)
        self._pos = 0
        self._virtual_pos = 0
        self._bracket_depth = 0
        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Nuevo flujo de tokens vinculado ({len(self._tokens)} tokens)",
                "normal",
            )

    # ==========================================================================
    # CURSORES Y ACCESO POSICIONAL
    # ==========================================================================

    @property
    def pos(self) -> int:
        """
        EN: Current physical cursor index in the token stream.
        ES: Posición actual del cursor físico real en el flujo de tokens.
        """
        return self._pos

    @pos.setter
    def pos(self, value: int) -> None:
        self._pos = max(0, min(value, len(self._tokens)))

    @property
    def virtual_pos(self) -> int:
        """
        EN: Current virtual cursor index for speculative lookahead.
        ES: Posición actual del cursor virtual para exploración previa.
        """
        return self._virtual_pos

    @virtual_pos.setter
    def virtual_pos(self, value: int) -> None:
        self._virtual_pos = max(0, min(value, len(self._tokens)))

    def advance(self, steps: int = 1) -> int:
        """
        EN: Advance the physical cursor by the specified number of steps.
        ES: Avanza el cursor físico la cantidad de pasos indicada.

        Args:
            steps: Number of tokens to advance (default 1).
                   Cantidad de tokens a avanzar (por defecto 1).

        Returns:
            New physical cursor position.
            Nueva posición del cursor físico.
        """
        self._pos = min(len(self._tokens), self._pos + steps)
        return self._pos

    # ==========================================================================
    # MODO BRACKET-AWARE (Supresión de saltos de línea dentro de delimitadores)
    # ==========================================================================

    @property
    def bracket_depth(self) -> int:
        """
        EN: Current nesting depth of open bracket delimiters.
        ES: Profundidad actual de delimitadores abiertos.
        """
        return self._bracket_depth

    @property
    def in_bracket(self) -> bool:
        """
        EN: Indicates whether the parser is currently inside at least one open delimiter.
        ES: Indica si el parser se encuentra dentro de al menos un delimitador abierto.
        """
        return self._bracket_depth > 0

    def enter_bracket(self) -> None:
        """
        EN: Increment open delimiter depth (suppressing newlines and indentation).
        ES: Incrementa la profundidad de delimitadores abiertos (suprimiendo saltos e indentación).
        """
        self._bracket_depth += 1

    def exit_bracket(self) -> None:
        """
        EN: Decrement open delimiter depth (restoring indentation sensitivity when reaching 0).
        ES: Decrementa la profundidad de delimitadores abiertos (restaurando sensibilidad al llegar a 0).
        """
        self._bracket_depth = max(0, self._bracket_depth - 1)

    def _skip_whitespace(self) -> None:
        """
        EN: Skip NEWLINE, INDENT, and DEDENT tokens while in bracket-aware mode.
        ES: Avanza el cursor físico sobre tokens NEWLINE, INDENT y DEDENT en modo bracket-aware.
        """
        if self._bracket_depth <= 0:
            return

        from gram.core.lexer.tokens import Token
        whitespace_types = (Token.NEWLINE, Token.INDENT, Token.DEDENT)
        while self._pos < len(self._tokens) and self._tokens[self._pos].token in whitespace_types:
            self._pos += 1

    # ==========================================================================
    # ENRUTAMIENTO DINÁMICO DE TELEMETRÍA Y ERRORES
    # ==========================================================================

    @property
    def stack(self) -> StackInfo | None:
        """
        EN: Parser diagnostics and telemetry StackInfo instance.
        ES: Pila (StackInfo) de telemetría y diagnóstico del parser.
        """
        return self._stack

    @stack.setter
    def stack(self, value: StackInfo | None) -> None:
        self._stack = value

    @property
    def errors(self) -> list[error.ParserError]:
        """
        EN: Historical list of syntax errors collected during parsing.
        ES: Lista histórica de errores sintácticos recolectados por este parser.
        """
        return list(self._errors)

    @property
    def node(self) -> InfoNode:
        """
        EN: Active target node where notes and diagnostics are routed.
        ES: Devuelve el nodo activo al que se deben enviar notas y diagnósticos.
        """
        return self._target_node if self._target_node is not None else self._default_node

    @property
    def target_node(self) -> InfoNode | None:
        """
        EN: Designated external telemetry target node, or None.
        ES: Devuelve el nodo destino externo actualmente asignado, o None.
        """
        return self._target_node

    def set_node(self, node: InfoNode | StackInfo | None) -> None:
        """
        EN: Designate an external node or stack as the target for all parser logs.
        ES: Asigna un nodo o stack externo como destino para todos los registros del parser.

        Args:
            node: Target Node, StackInfo, or None to restore default node.
                  Nodo o StackInfo de destino o None para restablecer al nodo por defecto.
        """
        if node is not None:
            if isinstance(node, StackInfo):
                self._stack = node
                self._target_node = node.main
            elif hasattr(node, 'main') and isinstance(node.main, InfoNode):
                self._stack = node if isinstance(node, StackInfo) else None
                self._target_node = node.main
            else:
                self._target_node = node  # type: ignore
        else:
            self._target_node = None

        if getattr(config, 'PARSER_ADD_INFO', True):
            nombre = getattr(self._target_node, 'name', 'POR_DEFECTO') if self._target_node is not None else 'POR_DEFECTO'
            self.note(f"Nodo de telemetría redirigido a '{nombre}'", 'advice')

    def reset_node(self) -> None:
        """
        EN: Restore telemetry routing to default root node.
        ES: Restaura el destino de telemetría al nodo raíz por defecto.
        """
        self._target_node = None
        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note("Nodo de telemetría restaurado al nodo por defecto", 'advice')

    @contextmanager
    def scoped_node(self, node: InfoNode | StackInfo) -> Iterator[InfoNode]:
        """
        EN: Context manager to temporarily redirect telemetry and errors to a node.
        ES: Gestor de contexto para redirigir temporalmente la telemetría y errores a un nodo.

        Args:
            node: Scoped Node or StackInfo target.
                  Nodo o StackInfo de destino temporal.

        Yields:
            Target InfoNode.
            Nodo InfoNode de destino.
        """
        previous_node = self._target_node
        if isinstance(node, StackInfo):
            target = node.main
        elif hasattr(node, 'main') and isinstance(node.main, InfoNode):
            target = node.main
        else:
            target = node  # type: ignore

        self._target_node = target
        try:
            yield target
        finally:
            self._target_node = previous_node

    # Alias idiomático
    use_node = scoped_node

    def _get_target_node(self, node: InfoNode | StackInfo | None) -> InfoNode:
        """
        EN: Resolve effective telemetry target node, prioritizing explicit argument.
        ES: Determina el nodo destino priorizando el argumento explícito sobre el configurado.
        """
        if node is not None:
            if isinstance(node, StackInfo):
                return node.main
            if hasattr(node, 'main') and isinstance(node.main, InfoNode):
                return node.main
            return node  # type: ignore
        return self.node

    def note(
        self,
        message: str,
        note_type: str = 'normal',
        priority: int = 1,
        node: InfoNode | StackInfo | None = None,
    ) -> None:
        """
        EN: Emit a diagnostic note to the active target telemetry node.
        ES: Emite una nota de telemetría al nodo destino activo.

        Args:
            message: Informational note text.
                     Texto del mensaje de telemetría.
            note_type: Note category ('normal', 'success', 'advice', 'warning', 'error').
                       Tipo de nota ('normal', 'success', 'advice', 'warning', 'error').
            priority: Telemetry priority level (default 1).
                      Nivel de prioridad de la nota (por defecto 1).
            node: Optional specific target node override.
                  Nodo destino específico opcional.
        """
        if getattr(config, 'PARSER_ADD_INFO', True):
            target = self._get_target_node(node)
            if hasattr(target, 'note'):
                target.note(message, note_type.lower())

    def fail(
        self,
        message: str,
        code: CodeError,
        *caution: str,
        node: InfoNode | StackInfo | None = None,
        raise_exception: bool = True,
    ) -> error.ParserError:
        """
        EN: Record a syntax error in telemetry and optionally raise ParserError.
        ES: Registra un error sintáctico en telemetría y opcionalmente levanta ParserError.

        Args:
            message: Descriptive failure explanation.
                     Explicación descriptiva del fallo.
            code: Standardized CodeError token.
                  Código de error estandarizado CodeError.
            caution: Optional cautionary contextual remarks.
                     Notas de advertencia contextuales opcionales.
            node: Target telemetry node override.
                  Nodo destino de telemetría opcional.
            raise_exception: If True, immediately raises ParserError.
                             Si es True, levanta ParserError inmediatamente.

        Returns:
            Constructed ParserError instance.
            Instancia ParserError construida.
        """
        target = self._get_target_node(node)

        if getattr(config, 'PARSER_ADD_ERROR', True) and hasattr(target, 'note'):
            target.note(f"Error sintáctico: {message} ({code})", 'error')

        err = error.ParserError(message, code, *caution)
        self._errors.append(err)
        if raise_exception:
            err.raise_error()
        return err

    # ==========================================================================
    # CONSULTA, ESTADO Y LOOKAHEAD
    # ==========================================================================

    def count(self) -> int:
        """
        EN: Return the total number of tokens in the stream.
        ES: Devuelve la cantidad total de tokens en el flujo.
        """
        return len(self._tokens)

    def remaining(self) -> int:
        """
        EN: Return the count of unconsumed tokens from current physical position.
        ES: Cantidad de tokens pendientes de consumir desde el cursor físico.
        """
        return max(0, len(self._tokens) - self._pos)

    def not_empty(self) -> bool:
        """
        EN: Check whether tokens remain available from physical cursor.
        ES: Indica si existen tokens disponibles desde el cursor físico.
        """
        return self._pos < len(self._tokens)

    def virtual_not_empty(self) -> bool:
        """
        EN: Check whether tokens remain available from virtual cursor.
        ES: Indica si existen tokens disponibles desde el cursor virtual.
        """
        return self._virtual_pos < len(self._tokens)

    def is_eof(self) -> bool:
        """
        EN: Check whether the physical cursor is at or past the EOF token.
        ES: Indica si el cursor físico se encuentra en o más allá del token EOF.
        """
        if not self.not_empty():
            return True
        from gram.core.lexer.tokens import Token
        curr = self._tokens[self._pos]
        return curr.token == Token.EOF or curr.token.name == 'EOF'

    def peek(self, offset: int = 0, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Non-destructively inspect token at relative offset from physical cursor.
        ES: Inspecciona el token ubicado a `offset` posiciones del cursor físico actual.

        Args:
            offset: Relative index offset from physical cursor (default 0).
                    Desplazamiento relativo respecto al cursor físico (por defecto 0).
            node: Optional telemetry node for diagnostic logging.
                  Nodo de telemetría opcional para registro de diagnóstico.

        Returns:
            TokenType at relative position or None if out of bounds.
            TokenType en la posición relativa o None si excede los límites.
        """
        index = self._pos + offset
        if 0 <= index < len(self._tokens):
            return self._tokens[index]
        return None

    def peek_token(self, offset: int = 0, node: InfoNode | None = None) -> Token | None:
        """
        EN: Return the enum Token type at relative offset from physical cursor.
        ES: Devuelve el tipo de token (Enum Token) en la posición relativa `offset`.

        Args:
            offset: Relative index offset from physical cursor (default 0).
                    Desplazamiento relativo respecto al cursor físico (por defecto 0).
            node: Optional telemetry node for diagnostic logging.
                  Nodo de telemetría opcional para registro de diagnóstico.

        Returns:
            Enum Token type or None if out of bounds.
            Tipo Enum Token o None si excede los límites.
        """
        tok = self.peek(offset, node=node)
        return tok.token if tok is not None else None

    def lookahead(self, count: int = 1, node: InfoNode | None = None) -> list[TokenType]:
        """
        EN: Fetch next `count` tokens ahead of physical cursor without consuming.
        ES: Obtiene los siguientes `count` tokens a partir del cursor físico actual sin consumirlos.

        Args:
            count: Number of upcoming tokens to inspect (default 1).
                   Cantidad de tokens a inspeccionar hacia adelante (por defecto 1).
            node: Optional telemetry node for diagnostic logging.
                  Nodo de telemetría opcional para registro de diagnóstico.

        Returns:
            List of upcoming tokens up to end of stream.
            Lista de próximos tokens hasta el final del flujo.
        """
        end = min(self._pos + count, len(self._tokens))
        return self._tokens[self._pos:end]

    def matches(
        self,
        *expected: Token | str,
        offset: int = 0,
        node: InfoNode | None = None,
    ) -> bool:
        """
        EN: Check whether token at relative offset matches any expected token type or value.
        ES: Comprueba si el token en la posición relativa `offset` coincide con alguno
            de los tipos de token o nombres esperados.

        Args:
            *expected: Target Token enum variants, token names, or literal strings.
                       Variantes de Token enum, nombres de token o cadenas literales esperadas.
            offset: Relative index offset from physical cursor (default 0).
                    Desplazamiento relativo respecto al cursor físico (por defecto 0).
            node: Optional telemetry node for diagnostic logging.
                  Nodo de telemetría opcional para registro de diagnóstico.

        Returns:
            True if matched, False otherwise.
            True si coincide, False en caso contrario.
        """
        tok = self.peek(offset, node=node)
        if tok is None:
            return False

        for exp in expected:
            if isinstance(exp, str):
                if tok.token.name == exp or str(tok.value) == exp:
                    return True
            else:
                if tok.token == exp:
                    return True
        return False

    def slice(self, start: int, end: int) -> list[TokenType]:
        """
        EN: Extract a slice of tokens between indices without changing cursor state.
        ES: Extrae un rango arbitrario de tokens sin alterar el estado del parser.

        Args:
            start: Starting token index (inclusive).
                   Índice inicial de token (inclusivo).
            end: Ending token index (exclusive).
                 Índice final de token (exclusivo).

        Returns:
            Extracted token sublist.
            Sublista de tokens extraída.
        """
        return self._tokens[max(0, start):min(end, len(self._tokens))]

    # ==========================================================================
    # PUNTOS DE GUARDADO Y BACKTRACKING
    # ==========================================================================

    def savepoint(self, node: InfoNode | None = None) -> Checkpoint:
        """
        EN: Capture an immutable snapshot of cursor positions and bracket depth.
        ES: Genera una captura inmutable del estado actual de los cursores físico y virtual
            y la profundidad de brackets para posibilitar backtracking seguro.

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            Immutable Checkpoint snapshot.
            Instantánea inmutable Checkpoint.
        """
        target = self._get_target_node(node)
        cp = Checkpoint(
            pos=self._pos,
            virtual_pos=self._virtual_pos,
            bracket_depth=self._bracket_depth,
            target_node=target,
        )

        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Savepoint creado: pos={cp.pos}, virtual={cp.virtual_pos}, bracket={cp.bracket_depth}",
                'normal',
                node=target,
            )

        return cp

    def restore(
        self,
        checkpoint: Checkpoint | int,
        node: InfoNode | None = None,
    ) -> None:
        """
        EN: Restore parser state to a prior savepoint, unwinding consumed tokens.
        ES: Restaura el parser a un estado previo guardado, deshaciendo
            el consumo de tokens tras una alternativa fallida.

        Args:
            checkpoint: Checkpoint snapshot or raw integer position to restore to.
                        Instantánea Checkpoint o posición entera a restaurar.
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.
        """
        target = self._get_target_node(node)

        if isinstance(checkpoint, Checkpoint):
            new_pos = checkpoint.pos
            new_virtual = checkpoint.virtual_pos
            self._bracket_depth = checkpoint.bracket_depth
        else:
            new_pos = checkpoint
            new_virtual = checkpoint

        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Backtracking: restaurando cursor físico {self._pos} -> {new_pos}",
                'advice',
                node=target,
            )

        self._pos = max(0, min(new_pos, len(self._tokens)))
        self._virtual_pos = max(0, min(new_virtual, len(self._tokens)))

    @contextmanager
    def transaction(self, node: InfoNode | None = None) -> Iterator[Checkpoint]:
        """
        EN: Context manager for atomic syntax transactions with automatic rollback on error.
        ES: Gestor de contexto para transacciones sintácticas atómicas con rollback automático.

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Yields:
            Initial Checkpoint of the transaction.
            Checkpoint inicial de la transacción.
        """
        target = self._get_target_node(node)
        cp = self.savepoint(target)
        try:
            yield cp
        except Exception:
            self.restore(cp, target)
            raise

    # ==========================================================================
    # EXPLORACIÓN VIRTUAL Y COMMIT/ROLLBACK
    # ==========================================================================

    def future(self, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Fetch token at virtual cursor and advance virtual cursor, leaving physical cursor intact.
        ES: Obtiene el token bajo el cursor virtual y avanza dicho cursor una posición,
            sin afectar el cursor físico real.

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            Token under virtual cursor or None if exhausted.
            Token bajo el cursor virtual o None si está agotado.
        """
        target = self._get_target_node(node)

        if not self.virtual_not_empty():
            return None

        token = self._tokens[self._virtual_pos]
        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Consultando virtual [{self._virtual_pos}]: {token.token.name} = {token.value!r}",
                'normal',
                node=target,
            )

        self._virtual_pos += 1
        return token

    def peek_virtual(self, offset: int = 0, node: InfoNode | None = None) -> TokenType | None:
        """
        EN: Inspect token relative to current virtual cursor without moving it.
        ES: Inspecciona un token relativo a la posición virtual actual sin mover el cursor.

        Args:
            offset: Relative index offset from virtual cursor (default 0).
                    Desplazamiento relativo respecto al cursor virtual (por defecto 0).
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            Token at offset or None if out of bounds.
            Token en la posición relativa o None si excede límites.
        """
        index = self._virtual_pos + offset
        if 0 <= index < len(self._tokens):
            return self._tokens[index]
        return None

    def set_virtual_token(self, pos: int, node: InfoNode | None = None) -> int:
        """
        EN: Manually adjust virtual cursor position (-1 = last token, -2 = sync with physical cursor).
        ES: Establece manualmente la posición del cursor virtual (-1 = último token, -2 = sincronizar con físico).

        Args:
            pos: New virtual position (-1 for last, -2 to sync with physical cursor).
                 Nueva posición virtual (-1 para último, -2 para sincronizar con cursor físico).
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            Effective virtual cursor position.
            Posición efectiva del cursor virtual.
        """
        target = self._get_target_node(node)

        if pos == -1:
            new_pos = max(0, self.count() - 1)
        elif pos == -2:
            new_pos = self._pos
        else:
            new_pos = pos

        if new_pos < 0 or new_pos > self.count():
            if getattr(config, 'PARSER_ADD_ERROR', True):
                self.note(
                    f"Posición virtual fuera de rango: {new_pos} (válido: 0..{self.count()})",
                    'error',
                    node=target,
                )
            return self._virtual_pos

        old_pos = self._virtual_pos
        self._virtual_pos = new_pos

        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Cursor virtual actualizado: {old_pos} -> {self._virtual_pos}",
                'success',
                node=target,
            )

        return self._virtual_pos

    def reset_virtual(self, node: InfoNode | None = None) -> None:
        """
        EN: Reset virtual cursor back to synchronize with the current physical cursor.
        ES: Restablece el cursor virtual sincronizándolo con el cursor físico actual.

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.
        """
        target = self._get_target_node(node)
        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Restableciendo cursor virtual: {self._virtual_pos} -> {self._pos}",
                'advice',
                node=target,
            )
        self._virtual_pos = self._pos

    def rollback(self, node: InfoNode | None = None) -> None:
        """
        EN: Discard speculative virtual exploration (alias for reset_virtual).
        ES: Descarta la exploración virtual especulativa (alias de reset_virtual).

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.
        """
        self.reset_virtual(node)

    def commit(self, node: InfoNode | None = None) -> list[TokenType]:
        """
        EN: Commit virtual traversal into physical cursor, consuming examined tokens.
        ES: Sincroniza el cursor físico con el virtual, consumiendo tokens explorados.

        Args:
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            List of newly consumed tokens during commit interval.
            Lista de tokens consumidos en el intervalo de confirmación.
        """
        target = self._get_target_node(node)
        consumed: list[TokenType] = []

        if self._virtual_pos > self._pos:
            consumed = self._tokens[self._pos:self._virtual_pos]
            if getattr(config, 'PARSER_ADD_INFO', True):
                self.note(
                    f"Commit: consumidos físicamente {len(consumed)} tokens ({self._pos} -> {self._virtual_pos})",
                    'success',
                    node=target,
                )
            self._pos = self._virtual_pos
            if self.watcher is not None and consumed:
                self.watcher.update_token(consumed[-1])

        return consumed

    # ==========================================================================
    # RECUPERACIÓN Y LIMPIEZA
    # ==========================================================================

    def quit(self, tok: Token, node: InfoNode | None = None) -> int:
        """
        EN: Strip all occurrences of the specified token type from stream and adjust cursors.
        ES: Elimina del flujo todos los tokens del tipo especificado y reajusta los cursores.

        Args:
            tok: Target Token enum type to purge from the token list.
                 Tipo Token enum a purgar de la lista de tokens.
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            Count of removed tokens.
            Cantidad de tokens eliminados.
        """
        target = self._get_target_node(node)
        initial_size = len(self._tokens)

        self._tokens = [t for t in self._tokens if t.token != tok]
        removed = initial_size - len(self._tokens)

        if getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Quit: se eliminaron {removed} tokens de tipo {tok.name}",
                'success',
                node=target,
            )

        self._pos = min(self._pos, len(self._tokens))
        self._virtual_pos = min(self._virtual_pos, len(self._tokens))
        return removed

    def synchronize(
        self,
        sync_tokens: tuple[Token, ...] | None = None,
        node: InfoNode | None = None,
    ) -> list[TokenType]:
        """
        EN: Panic-mode recovery: consume tokens until a safe synchronization delimiter is found.
        ES: Recuperación en modo pánico: consume tokens hasta hallar un delimitador seguro.

        Args:
            sync_tokens: Tuple of synchronization delimiter tokens (default NEWLINE, DEDENT, EOF).
                         Tupla de delimitadores de sincronización (por defecto NEWLINE, DEDENT, EOF).
            node: Optional target telemetry node.
                  Nodo de telemetría de destino opcional.

        Returns:
            List of discarded tokens during recovery synchronization.
            Lista de tokens descartados durante la sincronización de recuperación.
        """
        target = self._get_target_node(node)
        if sync_tokens is None:
            from gram.core.lexer.tokens import Token as T
            sync_tokens = (T.NEWLINE, T.DEDENT, T.EOF)

        discarded: list[TokenType] = []
        while self.not_empty():
            curr = self._tokens[self._pos]
            if curr.token in sync_tokens:
                break
            discarded.append(curr)
            self._pos += 1

        if discarded and getattr(config, 'PARSER_ADD_INFO', True):
            self.note(
                f"Sincronización: se descartaron {len(discarded)} tokens hasta delimitador seguro",
                'advice',
                node=target,
            )

        return discarded


__all__ = ['ParseControl']
