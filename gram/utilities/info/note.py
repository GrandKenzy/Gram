from __future__ import annotations
from gram.utilities import Format



class Note:
    def __init__(
        self,
        note: str,
        type: Format.LogType = 'normal'
    ):
        self.note = note
        self.type = type
        
    @property
    def description(self):
        return self.note
    
    def stringify(self, level: int = 0, ansi: bool = False):
        indent = '    ' * level
        if ansi:
            color = Format.LogTypeColor(self.type)
            return f'{indent}{color}{Format.LogTypeIcon(self.type)}{self.note}{Format.ARESET}'
        return f'{indent}{Format.LogTypeIcon(self.type)}{self.note}'
    

    def __repr__(self) -> str:
        return f"Note({self.note!r}, type={self.type!r})"

    def __str__(self) -> str:
        return self.note


__all__ = ['Note']
