"""
ES:
    Pila Global de Registro de Errores (StackError).
    =================================================
    Mantiene el registro histórico en memoria de todos los errores instanciados
    durante el ciclo de vida del framework y gestiona su volcado persistente a disco.

EN:
    Global Error Registry Stack (StackError).
    =================================================
    Maintains the in-memory historical record of all error instances generated
    during the framework's lifecycle and manages their persistent dump to disk.
"""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from gram.utilities.error import Error


class StackError:
    """
    ES:
        Gestiona la recolección global estática de excepciones de tipo `Error`.
        
        Actúa como un Singleton que registra cronológicamente los errores.
        Permite inspeccionar el estado actual de los fallos del framework y 
        escribir el log completo en un archivo de texto definido en `LOGFILE`.

    EN:
        Manages the static global collection of `Error` type exceptions.
        
        Acts as a Singleton that chronologically records errors.
        Allows inspecting the current state of framework failures and 
        writing the complete log to a text file defined in `LOGFILE`.
    """

    LOGFILE: ClassVar[Path] = Path('log/error.log')
    __err__: ClassVar[list[Error]] = []
    
    @classmethod
    def write(cls) -> None:
        """
        ES:
            Escribe secuencialmente todos los errores registrados en el archivo de log.
            
            Si los directorios padres de `LOGFILE` no existen, los crea automáticamente.
            Los errores se escriben en modo texto plano (sin colores ANSI) para
            garantizar la correcta lectura en editores de texto.

        EN:
            Sequentially writes all registered errors to the log file.
            
            If the parent directories of `LOGFILE` do not exist, they are created 
            automatically. Errors are written in plain text mode (without ANSI colors) 
            to ensure proper reading in text editors.
        """
        try:
            cls.LOGFILE.parent.mkdir(parents=True, exist_ok=True)
            with cls.LOGFILE.open('w', encoding='utf-8') as file:
                for error in cls.__err__: 
                    file.write(error.stringify(ansi=False))
                    file.write('\n\n')
        except OSError as exc:
            print(f'ERROR al escribir en el archivo log {cls.LOGFILE}: {exc}')    
    
    @classmethod
    def add(cls, error: Error) -> None:
        """
        ES:
            Añade una nueva instancia de error al final de la pila global.

        EN:
            Adds a new error instance to the end of the global stack.
        """
        cls.__err__.append(error)
        
    @classmethod
    def last(cls) -> Error | None:
        """
        ES:
            Recupera el último error que fue registrado en la pila.
            Retorna `None` si la pila se encuentra vacía.

        EN:
            Retrieves the last error that was registered in the stack.
            Returns `None` if the stack is empty.
        """
        if not cls.__err__:
            return None
        return cls.__err__[-1]
    
    @classmethod
    def all(cls) -> list[Error]:
        """
        ES:
            Retorna una copia superficial de la lista que contiene todos los errores.
            Útil para iterar sobre los errores sin riesgo de mutar la pila original.

        EN:
            Returns a shallow copy of the list containing all errors.
            Useful for iterating over errors without risking mutation to the original stack.
        """
        return cls.__err__.copy()
    
    @classmethod
    def count(cls) -> int:
        """
        ES:
            Devuelve la cantidad total de errores almacenados en la pila actual.

        EN:
            Returns the total number of errors stored in the current stack.
        """
        return len(cls.__err__)
    
    @classmethod
    def clear(cls) -> None:
        """
        ES:
            Limpia completamente el registro, eliminando todos los errores de la pila.

        EN:
            Completely clears the registry, removing all errors from the stack.
        """
        cls.__err__.clear()
        
    @classmethod
    def empty(cls) -> bool:
        """
        ES:
            Comprueba si la pila de registro de errores está completamente vacía.

        EN:
            Checks whether the error registry stack is completely empty.
        """
        return len(cls.__err__) == 0


__all__ = [
    'StackError'
]