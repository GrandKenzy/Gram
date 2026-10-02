"""
Módulo de Consultas Dinámicas para Autocompletado (`gram.core.combinators.query`).
=============================================================================
Define la clase `Query` (y su alias `query`) para dotar a las reglas sintácticas
`RuleItem` de capacidades de autocompletado e IntelliSense dinámico en tiempo real
(exploración de rutas en disco, directorios, archivos filtrados por extensión, etc.).

Arquitectura y Extensibilidad:
------------------------------
La infraestructura interna de este módulo está construida sobre controladores
desacoplados (`_handler`). En versiones futuras, este diseño permitirá registrar
funciones arbitrarias `query(function)` para consultar tablas de símbolos en memoria,
miembros de tipos/enums y árboles AST. En la versión actual, la creación directa
está controlada y se expone exclusivamente a través del método de fábrica oficial
`Query.query_roots(...)`.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Sequence


class Query:
    """
    EN:
        Dynamic query handler for contextual and runtime completions in RuleItem.
        Currently provides path resolution via `query_roots`. Designed for future
        extensibility with custom query providers.

    ES:
        Manejador de consultas dinámicas para autocompletado contextual en RuleItem.
        Actualmente provee resolución de rutas en disco mediante `query_roots`.
        Diseñado con arquitectura modular para futura extensibilidad con funciones
        arbitrarias de consulta.
    """

    def __init__(
        self,
        name: str = "custom",
        handler: Callable[..., list[dict[str, Any]]] | None = None,
        *,
        _internal: bool = False,
        **metadata: Any,
    ) -> None:
        """
        EN:
            Initialize a Query instance. Direct instantiation with custom functions
            is currently restricted to ensure stability. Use `Query.query_roots(...)`.

        ES:
            Inicializa una instancia de Query. La creación directa con funciones
            personalizadas está restringida temporalmente para asegurar la estabilidad.
            Utilice el constructor oficial `Query.query_roots(...)`.
        """
        if not _internal:
            raise NotImplementedError(
                "La creación directa de queries personalizadas está reservada para futuras "
                "versiones del framework. Por ahora utilice el método oficial `Query.query_roots(...)`."
            )
        self.name: str = name
        self._handler: Callable[..., list[dict[str, Any]]] | None = handler
        self.metadata: dict[str, Any] = metadata
        self.trigger_keywords: list[str] = list(metadata.get("trigger_keywords", []))

    @classmethod
    def query_roots(
        cls,
        path: str = "./",
        exts: Sequence[str] | Iterable[str] | None = None,
        folder: bool = True,
        current_token: bool = True,
        trigger_keywords: Sequence[str] | Iterable[str] | None = None,
        name: str = "query_roots",
    ) -> Query:
        """
        EN:
            Creates a filesystem path query for dynamic completions.

            Args:
                path: Root directory to inspect (e.g. './', '../libs', 'TIME/').
                exts: Allowed file extensions (e.g. ['.gst', '.h'] or ['gst', 'h']).
                      If empty or None, all files are displayed.
                folder: If True, subdirectories are included in completions.
                current_token: If True, uses the current token text under cursor to
                               navigate into subdirectories or filter candidates.
                trigger_keywords: Optional keywords that trigger this query.
                name: Query identifier.

            Returns:
                Configured Query instance.

        ES:
            Crea una consulta de rutas del sistema de archivos para autocompletado dinámico.

            Args:
                path: Directorio raíz a inspeccionar (ej. './', '../libs', 'TIME/').
                exts: Extensiones de archivo permitidas (ej. ['.gst', '.h'] o ['gst', 'h']).
                      Si está vacío o None, muestra todos los archivos.
                folder: Si es True, incluye subdirectorios en las sugerencias.
                current_token: Si es True, utiliza el token actual bajo el cursor para
                               navegar en subdirectorios o filtrar candidatos.
                trigger_keywords: Palabras clave opcionales que activan esta consulta.
                name: Identificador de la consulta.

            Returns:
                Instancia configurada de Query.
        """
        # Normalizar extensiones a formato minúsculo con punto prefijo (ej: ".gst")
        normalized_exts: set[str] = set()
        if exts:
            for ext in exts:
                cleaned = str(ext).strip().lower()
                if cleaned:
                    if not cleaned.startswith("."):
                        cleaned = f".{cleaned}"
                    normalized_exts.add(cleaned)

        raw_triggers = list(trigger_keywords) if trigger_keywords else []

        def _roots_handler(
            token_text: str | None = None,
            base_dir: Path | str | None = None,
        ) -> list[dict[str, Any]]:
            return cls._resolve_roots(
                root_path=path,
                exts=normalized_exts,
                folder=folder,
                use_current_token=current_token,
                token_text=token_text,
                base_dir=base_dir,
            )

        return cls(
            name=name,
            handler=_roots_handler,
            _internal=True,
            path=path,
            exts=list(normalized_exts),
            folder=folder,
            current_token=current_token,
            trigger_keywords=raw_triggers,
        )

    @classmethod
    def _resolve_roots(
        cls,
        root_path: str,
        exts: set[str],
        folder: bool,
        use_current_token: bool,
        token_text: str | None,
        base_dir: Path | str | None,
    ) -> list[dict[str, Any]]:
        """
        ES:
            Resuelve en disco las rutas correspondientes a la consulta actual,
            filtrando carpetas y extensiones y adaptándose a la navegación dinámica.
        """
        # 1. Determinar el directorio base efectivo (directorio del archivo editado o CWD)
        if base_dir:
            effective_base = Path(base_dir).resolve()
        else:
            effective_base = Path.cwd().resolve()

        # Si root_path es relativo, se ancla a effective_base
        target_root = (effective_base / root_path).resolve()
        if not target_root.exists() or not target_root.is_dir():
            return []

        # 2. Analizar subdirectorio y prefijo a partir del token actual
        sub_dir = ""
        prefix = ""

        if use_current_token and token_text:
            clean = token_text.strip("\"' \t\r\n").replace("\\", "/")
            if "/" in clean:
                parts = clean.split("/")
                sub_dir = "/".join(parts[:-1])
                prefix = parts[-1]
            else:
                prefix = clean

        # Directorio final a escanear
        scan_dir = (target_root / sub_dir).resolve()
        if not scan_dir.exists() or not scan_dir.is_dir():
            return []

        results: list[dict[str, Any]] = []
        prefix_lower = prefix.lower()

        try:
            with os.scandir(scan_dir) as it:
                for entry in it:
                    name = entry.name
                    # Filtrar por prefijo si se está escribiendo
                    if prefix_lower and not name.lower().startswith(prefix_lower):
                        continue

                    if entry.is_dir():
                        if folder:
                            results.append({
                                "label": f"{name}/",
                                "kind": 19,  # LSP CompletionItemKind.Folder
                                "detail": f"Directorio: {name}/",
                                "documentation": f"Ruta completa: `{entry.path}`",
                                "insertText": f"{name}/",
                            })
                    elif entry.is_file():
                        ext = os.path.splitext(name)[1].lower()
                        if exts and ext not in exts:
                            continue
                        results.append({
                            "label": name,
                            "kind": 17,  # LSP CompletionItemKind.File
                            "detail": f"Archivo {ext or 'binario'}",
                            "documentation": f"Ruta completa: `{entry.path}`",
                            "insertText": name,
                        })
        except Exception:
            return []

        # Ordenar: primero carpetas alfabéticamente, luego archivos
        results.sort(key=lambda x: (0 if x["kind"] == 19 else 1, x["label"].lower()))
        return results

    def execute(
        self,
        token_text: str | None = None,
        base_dir: Path | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        EN: Executes the query and returns formatted completion item dictionaries.
        ES: Ejecuta la consulta y retorna la lista de sugerencias formateadas para LSP.
        """
        if self._handler is not None:
            return self._handler(token_text=token_text, base_dir=base_dir)
        return []

    def __repr__(self) -> str:
        path_info = self.metadata.get("path", "./")
        return f"<Query name={self.name!r} path={path_info!r}>"


# Alias en minúsculas para permitir sintaxis fluida: `query.query_roots(...)`
query = Query

__all__ = [
    "Query",
    "query",
]
