"""
Motor del Analizador Léxico de Gram (`gram.core.lexer`).
=========================================================
Convierte líneas de código fuente en un flujo ordenado de objetos `TokenType`.
Gestiona niveles de indentación jerárquica (INDENT/DEDENT), comentarios,
espacios, saltos de línea (NEWLINE) y fin de archivo (EOF), delegando el
reconocimiento de literales, identificadores y símbolos a los visitors especializados.

Version 1.0.0
"""
from __future__ import annotations
def Version():
    return "1.0.0"

from typing import Sequence
from pathlib import Path
from gram import config, errors
from gram.utilities import error
from gram.utilities.info.stack import StackInfo
from gram.core.lexer.items import TokenStream
from gram.core.lexer import items, tokens, visitors, words

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
            'EmptyKeywords',
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
    _stack: StackInfo = StackInfo(
        'lexer-log',
        'LEXER',
        'Registro y diagnóstico del analizador léxico',
        expose_nodes=True,
        generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR,
        generate_log_file=config.INFO_GENERATE_LOGFILE and config.LEXER_ADD_INFO,
    )
    
    @classmethod
    def get_stack(cls):
        return cls._stack
    
    @classmethod
    def reset_stack(cls):
        cls._stack: StackInfo = StackInfo(
            'lexer-log',
            'LEXER',
            'Registro y diagnóstico del analizador léxico',
            expose_nodes=True,
            generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR,
            generate_log_file=config.INFO_GENERATE_LOGFILE,
        )
    
    def __init__(
        self,
        source: Sequence[str] | str | Path,
    ) -> None:
        if isinstance(source, str):
            self.source: list[str] = source.splitlines()
        elif isinstance(source, Path):
            if not source.exists():
                self.stack.note(f"El archivo {source.as_uri()} no existe", 'fatal')
                error.LexerError('FileNotFound',errors.LEXER_FILE_NOT_FOUND, f"El archivo {source.as_uri()} no existe")
            else:
                self.source = source.read_text(encoding='utf-8').splitlines(keepends=True)
        else:
            self.source = list(source)
            
        Lexer.reset_stack()
            
        self.line: int = 0
        self.col: int = 0
        self.indents: list[int] = [0]
        self.comment_token = Token.from_string(config.LEXER_COMMENT_TOKEN)


        self.info_node = self.stack.node(
            'LEXER',
            f'Inicializando lexer con {len(self.source)} líneas',
            priority=2,
        )

        if config.LEXER_ADD_INFO:
            self.info_node.note(
                f'Lexer inicializado. Procesando {len(self.source)} líneas de entrada',
                'success',
            )

    @property
    def stack(self):
        return Lexer._stack

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

    def fail(self, name: str, code: errors.coderr, *caution: str) -> None:
        """
        Registra un error léxico en la pila de telemetría y detiene la ejecución.

        Args:
            name: Descripción legible del error.
            code: Código OSGDC numérico o CodeError correspondiente.
            *caution: Sugerencias o precauciones para mitigar el error.
        """
        if config.LEXER_ADD_ERROR:
            self.info_node.note(f'Error léxico: {name}', 'error')

        error.LexerError(name, code, *caution).raise_error()

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
            if config.LEXER_ADD_INFO:
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
                if config.LEXER_ADD_INFO:
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
        if isinstance(comment_config, (tuple, list, set)):
            for tok in comment_config:
                if isinstance(tok, str):
                    if (len(tok) == 1 and char == tok) or self.currline[self.col:self.col + len(tok)] == tok:
                        return True
                elif isinstance(tok, Token) and MAP_SYMBOLS.get(char) == tok:
                    return True
            return False
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
        comment_len = 1
        if isinstance(self.comment_token, str):
            comment_len = len(self.comment_token)
        elif isinstance(self.comment_token, (tuple, list, set)):
            for tok in self.comment_token:
                if isinstance(tok, str) and self.currline[self.col:].startswith(tok):
                    comment_len = len(tok)
                    break
        self.col += comment_len
        content = self.currline[self.col:]
        self.col = len(self.currline)

        if config.LEXER_ADD_INFO:
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

        if config.LEXER_ADD_INFO:
            self.info_node.note('Iniciando análisis léxico', 'normal')

        while self.has_lines():
            if self.is_empty():
                if not config.LEXER_IGNORE_EMPTY_LINES and not config.LEXER_IGNORE_NEWLINES:
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
                    if config.LEXER_SAVE_COMMENTS:
                        tokens_list.append(self.process_comment())
                    else:
                        self.col = len(self.currline)
                    break

                # Despachar al visitor especializado correspondiente
                token = visitors.visit(self, char)
                tokens_list.append(token)

            # Salto de línea al terminar la línea física (omitido si ignore_newlines está activo)
            if not config.LEXER_IGNORE_NEWLINES:
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

        if config.LEXER_ADD_INFO:
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

