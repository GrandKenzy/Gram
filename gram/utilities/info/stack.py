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

from .. import Format
from .log import Log


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
        

        name = Path(Format.FileTar.file).name if Format.FileTar.file else ''
            
        if not file_name.endswith('.log'):
            file_name = file_name + '.log'
        
        self.file_name: str = file_name
        self.expose_nodes: bool = expose_nodes
        self.folder_name = name

        from . import Node
        self.main: Node = Node(node_name, description, 0)
        self.log: Path | None = None
        self._targets: list[Node] = []
        if generate_log_file:
            self.register()
        
        if self.log and generate_on_error:
            atexit.register(self.write)

        type(self)._stacks.append(self)
        
    def register(self):
        if self.folder_name or Format.FileTar.file:
            file, i = Format.FileTar.get()
            fn = f'{file}-{i}' if file else ''
        else:
            fn = self.folder_name
        
        self.log = Log.register(self.file_name, fn)
        
    @property
    def target(self) -> Node | None:
        return self._targets[-1] if self._targets else None

    @property
    def targets(self) -> list[Node]:
        return self._targets

    def replace_targets(self, targets: list[Node]) -> None:
        """Replace the active target stack while preserving its list identity."""
        self._targets[:] = targets

    def current(self) -> Node:
        return self.target or self.main

    def node(
        self,
        name: str,
        description: str = '',
        priority: int = 0,
        *,
        set_target: bool = False,
        from_target: bool = True,
    ) -> Node:
        parent = self.current() if from_target else self.main
        child = parent.node(name, description, priority)
        if set_target:
            self._targets.append(child)
        return child

    def down(self, get: bool = False) -> Node | None:
        if not self._targets:
            return None
        node = self._targets.pop()
        return node if get else None

    def insert(self, node: Node) -> None:
        self.current().stack.append(node)

    def migrate(self, node: Node) -> None:
        target = self.target
        if target is None:
            raise RuntimeError('No active target defined for migration.')
        target.stack = node.stack

    def note(self, note: str, type: Format.LogType = 'normal'):
        return self.current().note(note, type)

    def emit(self, note: str, type: Format.LogType = 'normal'):
        return self.current().emit(note, type)

    def debug(self, note: str):
        return self.current().debug(note)

    def warn(self, note: str):
        return self.current().warn(note)

    def advice(self, note: str):
        return self.current().advice(note)

    def success(self, note: str):
        return self.current().success(note)

    def error(self, note: str):
        return self.current().error(note)

    def fatal(self, note: str):
        return self.current().fatal(note)
    
    def console(self):
        rendered = self.stringify(ansi=False)
        if rendered:
            print(rendered)
            
    def stringify(self, ansi: bool = False):
        lines = self.main.stringify(
            level=0,
            expose_nodes=self.expose_nodes,
            ansi=ansi,
            format_list=True
        )

        if lines:
            prefix = self.file_name.split('.')[0]
            header = lines[0]
            lines[0] = f"Stack {prefix} {header}"
            return '\n'.join(lines)
        return ''

    def write(self) -> None:
        """Persist the current stack snapshot to its configured log path."""
        if self.log:
            Log.write_to_path(self.stringify(ansi=False), self.log)
        else:
            Log.write(self.stringify(ansi=False), self.file_name)
    @classmethod
    def show_all(cls) -> None:
        """Write all stacks registered during the current process."""
        for stack in tuple(cls._stacks):
            stack.write()

    def clean(self):
        self.main.stack.clear()
        self._targets.clear()

    @classmethod
    def clear_all(cls) -> None:
        """Limpia los stacks registrados (útil para pruebas unitarias)."""
        
        cls._stacks.clear()

    @classmethod
    def clear_and_clean_all(cls):
        for stack in cls._stacks:
            stack.clean()
        cls._stacks.clear()

__all__ = ['StackInfo']
