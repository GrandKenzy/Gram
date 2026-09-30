"""
Motor del Analizador Léxico de Gram (`gram.core.lexer`).
=========================================================
Convierte líneas de código fuente en un flujo ordenado de objetos `TokenType`.
Gestiona niveles de indentación jerárquica (INDENT/DEDENT), comentarios,
espacios, saltos de línea (NEWLINE) y fin de archivo (EOF), delegando el
reconocimiento de literales, identificadores y símbolos a los visitors especializados.
"""
from __future__ import annotations

from typing import Sequence

from gram import config, errors
from gram.core.lexer import items, stack, tokens, visit, word, words
from gram.core.lexer.items import TokenStream
from gram.core.lexer.tokens import (
    CustomToken,
    MAP_SYMBOLS,
    Token,
    TokenType,
    get_sorted_symbols,
    get_tokens,
)
from gram.core.lexer.words import (
    Keyword,
    WordGroup,
    WordGroupManager,
    add_group,
    add_keyword,
    all_group_names,
    all_groups,
    all_keyword_names,
    all_keywords,
    clear_all,
    count_keywords,
    create_group,
    exists_in_group,
    get_group,
    get_keyword,
    group_exists,
    groups,
    is_empty,
    keyword_exists,
    remove_group,
    remove_keyword,
)
from gram.utilities import error


def check_state() -> int:
    """
    Verifica que existan palabras clave registradas antes de procesar el código.

    Returns:
        int: Cantidad de palabras clave registradas en el catálogo.

    Raises:
        LexerError: Si no hay ninguna palabra clave en el sistema.
    """
    if words.is_empty():
        error.LexerError(
            'EMPTY KEYWORDS',
            errors.EMPTY_KEYWORDS,
            'No se encontró ninguna palabra clave registrada. Registre al menos una mediante words.add_keyword() o Keyword.add().',
        ).raise_error()
    return words.count_keywords()


