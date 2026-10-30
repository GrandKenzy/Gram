from __future__ import annotations

from .. import Format
from .log import Log
from .note import Note


class Node:
    __slots__ = ('name', 'description', 'priority', 'stack')

    def __init__(
        self,
        name: str,
        description: str,
        priority: int = 0
    ):
        self.name = name
        self.description = description
        self.priority = priority
        self.stack: list[Note | Node] = []
        
    def note(self, description: str, type: Format.LogType = 'normal') -> Note:
        n = Note(description, type.lower())
        self.stack.append(n)
        return n

    def emit(self, description: str, type: Format.LogType = 'normal') -> Note:
        """Append one typed note without making callers know stack internals."""
        return self.note(description, type)

    def debug(self, description: str) -> Note:
        return self.emit(description, 'normal')

    def warn(self, description: str) -> Note:
        return self.emit(description, 'warn')

    def advice(self, description: str) -> Note:
        return self.emit(description, 'advice')

    def success(self, description: str) -> Note:
        return self.emit(description, 'success')

    def error(self, description: str) -> Note:
        return self.emit(description, 'error')

    def fatal(self, description: str) -> Note:
        return self.emit(description, 'fatal')
    
    def node(self, name: str, description: str, priority: int = 0):
        sub = Node(name, description, priority)
        self.stack.append(sub)
        return sub

    @property
    def notes(self) -> list[Note]:
        """Devuelve todas las notas contenidas directamente en este nodo."""
        return [item for item in self.stack if isinstance(item, Note)]

    @property
    def nodes(self) -> list[Node]:
        """Devuelve todos los subnodos contenidos directamente en este nodo."""
        return [item for item in self.stack if isinstance(item, Node)]

    def stringify(self, level: int = 0, expose_nodes: bool = False, ansi: bool = False, format_list: bool = False):
        prefix = Format.left if level == 0 else f'{Format.left}{Format.line * 4}'
        
        indent = prefix + ((Format.line * 4) * level)
        content: list[str] = [f'{indent}<Node {self.name} L={level}>:']
        
        items: list[Note | Node]
        if self.stack:
            items = self.stack
        else:
            items = [Note('Empty Node', 'normal')]

        for item in items:
            if isinstance(item, Note):
                if item.type in Format.ONLY_SHOW_TYPES:
                    content.append(f'| {item.stringify(level + 1, ansi)}')
            else:
                if item.priority <= Format.MAX_PRIORITY:
                    if expose_nodes:
                        child_result = item.stringify(
                            level + 1,
                            expose_nodes=expose_nodes,
                            ansi=ansi,
                            format_list=True
                        )
                        
                        content.extend(child_result)
                else:
                    content.append(f'{indent}<Node {item.name} low-priority>')
        
        if format_list:
            return content
        return '\n'.join(content)        

    def count_notes(self) -> int:
            """Retorna el número de notas directas en este nodo."""
            return sum(1 for item in self.stack if isinstance(item, Note))

    def count_nodes(self) -> int:
        """Retorna el número de subnodos directos en este nodo."""
        return sum(1 for item in self.stack if isinstance(item, Node))

    def __repr__(self) -> str:
        return f"Node({self.name!r}, priority={self.priority}, items={len(self.stack)})"


__all__ = [
    'Log',
    'StackInfo',
    'Node',
    'Note',
]

from .stack import StackInfo
