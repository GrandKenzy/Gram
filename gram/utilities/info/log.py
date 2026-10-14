from __future__ import annotations
from pathlib import Path
from typing import ClassVar
import shutil

class Log:
    _files: ClassVar[dict[str, Path]] = {}
    LOGFILE: ClassVar[Path] = Path('log').resolve()
    _deleted: bool = False
    
    @classmethod
    def register(cls, name: str, folder_name: str = "") -> Path:
        if not cls._deleted:
            if cls.LOGFILE.exists():
                for e in cls.LOGFILE.iterdir():
                    if e.is_dir() and not e.is_symlink():
                        shutil.rmtree(e)
                    else:
                        e.unlink()
            cls._deleted = True

        clean_name = Path(name).name 
        if not clean_name.endswith('.log'):
            clean_name += '.log'
            
        clean_folder = folder_name.strip('/\\') if folder_name else ""
        target_path = (cls.LOGFILE / clean_folder / clean_name).resolve()
        
        if not target_path.is_relative_to(cls.LOGFILE):
            raise PermissionError(f"Seguridad: Intento de escape de directorio detectado hacia {target_path}")
            
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if target_path.exists():
            target_path.unlink()
            
        target_path.write_text('', encoding='utf-8')
        cls._files[name] = target_path
        
        return target_path
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
    def write_to_path(cls, content: str, path: Path):
        """Escribe directamente en una ruta Path ya validada."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            if content:
                f.write(content + '\n')
 
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
