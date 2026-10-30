from __future__ import annotations
from pathlib import Path
from typing import ClassVar

class Log:
    _files: ClassVar[dict[str, Path]] = {}
    LOGFILE: ClassVar[Path] = Path('log').resolve()

    @classmethod
    def _clean_name(cls, name: str) -> str:
        clean_name = Path(name).name
        return clean_name if clean_name.endswith('.log') else f'{clean_name}.log'

    @classmethod
    def _target(cls, name: str, folder_name: str = '') -> Path:
        root = cls.LOGFILE.resolve()
        clean_name = cls._clean_name(name)
        clean_folder = Path(folder_name).name if folder_name else ''
        target = (root / clean_folder / clean_name).resolve()
        if not target.is_relative_to(root):
            raise PermissionError(
                f'Seguridad: Intento de escape de directorio detectado hacia {target}'
            )
        return target
    
    @classmethod
    def register(cls, name: str, folder_name: str = "") -> Path:
        target_path = cls._target(name, folder_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text('', encoding='utf-8')
        cls._files[cls._clean_name(name)] = target_path
        return target_path

    @classmethod
    def write(cls, content: str, file_name: str):
        key = cls._clean_name(file_name)
        path = cls._files.get(key)
        if path is None:
            path = cls._target(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            cls._files[key] = path

        path.write_text(content, encoding='utf-8')
       
    @classmethod
    def write_to_path(cls, content: str, path: Path, *, append: bool = False):
        """Write to a caller-supplied path, replacing content unless append is explicit."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with path.open('a', encoding='utf-8') as file:
                if content:
                    file.write(content + '\n')
        else:
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


__all__ = ['Log']
