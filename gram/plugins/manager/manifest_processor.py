"""
Procesador y Validador Semántico de Manifiestos para Plugins de Gram.
====================================================================
Inspecciona la integridad contextual de un PluginManifest contra el sistema de
archivos, asegurando la existencia de main.py, archivos de colores referenciados,
licencias independientes y dependencias declaradas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gram import errors
from gram.plugins.colors import PluginColors, parse_colors
from gram.plugins.manifest import PluginManifest, parse_manifest
from gram.utilities import error


@dataclass
class ManifestProcessResult:
    """Resultado estructurado del procesamiento contextual del manifiesto."""
    manifest: PluginManifest
    main_file_path: Path
    colors: PluginColors | None = None
    colors_file_path: Path | None = None
    license_file_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


class ManifestProcessor:
    """
    Validador de entorno y contexto físico para manifiestos de plugins.
    """

    @classmethod
    def process(
        cls,
        manifest_or_path: PluginManifest | Path | str,
        require_main: bool = True,
        load_colors: bool = True,
    ) -> ManifestProcessResult:
        """
        Procesa exhaustivamente un manifiesto y comprueba las referencias a archivos en disco.

        Args:
            manifest_or_path: Instancia de PluginManifest o ruta al archivo manifest.json.
            require_main: Si es True, verifica que 'main.py' exista junto a manifest.json.
            load_colors: Si es True y se especifica 'colors', parsea y valida dicho archivo.

        Returns:
            ManifestProcessResult con los recursos asociados resueltos.
        """
        if isinstance(manifest_or_path, PluginManifest):
            manifest = manifest_or_path
        else:
            manifest = parse_manifest(manifest_or_path)

        warnings: list[str] = []
        base_dir = manifest.manifest_path.parent if manifest.manifest_path else Path.cwd()

        # 1. Verificación de main.py
        main_path = base_dir / manifest.main
        if require_main and manifest.manifest_path:
            if not main_path.exists() or not main_path.is_file():
                error.GrammarError(
                    "Punto de entrada main.py no encontrado",
                    errors.PLUGIN_MAIN_NOT_FOUND,
                    f"El plugin '{manifest.plugin_name}' requiere un archivo '{manifest.main}' en: {main_path}",
                    "Todo plugin de Gram debe incluir 'main.py' como su punto de entrada principal.",
                ).raise_error()

        # 2. Verificación y carga de colores (si están definidos)
        colors_obj: PluginColors | None = None
        colors_path: Path | None = None
        if manifest.colors and manifest.manifest_path:
            candidate_path = base_dir / manifest.colors
            if candidate_path.exists() and candidate_path.is_file():
                colors_path = candidate_path
                if load_colors:
                    colors_obj = parse_colors(candidate_path)
            else:
                error.GrammarError(
                    "Archivo de colores referenciado no encontrado",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"El manifiesto especifica 'colors': '{manifest.colors}', pero el archivo no existe en: {candidate_path}",
                ).raise_error()

        # 3. Verificación de license_file (si está especificado)
        license_path: Path | None = None
        if manifest.license_file and manifest.manifest_path:
            candidate_lic = base_dir / manifest.license_file
            if candidate_lic.exists() and candidate_lic.is_file():
                license_path = candidate_lic
            else:
                warnings.append(
                    f"license_file '{manifest.license_file}' no encontrado en {candidate_lic}"
                )

        return ManifestProcessResult(
            manifest=manifest,
            main_file_path=main_path,
            colors=colors_obj,
            colors_file_path=colors_path,
            license_file_path=license_path,
            warnings=warnings,
        )


__all__ = [
    "ManifestProcessor",
    "ManifestProcessResult",
]
