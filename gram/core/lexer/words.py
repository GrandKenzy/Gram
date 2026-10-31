"""
Unified Keyword and WordGroup Management (`gram.core.lexer.words`).
===================================================================
Manages language keywords (`Keyword`) and semantic keyword groups (`WordGroup`),
providing dynamic registration, visual metadata, collision detection, and $O(1)$
membership lookups.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from gram import config, errors
from gram.utilities import Format

MAP_KEYWORDS: dict[str, Keyword] = {}
_GLOBAL_GROUPS: dict[str, WordGroup] = {}
_SESSION_TARGET: Any | None = None


def bind_session(session: Any) -> None:
    """Route the loose lexicon API to ``session`` until it is unbound."""
    global _SESSION_TARGET
    _SESSION_TARGET = session


def unbind_session(session: Any | None = None) -> None:
    """Stop routing loose lexicon calls to ``session``."""
    global _SESSION_TARGET
    if session is None or _SESSION_TARGET is session:
        _SESSION_TARGET = None


def active_session() -> Any | None:
    """Return the session currently owning the loose lexicon API, if any."""
    return _SESSION_TARGET


def _catalogs() -> tuple[dict[str, Keyword], dict[str, WordGroup]]:
    """Return the active keyword and group dictionaries."""
    if _SESSION_TARGET is not None:
        return _SESSION_TARGET.keywords, _SESSION_TARGET.groups
    return MAP_KEYWORDS, _GLOBAL_GROUPS


def _log_lexer_note(message: str, note_type: Format.LogType = "normal") -> None:
    """Emit a diagnostic note to the active lexer stack if `LEXER_ADD_INFO` is enabled."""
    enabled = (
        _SESSION_TARGET.config.get("LEXER_ADD_INFO", True)
        if _SESSION_TARGET is not None
        else getattr(config, "LEXER_ADD_INFO", True)
    )
    if not enabled:
        return
    from gram.core.lexer.control import LexerState

    LexerState.get_stack().note(message, note_type)


# ==============================================================================
# 1. KEYWORD CLASS
# ==============================================================================

class Keyword:
    """
    Represents a registered language keyword and its associated IDE/lexer metadata.

    Attributes:
        name (str): Exact lexeme string of the keyword (e.g., `'def'`, `'if'`).
        hex_color (str): Suggested hex color for syntax highlighting.
        group (str | None): Name of the logical `WordGroup` to which it belongs.
        description (str): Short description of the keyword.
        documentation (str): Extended documentation for hover/completion.
    """

    __slots__ = ("description", "documentation", "group", "hex_color", "name")

    def __init__(
        self,
        name: str,
        hex_color: str = "#FFFFFF",
        group: str | WordGroup | None = None,
        description: str = "",
        documentation: str = "",
        *,
        color: str | None = None,
    ) -> None:
        if color is not None:
            hex_color = color
        if not name or not name.strip():
            errors.LexerError(
                "KeywordInvalidName",
                errors.LEXER_KEYWORD_INVALID_NAME,
                "El nombre de la palabra clave no puede estar vacío.",
                "Proporcione un identificador válido sin espacios en blanco.",
            ).raise_error()

        self.name: str = name.strip()
        self.hex_color: str = hex_color
        group_name = group.name if isinstance(group, WordGroup) else group
        self.group: str | None = group_name
        self.description: str = description
        self.documentation: str = documentation
        # Registration is deliberately performed by ``add_keyword``. Keeping
        # this constructor side-effect free makes a Keyword safe to use as a
        # value object inside an isolated Session.

    @property
    def color(self) -> str:
        """Return hex color of keyword."""
        return self.hex_color

    @classmethod
    def count(cls) -> int:
        """Return the total number of registered keywords in `MAP_KEYWORDS`."""
        return len(_catalogs()[0])

    def __repr__(self) -> str:
        return f"Keyword({self.name!r}, color={self.hex_color!r}, group={self.group!r})"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Keyword):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return False

    def __hash__(self) -> int:
        return hash(self.name)


# ==============================================================================
# 2. WORDGROUP CLASS & MANAGER
# ==============================================================================

class WordGroup:
    """
    Represents a logical or semantic group of registered `Keyword` instances
    (e.g., `'$TYPES'`, `'$CONTROL'`).
    """

    __slots__ = ("_keywords", "color_group", "description", "name")

    def __init__(
        self,
        name: str,
        color_group: str = "#FFA500",
        description: str = "",
    ) -> None:
        self.name: str = name
        self.color_group: str = color_group
        self.description: str = description
        self._keywords: dict[str, Keyword] = {}

    @property
    def values(self) -> list[str]:
        """Return a list of all keyword names in this group."""
        return list(self._keywords.keys())

    @property
    def keywords_list(self) -> list[Keyword]:
        """Return a list of all `Keyword` instances in this group."""
        return list(self._keywords.values())

    def contains(self, keyword_name: str) -> bool:
        """Return whether the exact keyword spelling belongs to this group.

        The comparison is case-sensitive and uses the group's hash index, so
        membership is O(1) average-case.
        """
        return keyword_name in self._keywords

    def add_keyword(self, item: str | Keyword) -> Keyword | None:
        """Bind a keyword to this group in the active catalog.

        This mutator remains as a compatibility shim. New code should use
        :func:`add_keyword`, which is the canonical registration API.
        """
        keywords, _ = _catalogs()
        if isinstance(item, Keyword):
            name = item.name
            kw: Keyword | None = item
            if name not in keywords:
                keywords[name] = item
        else:
            name = str(item)
            kw = keywords.get(name)

        if kw is None:
            _log_lexer_note(
                f'Intento de agregar palabra no registrada "{name}" al grupo "{self.name}"',
                "error",
            )
            errors.LexerError(
                f"WordGroupKeywordNotRegistered: {name!r}",
                errors.LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED,
                f'La palabra clave "{name}" debe registrarse previamente en el lexer '
                f'antes de asociarla al grupo "{self.name}".',
            ).raise_error()
            return None

        if kw.group is None or kw.group == self.name:
            kw.group = self.name
            self._keywords[name] = kw
            return kw
        return None

    def remove_keyword(self, name: str) -> Keyword | None:
        """Remove a keyword by name from this group."""
        kw = self._keywords.pop(name, None)
        if kw is not None and kw.group == self.name:
            kw.group = None
        return kw

    def count(self) -> int:
        """Return the number of keywords in this group."""
        return len(self._keywords)

    def clear(self) -> None:
        """Remove all keywords and clear their stale group references.

        Complexity: O(K), where K is the number of keywords in this group.
        """
        for keyword in self._keywords.values():
            if keyword.group == self.name:
                keyword.group = None
        self._keywords.clear()

    def __repr__(self) -> str:
        return (
            f"WordGroup({self.name!r}, keywords={self.values}, "
            f"color={self.color_group!r})"
        )

    def __contains__(self, item: str | Keyword) -> bool:
        name = item.name if isinstance(item, Keyword) else str(item)
        return self.contains(name)


class WordGroupManager:
    """Centralized registry and lifecycle manager for lexical `WordGroup` instances."""

    def __init__(self) -> None:
        raise RuntimeError(
            "WordGroupManager is obsolete; use Session.add_group() or words.add_group()."
        )


# ==============================================================================
# 3. GLOBAL CATALOG FUNCTIONS
# ==============================================================================

class _LegacyGroupsView:
    """Compatibility view over the active Session group catalog."""

    @property
    def _groups(self) -> dict[str, WordGroup]:
        return _catalogs()[1]

    def create(
        self,
        name: str | WordGroup,
        values: Iterable[str | Keyword] | None = None,
        color_group: str = "#FFA500",
        description: str = "",
        *,
        allow_override: bool = False,
    ) -> WordGroup:
        return add_group(
            name,
            values,
            color_group,
            description,
            allow_override=allow_override,
        )

    def get(self, name: str | WordGroup, *, strict: bool = False) -> WordGroup | None:
        return get_group(name, strict=strict)

    def exists(self, name: str | WordGroup) -> bool:
        return group_exists(name)

    def remove(self, name: str | WordGroup) -> WordGroup | None:
        return remove_group(name)

    def all(self) -> dict[str, WordGroup]:
        return all_groups()

    def all_names(self) -> list[str]:
        return all_group_names()

    def clear(self) -> None:
        _catalogs()[1].clear()


groups = _LegacyGroupsView()


def add_keyword(
    name: str,
    hex_color: str = "#FFFFFF",
    group: str | WordGroup | None = None,
    description: str = "",
    documentation: str = "",
    *,
    color: str | None = None,
    allow_override: bool = False,
) -> Keyword:
    """Register a keyword in the active lexer catalog."""
    keywords, groups_catalog = _catalogs()
    if color is not None:
        hex_color = color
    if not name or not name.strip():
        errors.LexerError(
            "KeywordInvalidName",
            errors.LEXER_KEYWORD_INVALID_NAME,
            "El nombre de la palabra clave no puede estar vacío.",
        ).raise_error()

    clean_name = name.strip()
    if clean_name in keywords and not allow_override:
        errors.LexerError(
            "KeywordAlreadyExists",
            errors.LEXER_KEYWORD_ALREADY_EXISTS,
            f"La palabra clave {clean_name!r} ya está registrada.",
            "Use allow_override=True para reemplazarla o elija un nombre diferente.",
        ).raise_error()

    keyword = Keyword(
        name=clean_name,
        hex_color=hex_color,
        description=description,
        documentation=documentation,
    )
    keywords[clean_name] = keyword

    if group is not None:
        group_name = group.name if isinstance(group, WordGroup) else str(group)
        target_group = groups_catalog.get(group_name)
        if target_group is None:
            _log_lexer_note(
                f"El grupo {group_name!r} no existe aún al registrar la palabra clave "
                f"{clean_name!r}. Créelo usando words.add_group.",
                "warn",
            )
        else:
            target_group.add_keyword(keyword)
    return keyword


def get_keyword(name: str, *, strict: bool = False) -> Keyword | None:
    """Retrieve a registered `Keyword` by exact name."""
    kw = _catalogs()[0].get(name)
    if kw is None and strict:
        errors.LexerError(
            "KeywordNotFound",
            errors.LEXER_KEYWORD_NOT_FOUND,
            f"La palabra clave {name!r} no está registrada.",
            "Verifique que la palabra clave haya sido registrada antes de consultarla con strict=True.",
        ).raise_error()
    return kw


def keyword_exists(name: str) -> bool:
    """Return True if `name` is registered in the active catalog."""
    return name in _catalogs()[0]


def remove_keyword(name: str, *, strict: bool = False) -> Keyword | None:
    """Remove a keyword from the active catalog and associated groups."""
    keywords, groups_catalog = _catalogs()
    kw = keywords.pop(name, None)
    if kw is None:
        if strict:
            errors.LexerError(
                "KeywordNotFound",
                errors.LEXER_KEYWORD_NOT_FOUND,
                f"La palabra clave {name!r} no está registrada.",
            ).raise_error()
        return None

    for grp in groups_catalog.values():
        grp.remove_keyword(name)

    return kw


def all_keywords() -> list[Keyword]:
    """Return a list of all registered `Keyword` instances."""
    return list(_catalogs()[0].values())


def all_keyword_names() -> list[str]:
    """Return a list of all registered keyword names."""
    return list(_catalogs()[0].keys())


def is_empty() -> bool:
    """Return True if no keywords are registered in the active catalog."""
    return not _catalogs()[0]


def count_keywords() -> int:
    """Return the number of registered keywords."""
    return len(_catalogs()[0])


def add_group(
    name: str | WordGroup,
    values: Iterable[str | Keyword] | None = None,
    color_group: str = "#FFA500",
    description: str = "",
    *,
    allow_override: bool = False,
) -> WordGroup:
    """Create and register a new `WordGroup`."""
    _, groups_catalog = _catalogs()
    group_name = name.name if isinstance(name, WordGroup) else str(name)
    if group_name in groups_catalog and not allow_override:
        _log_lexer_note(f"El grupo {group_name!r} ya está registrado", "error")
        errors.LexerError(
            "GroupAlreadyExists",
            errors.LEXER_WORDGROUP_ALREADY_EXISTS,
            f'El grupo de palabras clave "{group_name}" ya fue creado. '
            "Use allow_override=True para sobrescribirlo.",
        ).raise_error()

    group = name if isinstance(name, WordGroup) else WordGroup(
        name=group_name,
        color_group=color_group,
        description=description,
    )
    groups_catalog[group_name] = group
    if values is not None:
        for value in values:
            group.add_keyword(value)
    _log_lexer_note(f"Grupo de palabras creado: {group_name!r}", "success")
    return group


def get_group(name: str | WordGroup, *, strict: bool = False) -> WordGroup | None:
    """Retrieve a `WordGroup` by name or instance."""
    group_name = name.name if isinstance(name, WordGroup) else str(name)
    group = _catalogs()[1].get(group_name)
    if group is None and strict:
        _log_lexer_note(f"Grupo no encontrado: {group_name!r}", "error")
        errors.LexerError(
            "GroupNotFound",
            errors.LEXER_WORDGROUP_NOT_FOUND,
            f'El grupo de palabras clave "{group_name}" no está registrado.',
        ).raise_error()
    return group


def group_exists(name: str | WordGroup) -> bool:
    """Return True if the specified group exists."""
    group_name = name.name if isinstance(name, WordGroup) else str(name)
    return group_name in _catalogs()[1]


def remove_group(name: str | WordGroup) -> WordGroup | None:
    """Remove a registered `WordGroup` and clear its group reference on member keywords."""
    group_name = name.name if isinstance(name, WordGroup) else str(name)
    grp = _catalogs()[1].pop(group_name, None)
    if grp is not None:
        for kw in grp.keywords_list:
            if kw.group == grp.name:
                kw.group = None
    return grp


def all_groups() -> dict[str, WordGroup]:
    """Return all registered `WordGroup` instances."""
    return dict(_catalogs()[1])


def all_group_names() -> list[str]:
    """Return all registered group names."""
    return list(_catalogs()[1].keys())


def exists_in_group(keyword_name: str | Keyword, group_name: str | WordGroup) -> bool:
    """Return True if `keyword_name` belongs to `group_name`."""
    grp = get_group(group_name)
    if grp is None:
        return False
    kw_str = keyword_name.name if isinstance(keyword_name, Keyword) else str(keyword_name)
    return grp.contains(kw_str)


def clear_all() -> None:
    """Reset and clear all registered keywords and word groups."""
    keywords, groups_catalog = _catalogs()
    keywords.clear()
    groups_catalog.clear()


__all__ = [
    "Keyword",
    "WordGroup",
    "WordGroupManager",
    "add_group",
    "add_keyword",
    "all_group_names",
    "all_groups",
    "all_keyword_names",
    "all_keywords",
    "clear_all",
    "count_keywords",
    "exists_in_group",
    "get_group",
    "get_keyword",
    "group_exists",
    "groups",
    "is_empty",
    "keyword_exists",
    "remove_group",
    "remove_keyword",
]