class Lexer:
    """
    ES:
        Analizador léxico principal de Gram Framework.
        Transforma código fuente estructurado en un flujo de tokens con trazabilidad.

    EN:
        Main lexical analyzer for the Gram Framework.
        Transforms structured source code into a traceable token stream.
    """

    def __init__(
        self,
        source: Sequence[str] | str,
        comment_token: str | Token | None = None,
        save_comments: bool | None = None,
        ignore_newlines: bool | None = None,
    ) -> None:
        """
        Inicializa el analizador léxico con el código fuente y opciones opcionales.

        Args:
            source: Líneas de código fuente (o cadena con saltos de línea).
            comment_token: Carácter, delimitador o Token para comentarios.
            save_comments: Si se deben incluir los comentarios en el flujo de tokens.
            ignore_newlines: Si es True, no guarda tokens Token.NEWLINE.
        """
        if isinstance(source, str):
            self.source: list[str] = source.splitlines()
        else:
            self.source = list(source)

        self.comment_token = comment_token if comment_token is not None else getattr(config, 'LEXER_COMMENT_TOKEN', '#')
        self.save_comments = save_comments if save_comments is not None else getattr(config, 'LEXER_SAVE_COMMENTS', True)
        self.ignore_newlines = ignore_newlines if ignore_newlines is not None else getattr(config, 'LEXER_IGNORE_NEWLINES', True)
        self.line: int = 0
        self.col: int = 0
        self.indents: list[int] = [0]

        self.info_node = stack.stack.node(
            'LEXER',
            f'Inicializando lexer con {len(self.source)} líneas',
            priority=2,
        )

        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
            self.info_node.note(
                f'Lexer inicializado. Procesando {len(self.source)} líneas de entrada',
                'success',
            )

    @property
    def currline(self) -> str:
        """Devuelve la línea actual de código fuente con acceso seguro."""
        if 0 <= self.line < len(self.source):
            return self.source[self.line]
        return ''

    def has_lines(self) -> bool:
        """Indica si aún quedan líneas por procesar."""
        return self.line < len(self.source)

    def is_empty(self) -> bool:
        """Indica si la línea actual está vacía o solo contiene espacios en blanco."""
        return self.currline.strip() == ''

    def peek(self) -> str:
        """Devuelve el carácter en la posición actual del cursor sin consumirlo."""
        return self.currline[self.col]

    def advance(self) -> str:
        """Consume el carácter actual y avanza el cursor una columna."""
        char = self.peek()
        self.col += 1
        return char

    def fail(self, message: str, code: int | errors.codes.CodeError, *caution: str) -> None:
        """
        Registra un error léxico en la pila de telemetría y detiene la ejecución.

        Args:
            message: Descripción legible del error.
            code: Código OSGDC numérico o CodeError correspondiente.
            *caution: Sugerencias o precauciones para mitigar el error.
        """
        if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(self.info_node, 'note'):
            self.info_node.note(f'Error léxico: {message}', 'error')

        error.LexerError(message, code, *caution).raise_error()

    def process_indent(self) -> list[TokenType]:
        """
        Calcula la indentación inicial de la línea actual y genera tokens
        INDENT o DEDENT según corresponda.

        Returns:
            list[TokenType]: Lista de tokens INDENT o DEDENT generados.

        Raises:
            LexerError: Si el nivel de desindentación no coincide con ningún bloque previo.
        """
        generated: list[TokenType] = []
        indent = len(self.currline) - len(self.currline.lstrip(' '))
        current_indent = self.indents[-1]

        if indent > current_indent:
            self.indents.append(indent)
            generated.append(
                TokenType(
                    Token.INDENT,
                    indent,
                    self.line,
                    0,
                )
            )
            if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
                self.info_node.note(
                    f'INDENT generado: nivel {current_indent} -> {indent}',
                    'success',
                )

        elif indent < current_indent:
            while len(self.indents) > 1 and indent < self.indents[-1]:
                self.indents.pop()
                generated.append(
                    TokenType(
                        Token.DEDENT,
                        self.indents[-1],
                        self.line,
                        0,
                    )
                )
                if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
                    self.info_node.note(
                        f'DEDENT generado: nivel regresó a {self.indents[-1]}',
                        'success',
                    )

            if indent != self.indents[-1]:
                self.fail(
                    f'Indentación inválida en línea {self.line + 1}: {indent} espacios',
                    errors.LEXER_INDENTATION_MISMATCH,
                    f'El nivel de indentación actual no concuerda con ningún bloque anterior: {self.indents}.',
                )

        self.col = indent
        return generated

    def is_comment_start(self, char: str) -> bool:
        """
        Comprueba si el carácter actual corresponde al delimitador de comentario configurado.

        Args:
            char: Carácter inspeccionado bajo el cursor.

        Returns:
            bool: True si el carácter inicia un comentario.
        """
        comment_config = self.comment_token
        if isinstance(comment_config, str):
            if len(comment_config) == 1:
                return char == comment_config
            return self.currline[self.col:self.col + len(comment_config)] == comment_config
        if isinstance(comment_config, Token):
            return MAP_SYMBOLS.get(char) == comment_config
        return False

    def process_comment(self) -> TokenType:
        """
        Consume el resto de la línea física como token de comentario.

        Returns:
            TokenType: Token de comentario con el contenido restante de la línea.
        """
        start = self.col
        comment_len = len(self.comment_token) if isinstance(self.comment_token, str) else 1
        self.col += comment_len
        content = self.currline[self.col:]
        self.col = len(self.currline)

        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
            self.info_node.note(
                f'Comentario detectado en línea {self.line}, columna {start}',
                'normal',
            )

        return TokenType(
            Token.COMMENT,
            content,
            self.line,
            start,
        )

    def process(self) -> list[TokenType]:
        """
        Ejecuta el ciclo principal de análisis léxico sobre todas las líneas.

        Returns:
            list[TokenType]: Flujo ordenado y completo de tokens producidos.
        """
        check_state()
        tokens_list: list[TokenType] = []

        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
            self.info_node.note('Iniciando análisis léxico', 'normal')

        while self.has_lines():
            if self.is_empty():
                if not getattr(config, 'LEXER_IGNORE_EMPTY_LINES', True) and not self.ignore_newlines:
                    tokens_list.append(
                        TokenType(
                            Token.NEWLINE,
                            None,
                            self.line,
                            0,
                        )
                    )
                self.line += 1
                self.col = 0
                continue

            # Gestión de indentación al inicio de la línea física
            indent_tokens = self.process_indent()
            if indent_tokens:
                tokens_list.extend(indent_tokens)

            # Recorrido de caracteres dentro de la línea
            while self.col < len(self.currline):
                char = self.peek()

                # Ignorar espacios en blanco horizontales y retornos de carro
                if char in ' \r':
                    self.advance()
                    continue

                # Comentarios de línea
                if self.is_comment_start(char):
                    if self.save_comments:
                        tokens_list.append(self.process_comment())
                    else:
                        self.col = len(self.currline)
                    break

                # Despachar al visitor especializado correspondiente
                token = visit.process(self, char)
                tokens_list.append(token)

            # Salto de línea al terminar la línea física (omitido si ignore_newlines está activo)
            if not self.ignore_newlines:
                tokens_list.append(
                    TokenType(
                        Token.NEWLINE,
                        None,
                        self.line,
                        self.col,
                    )
                )

            self.line += 1
            self.col = 0

        # Cerrar bloques de indentación pendientes antes de EOF
        while len(self.indents) > 1:
            self.indents.pop()
            tokens_list.append(
                TokenType(
                    Token.DEDENT,
                    self.indents[-1],
                    self.line,
                    self.col,
                )
            )

        # Fin de archivo (EOF)
        tokens_list.append(
            TokenType(
                Token.EOF,
                None,
                self.line,
                self.col,
            )
        )

        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(self.info_node, 'note'):
            self.info_node.note(
                f'Análisis léxico completado. Total de tokens generados: {len(tokens_list)}',
                'success',
            )

        return tokens_list

    def stream(self) -> TokenStream:
        """
        Ejecuta el análisis léxico y devuelve un `TokenStream` listo para el parser.
        """
        return TokenStream(self.process())


