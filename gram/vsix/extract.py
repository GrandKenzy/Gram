"""
Módulo de Extracción de Metadatos Sintácticos para VS Code / VSIX (`gram.vsix.extract`).
========================================================================================
Inspecciona el catálogo en memoria del lexer, las reglas declarativas nativas,
los grupos léxicos y los plugins registrados para construir una representación unificada
de las palabras clave, reglas, tokens, sugerencias de autocompletado y paletas cromáticas.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gram.core.lexer.tokens import Token
from gram.core.lexer.words import MAP_KEYWORDS, groups
from gram.plugins.colors import ColorDefinition, PluginColors
from gram.plugins.registry import all_plugins


@dataclass
class KeywordMetadata:
    """Metadatos de una palabra clave de Gram para el editor y LSP."""
    name: str
    hex_color: str = "#FFFFFF"
    group: str | None = None
    description: str = ""
    source_plugin: str = "native"


@dataclass
class RuleMetadata:
    """Metadatos de una regla de producción sintáctica de Gram."""
    name: str
    code: int = 0
    description: str = ""
    docs: str = ""
    colors: dict[int, str] = field(default_factory=dict)
    color: str = "#FFFFFF"
    scope: str = ""
    is_structural: bool = False
    suggestions: dict[int, Any] = field(default_factory=dict)
    suggestions_autocomplete: bool = True
    queries: list[Any] = field(default_factory=list)
    hints: dict[int, Any] = field(default_factory=dict)
    source_plugin: str = "native"


@dataclass
class SyntaxMetadata:
    """
    Colección unificada de metadatos sintácticos, de autocompletado y cromáticos
    destinada a la generación de herramientas de edición (TextMate, VSIX, temas, LSP).
    """
    keywords: dict[str, KeywordMetadata] = field(default_factory=dict)
    rules: dict[str, RuleMetadata] = field(default_factory=dict)
    colors: dict[str, ColorDefinition] = field(default_factory=dict)
    word_groups: dict[str, list[str]] = field(default_factory=dict)
    token_types: list[str] = field(default_factory=list)
    file_extensions: list[str] = field(default_factory=lambda: [".gram", ".glang", ".g"])
    compiler_path: str = ""
    compiler_args: list[str] = field(default_factory=list)

    def get_keywords_by_group(self, group: str) -> list[str]:
        """Retorna las keywords pertenecientes a un grupo específico."""
        return [k.name for k in self.keywords.values() if k.group == group]

    def get_keywords_by_plugin(self, plugin_name: str) -> list[str]:
        """Retorna las keywords registradas por un plugin específico."""
        return [k.name for k in self.keywords.values() if k.source_plugin == plugin_name]

    def get_all_suggestions(self) -> list[dict[str, str]]:
        """
        Retorna una lista consolidada de sugerencias de autocompletado para el LSP.
        Incluye palabras clave registradas y sugerencias definidas en reglas.
        """
        items: list[dict[str, str]] = []

        # 1. Sugerencias de palabras clave
        for kw_name, kw_meta in self.keywords.items():
            items.append({
                "label": kw_name,
                "kind": "Keyword",
                "detail": f"Palabra clave ({kw_meta.group or 'Gram'})",
                "documentation": kw_meta.description or f"Palabra clave reservada '{kw_name}'.",
                "insertText": kw_name,
            })

        # 2. Sugerencias de reglas sintácticas
        for r_name, r_meta in self.rules.items():
            items.append({
                "label": r_name,
                "kind": "Class",
                "detail": f"Regla Gram (código {r_meta.code})",
                "documentation": r_meta.description or r_meta.docs or f"Regla sintáctica '{r_name}'.",
                "insertText": r_name,
            })

            # Sugerencias internas de la regla
            if r_meta.suggestions and isinstance(r_meta.suggestions, dict):
                for pos, sug_list in r_meta.suggestions.items():
                    resolved = sug_list() if callable(sug_list) else sug_list
                    if isinstance(resolved, list):
                        for item in resolved:
                            if isinstance(item, tuple) and len(item) >= 2:
                                s_lbl, s_doc = str(item[0]), str(item[1])
                                items.append({
                                    "label": s_lbl,
                                    "kind": "Snippet",
                                    "detail": f"Sugerencia para {r_name}",
                                    "documentation": s_doc,
                                    "insertText": s_lbl,
                                })
                            elif isinstance(item, str):
                                items.append({
                                    "label": item,
                                    "kind": "Snippet",
                                    "detail": f"Sugerencia para {r_name}",
                                    "documentation": "",
                                    "insertText": item,
                                })

        return items

    def merge(self, other: SyntaxMetadata) -> SyntaxMetadata:
        """Fusiona otros metadatos sintácticos en la instancia actual."""
        self.keywords.update(other.keywords)
        self.rules.update(other.rules)
        self.colors.update(other.colors)
        for g_name, kws in other.word_groups.items():
            existing = self.word_groups.setdefault(g_name, [])
            for kw in kws:
                if kw not in existing:
                    existing.append(kw)
        for tok in other.token_types:
            if tok not in self.token_types:
                self.token_types.append(tok)
        for ext in other.file_extensions:
            if ext not in self.file_extensions:
                self.file_extensions.append(ext)
        if other.compiler_path:
            self.compiler_path = other.compiler_path
        if other.compiler_args:
            self.compiler_args = list(other.compiler_args)
        return self

    def copy(self) -> SyntaxMetadata:
        """Crea una copia superficial de la estructura de metadatos."""
        clone = SyntaxMetadata(
            keywords=dict(self.keywords),
            rules=dict(self.rules),
            colors=dict(self.colors),
            word_groups={k: list(v) for k, v in self.word_groups.items()},
            token_types=list(self.token_types),
            file_extensions=list(self.file_extensions),
            compiler_path=self.compiler_path,
            compiler_args=list(self.compiler_args),
        )
        return clone


def extract_metadata(
    plugins: list[Any] | None = None,
    include_native: bool = True,
) -> SyntaxMetadata:
    """
    Extrae exhaustivamente todos los metadatos léxicos, sintácticos, de autocompletado
    y de color del núcleo de Gram y de los plugins especificados (o registrados).
    """
    metadata = SyntaxMetadata()

    # 1. Tokens léxicos fundamentales
    if include_native:
        for tok in Token:
            if tok.name not in metadata.token_types:
                metadata.token_types.append(tok.name)

    # 2. Grupos de palabras clave y mapeo de colores
    group_color_map: dict[str, str] = {}
    try:
        for g_name, grp in groups.all().items():
            kw_names = [k.name for k in getattr(grp, "keywords_list", [])]
            metadata.word_groups[g_name] = kw_names
            g_color = getattr(grp, "color_group", "#FFFFFF") or "#FFFFFF"
            if g_color and g_color.upper() != "#FFFFFF":
                group_color_map[g_name] = g_color
    except Exception:
        pass

    # 3. Palabras clave del Lexer (con resolución de herencia de color de grupo)
    for name, kw in MAP_KEYWORDS.items():
        src = getattr(kw, "_source_plugin", "native")
        if not include_native and src == "native":
            continue
        kw_color = kw.hex_color or "#FFFFFF"
        if (not kw_color or kw_color.upper() == "#FFFFFF") and kw.group and kw.group in group_color_map:
            kw_color = group_color_map[kw.group]

        metadata.keywords[name] = KeywordMetadata(
            name=name,
            hex_color=kw_color,
            group=kw.group,
            description=kw.description or "",
            source_plugin=src,
        )

    # 4. Reglas nativas (gram.native.rules) usando RuleItem.compile()
    if include_native:
        try:
            from gram.core.combinators.base import RuleItem
            import gram.native.rules as native_rules

            for attr_name in dir(native_rules):
                attr = getattr(native_rules, attr_name)
                if inspect.isclass(attr) and issubclass(attr, RuleItem) and attr is not RuleItem:
                    if hasattr(attr, "compile") and callable(attr.compile):
                        compiled = attr.compile()
                        metadata.rules[compiled["name"]] = RuleMetadata(
                            name=compiled["name"],
                            code=compiled["code"],
                            description=compiled["description"],
                            docs=compiled["docs"],
                            colors=compiled["colors"],
                            color=compiled["color"],
                            scope=compiled["scope"],
                            is_structural=compiled["is_structural"],
                            suggestions=compiled["suggestions"],
                            suggestions_autocomplete=compiled.get("suggestions_autocomplete", True),
                            queries=compiled.get("queries", []),
                            hints=compiled.get("hints", {}),
                            source_plugin="native",
                        )
                    else:
                        r_name = getattr(attr, "name", attr.__name__)
                        metadata.rules[r_name] = RuleMetadata(
                            name=r_name,
                            code=getattr(attr, "code", 0),
                            description=getattr(attr, "description", ""),
                            colors=dict(getattr(attr, "colors", {}) or {}),
                            is_structural=getattr(attr, "is_structural", False),
                            queries=list(getattr(attr, "queries", []) or []),
                            hints=dict(getattr(attr, "hints", {}) or {}),
                            source_plugin="native",
                        )
        except Exception:
            pass

    # 5. Paletas de colores y reglas de plugins
    active_plugins = plugins if plugins is not None else all_plugins()
    for p in active_plugins:
        p_name = getattr(p, "name", str(p))
        p_colors = getattr(p, "colors", None)
        if isinstance(p_colors, PluginColors):
            for c_name, c_def in p_colors._colors.items():
                metadata.colors[c_name] = c_def
        elif isinstance(p_colors, dict):
            for c_name, c_def in p_colors.items():
                if isinstance(c_def, ColorDefinition):
                    metadata.colors[c_name] = c_def

        if hasattr(p, "get_grammar"):
            try:
                from gram.core.combinators.base import RuleItem
                p_grammar = p.get_grammar()
                if isinstance(p_grammar, dict):
                    for r_item in p_grammar.keys():
                        if inspect.isclass(r_item) and issubclass(r_item, RuleItem):
                            compiled = r_item.compile()
                            metadata.rules[compiled["name"]] = RuleMetadata(
                                name=compiled["name"],
                                code=compiled["code"],
                                description=compiled["description"],
                                docs=compiled["docs"],
                                colors=compiled["colors"],
                                color=compiled["color"],
                                scope=compiled["scope"],
                                is_structural=compiled["is_structural"],
                                suggestions=compiled["suggestions"],
                                suggestions_autocomplete=compiled.get("suggestions_autocomplete", True),
                                queries=compiled.get("queries", []),
                                hints=compiled.get("hints", {}),
                                source_plugin=p_name,
                            )
            except Exception:
                pass

    return metadata


__all__ = [
    "KeywordMetadata",
    "RuleMetadata",
    "SyntaxMetadata",
    "extract_metadata",
]
