from __future__ import annotations
from pathlib import Path
from typing import ClassVar

class Log():
    _files: ClassVar[dict[str, Path]] = {}
    LOGFILE: ClassVar[Path] = Path('log')
    
    @classmethod
    def register(cls, name: str):
        if not name.endswith('.log'):
            name += '.log'
        
        path = cls.LOGFILE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        cls._files[name] = path
        
        return path
    
    @classmethod
    def write(cls, content: str, file_name: str):
        if not file_name.endswith('.log'):
            file_name += '.log'
        
        path = cls._files.get(file_name)
        if path is None:
            path = cls.LOGFILE / file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            cls._files[file_name] = path

        path.write_text(content, encoding='utf-8')
        
    @classmethod
    def path_for(cls, key: str) -> Path | None:
        """Devuelve la ruta del log registrado para una clave dada o None."""
        if not key.endswith('.log'):
            key += '.log'
        return cls._files.get(key)

    @classmethod
    def registered_files(cls) -> list[str]:
        """Retorna la lista de nombres de archivos de log actualmente registrados."""
        return list(cls._files.keys())

    @classmethod
    def clear(cls) -> None:
        """Limpia el registro de archivos en memoria (útil en pruebas)."""
        cls._files.clear()
        cls._ansi_notice_shown = False


__all__ = ['Log']
