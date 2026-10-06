"""
Pila de Telemetría y Contenedor Jerárquico (Stack).
===================================================
Proporciona la interfaz de alto nivel para agrupar nodos y notas de telemetría
bajo un archivo de log y canalizar su salida por consola o archivo.
"""
from __future__ import annotations

import atexit
from pathlib import Path
from typing import ClassVar

from gram.utilities import Format
from gram.utilities.info.log import Log


class StackInfo:
    _stacks: ClassVar[list[StackInfo]] = []
    
    def __init__(
        self,
        file_name: str,
        node_name: str,
        description: str,
        expose_nodes: bool = False,
        generate_on_error: bool = False,
        generate_log_file: bool = False,
        ):
        
        if not file_name.endswith('.log'):
            file_name = file_name + '.log'
        
        self.file_name: str = file_name
        self.expose_nodes: bool = expose_nodes

        from gram.utilities.info import Node
        self.main: Node = Node(node_name, description, 0)
        self.log: Path | None = None
        if generate_log_file:
            self.register()
        
        if self.log and generate_on_error:
            atexit.register(self.write)
        
    def register(self):
        self.log = Log.register(self.file_name)
        
    def note(self, note: str, type: Format.LogType = 'normal'):
        return self.main.note(note, type)
    
    def node(self, name: str, description: str, priority: int = 0):
        return self.main.node(name, description, priority)
    
    def console(self):
        lines = list(self.main.stringify(
            level=0,
            expose_nodes=self.expose_nodes,
            ansi=False,
            format_list = True
        ))
        
        if lines:
            prefix = self.file_name.split('.')[0]
            header = lines[0]
            lines[0] = f'Stack {prefix} {header}'
            print('\n'.join(lines))
            
    def stringify(self, ansi: bool = False):
        lines = list(self.main.stringify(
            level=0,
            expose_nodes=self.expose_nodes,
            ansi=ansi,
            format_list=True
        ))

        if lines:
            prefix = self.file_name.split('.')[0]
            header = lines[0]
            lines[0] = f"Stack {prefix} {header}"
            return '\n'.join(lines)
        return ''

    def write(self) -> None:
        """Persiste el contenido del stack en el archivo de log si está configurado."""
        Log.write(self.stringify(ansi=False), self.file_name)

    @classmethod
    def show_all(cls) -> None:
        """Vuelca y muestra todos los stacks registrados en el ciclo de ejecución."""
        for stack in cls._stacks:
            stack.write()
            stack.console()

    @classmethod
    def clear_all(cls) -> None:
        """Limpia los stacks registrados (útil para pruebas unitarias)."""
        cls._stacks.clear()


__all__ = ['StackInfo']