def tokenize(
    source: Sequence[str] | str,
    comment_token: str | Token | None = None,
    save_comments: bool | None = None,
    ignore_newlines: bool | None = None,
) -> list[TokenType]:
    """
    Función de alto nivel para tokenizar código fuente directamente en una lista de tokens.

    Args:
        source: Código fuente como cadena multilínea o lista de líneas.
        comment_token: Delimitador de comentarios personalizado.
        save_comments: Si se deben incluir los tokens de comentario.
        ignore_newlines: Si es True, no guarda tokens NEWLINE.

    Returns:
        list[TokenType]: Secuencia completa de tokens.
    """
    return Lexer(
        source,
        comment_token=comment_token,
        save_comments=save_comments,
        ignore_newlines=ignore_newlines,
    ).process()


def tokenize_stream(
    source: Sequence[str] | str,
    comment_token: str | Token | None = None,
    save_comments: bool | None = None,
    ignore_newlines: bool | None = None,
) -> TokenStream:
    """
    Función de alto nivel para tokenizar código fuente y retornar un `TokenStream`.
    """
    return Lexer(
        source,
        comment_token=comment_token,
        save_comments=save_comments,
        ignore_newlines=ignore_newlines,
    ).stream()


__all__ = [
    # Analizador Léxico y Helpers
    'Lexer',
    'tokenize',
    'tokenize_stream',
    'check_state',
    # Tokens
    'Token',
    'TokenType',
    'CustomToken',
    'MAP_SYMBOLS',
    'get_tokens',
    'get_sorted_symbols',
    # Flujo de Tokens
    'TokenStream',
    # Catálogo de Palabras Clave y Grupos
    'Keyword',
    'WordGroup',
    'WordGroupManager',
    'groups',
    'add_keyword',
    'get_keyword',
    'keyword_exists',
    'remove_keyword',
    'all_keywords',
    'all_keyword_names',
    'is_empty',
    'count_keywords',
    'add_group',
    'create_group',
    'get_group',
    'group_exists',
    'remove_group',
    'all_groups',
    'all_group_names',
    'exists_in_group',
    'clear_all',
    # Módulos y submódulos
    'tokens',
    'words',
    'word',
    'visit',
    'items',
    'stack',
]
