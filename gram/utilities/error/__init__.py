"""
ES:
    Sistema Jerárquico de Errores del Framework Gram.
    ==================================================
    Proporciona la clase base `Error` y sus especializaciones por subsistema 
    (Lexer, Parser, AST, Grammar, Compilation, Plugin).
    Integra detección automática del frame de origen, formateo visual en caja,
    compatibilidad ANSI y registro en la pila global `StackError`.

    Nota: Este sistema será apartado en versiones futuras, pero mantendrá su 
    compatibilidad hacia atrás para no afectar el funcionamiento de Gram.

EN:
    Gram Framework Hierarchical Error System.
    ==================================================
    Provides the base `Error` class and its subsystem specializations
    (Lexer, Parser, AST, Grammar, Compilation, Plugin).
    Integrates automatic origin frame detection, boxed visual formatting,
    ANSI compatibility, and registration in the global `StackError` stack.

    Note: This system will be deprecated in future versions but will maintain 
    backward compatibility so Gram continues to function identically.
"""
from __future__ import annotations
import inspect
from pathlib import Path
from types import FrameType

from gram.utilities.error import codes, stack
from gram.utilities import Format


class Error(Exception):
    """
    ES:
        Representa la clase base para todos los errores dentro del framework Gram.
        
        Hereda de `Exception` y proporciona un marco estructurado para reportar 
        errores visuales, incluyendo códigos formales ensamblados dinámicamente, 
        mensajes de precaución multilinea y un seguimiento exacto del archivo 
        de origen que invocó la falla.

    EN:
        Represents the base class for all errors within the Gram framework.
        
        Inherits from `Exception` and provides a structured framework for 
        reporting visual errors, including dynamically assembled formal codes, 
        multiline caution messages, and exact origin tracking of the file 
        that invoked the failure.
    """

    name: str
    code: codes.CodeError
    caution: tuple[str, ...]
    origin: str

    def __init__(
        self,
        name: str,
        code: codes.CodeError,
        *caution: str
    ) -> None:
        """
        ES:
            Inicializa el error estructurado capturando su contexto de origen.
            
            Ensambla el nombre del error, su código formal asociado y una tupla
            de cadenas que representan párrafos explicativos (`caution`). 
            Inmediatamente rastrea la pila de llamadas para determinar qué archivo 
            lanzó la excepción.

        EN:
            Initializes the structured error by capturing its origin context.
            
            Assembles the error name, its associated formal code, and a tuple
            of strings representing explanatory paragraphs (`caution`). 
            It immediately inspects the call stack to determine which file 
            raised the exception.
        """
        super().__init__(caution)
        self.name = name
        self.code = code
        self.caution = caution
        
        caller: FrameType | None = inspect.currentframe().f_back if inspect.currentframe() else None
        self.origin = Error.origin_error(caller)

    @classmethod
    def origin_error(cls, caller: FrameType | None) -> str:
        """
        ES:
            Resuelve la ruta absoluta del archivo que originó la excepción.
            Si la resolución de la ruta absoluta falla, retorna la ruta estática
            proporcionada por el intérprete.

        EN:
            Resolves the absolute path of the file that originated the exception.
            If resolving the absolute path fails, it falls back to returning 
            the static path provided by the interpreter.
        """
        if caller is None:
            return 'unknown'

        try:
            return str(Path(caller.f_code.co_filename).resolve())
        except (OSError, ValueError):
            return caller.f_code.co_filename

    def __str__(self) -> str:
        """
        ES: Retorna el nombre del error al convertir la instancia a cadena.
        EN: Returns the error name when converting the instance to a string.
        """
        return self.name
    
    def get_index(self) -> int:
        """
        ES:
            Obtiene el índice secuencial de este error dentro de la pila global.
            Retorna -1 si el error aún no ha sido registrado.

        EN:
            Retrieves the sequential index of this error within the global stack.
            Returns -1 if the error has not been registered yet.
        """
        try:
            return stack.StackError.__err__.index(self)
        except ValueError:
            return -1
        
    def _format_box(self, text: str) -> str:
        """
        ES:
            Envuelve una cadena de texto dentro de una caja decorativa centrada,
            basándose en la configuración de la constante `Format.line`.

        EN:
            Wraps a text string inside a centered decorative box, based on 
            the global `Format.line` configuration.
        """
        box_width: int = len('|' + (Format.line * 38) + '|')
        inner_length: int = box_width - 2
        text_length: int = len(text)
        remaining: int = max(0, inner_length - text_length)
        left: int = remaining // 2
        right: int = remaining - left
        
        return (
            '|'
            + Format.line * left
            + f' {text} '
            + Format.line * right
            + '|'
        )
        
    def stringify(self, ansi: bool = False) -> str:
        """
        ES:
            Construye la representación final en texto del error.
            Ensambla los encabezados dinámicos, el texto de la advertencia separado
            por párrafos y los metadatos de origen. Permite inyectar códigos ANSI.

        EN:
            Builds the final textual representation of the error.
            Assembles the dynamic headers, the caution text separated by paragraphs, 
            and the origin metadata. Allows injecting ANSI codes.
        """
        code: str = self.code.stringify()
        
        top_header: str = self._format_box('ERROR')
        bottom_header: str = self._format_box(f'eof {self.get_index()}')
        
        caution_text: str = (
            '\n\n'.join(self.caution) 
            if self.caution 
            else 'No se proporcionó información adicional.'
        )
        
        lines: list[str] = [
            top_header,
            f'Name: {self.name}, Type: {self.__class__.__name__}.\n',
            f'CAUTION: {caution_text}',
            f'\nINF:\n    ORIGIN: {self.origin}\n    CODE: {code}\n',
            bottom_header
        ]
        
        if ansi:
            return (
                f'{Format.ARED}{Format.ABOLD}{lines[0]}{Format.ARESET}\n'
                f'{Format.ARED}Name : {self.name}, Type: '
                f'{Format.AGREEN}{self.__class__.__name__}{Format.ARED}\n\n'
                f'{Format.ARESET}'
                f'{Format.AYELLOW}CAUTION: {Format.ARESET}'
                f'{caution_text}\n\n'
                f'{Format.ARED}INF:{Format.ARESET}\n'
                f'    ORIGIN: {self.origin}\n'
                f'    CODE: {code}\n'
                f'{Format.ARED}{Format.ABOLD}{lines[-1]}{Format.ARESET}'
            )
            
        return '\n'.join(lines)
    
    def print(self) -> None:
        """
        ES:
            Imprime el error en la salida estándar intentando utilizar colores ANSI si están habilitados.
            Si el terminal falla al codificar los caracteres (por ejemplo en Windows cp1252),
            realiza un fallback seguro reemplazando caracteres no mapeables.

        EN:
            Prints the error to standard output trying to use ANSI colors if enabled.
            If the terminal fails to encode characters (e.g. on Windows cp1252),
            it safely falls back by replacing unmappable characters.
        """
        import sys
        from gram import config
        ansi = getattr(config, 'ERROR_SUPPORT_ANSI', False)
        try:
            print(self.stringify(ansi=ansi))
        except (UnicodeEncodeError, UnicodeError):
            try:
                encoding = sys.stdout.encoding or 'ascii'
                safe_text = self.stringify(ansi=False).encode(encoding, errors='replace').decode(encoding)
                print(safe_text)
            except Exception:
                print(f"ERROR: {self.name} - {self.caution}")

    def raise_error(self, exit: bool = False) -> None:
        """
        ES:
            Imprime el formato visual del error en la consola si no está silenciado.
            Si `exit` es True y `ERROR_EXIT_ON_ERROR` es True, detiene el proceso con sys.exit(1).
            En caso contrario, lanza la excepción actual (`raise self`).

        EN:
            Prints the visual format of the error to the console if not muted.
            If `exit` is True and `ERROR_EXIT_ON_ERROR` is True, exits the process with sys.exit(1).
            Otherwise, raises the current exception (`raise self`).
        """
        import sys
        from gram import config
        if not getattr(config, 'ERROR_HIDE_CONSOLE', False):
            self.print()
        if exit and getattr(config, 'ERROR_EXIT_ON_ERROR', False):
            sys.exit(1)
        raise self


class LexerError(Error):
    """Excepción estructurada para errores en la fase léxica."""


class ParserError(Error):
    """Excepción estructurada para errores en la fase sintáctica (parsing)."""


class ASTError(Error):
    """Excepción estructurada para errores en construcción o análisis del AST."""


class GrammarError(Error):
    """Excepción estructurada para errores en reglas y combinadores gramaticales."""


class CompilationError(Error):
    """Excepción estructurada para errores en meta-compilación y DSLs."""


class PluginError(Error):
    """Excepción estructurada para errores en manifiestos y ciclo de vida de plugins."""


__all__ = [
    'Error',
    'LexerError',
    'ParserError',
    'ASTError',
    'GrammarError',
    'CompilationError',
    'PluginError',
]