"""
Gestión Unificada de Palabras Clave y Grupos Léxicos (`gram.core.lexer.words`).
=============================================================================
Consolida la administración de palabras clave (Keywords) y grupos lógicos de
palabras (WordGroups), proporcionando registro dinámico, metadatos visuales,
detección de colisiones, discriminación de identificadores y aislamiento de estado.
"""
from __future__ import annotations

import sys
from typing import Any

from gram import config, errors
from gram.utilities import error


def _log_lexer_note(message: str, note_type: str = 'normal') -> None:
    """Emite una nota de telemetría al stack léxico si está disponible."""
    try:
        mod = sys.modules.get('gram.core.lexer.stack')
        if mod is not None and hasattr(mod, 'stack') and mod.stack is not None:
            mod.stack.note(message, note_type.lower())
    except Exception:
        pass


# ==============================================================================
# 1. CLASE KEYWORD Y CATÁLOGO GLOBAL
# ==============================================================================

class Keyword:
    """
    ES:
        Representa una palabra clave registrada en el lenguaje con metadatos asociados.

        Atributos:
            name (str): Identificador textual exacto de la palabra clave (ej. 'def', 'if').
            hex_color (str): Color hexadecimal sugerido para resaltado de sintaxis.
            group (str | None): Nombre del grupo lógico al que pertenece.
            description (str): Documentación contextual de la palabra clave.

    EN:
        Represents a registered keyword in the language with associated metadata.
    """

    def __init__(
        self,
        name: str,
        hex_color: str = '#FFFFFF',
        group: str | WordGroup | None = None,
        description: str = '',
    ) -> None:
        if not name or not name.strip():
            error.LexerError(
                'El nombre de la palabra clave no puede estar vacío.',
                errors.KEYWORD_INVALID_NAME,
                'Proporcione un identificador no vacío y sin espacios en blanco.',
            ).raise_error()

        self.name: str = name.strip()
        self.hex_color: str = hex_color
        group_name = group.name if isinstance(group, WordGroup) else group
        self.group: str | None = group_name
        self.description: str = description
        self._source_plugin: str = 'native'

        if self.group is not None and not group_exists(self.group):
            if getattr(config, 'LEXER_ADD_INFO', True):
                _log_lexer_note(
                    f'El grupo {self.group!r} no existe aún al registrar la palabra clave {self.name!r}.',
                    'warn',
                )

    @classmethod
    def count(cls) -> int:
        """Devuelve el total de palabras clave registradas en el catálogo."""
        return len(MAP_KEYWORDS)

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


# Tablas globales en memoria
MAP_KEYWORDS: dict[str, Keyword] = {}


def add_keyword(
    name: str,
    hex_color: str = '#FFFFFF',
    group: str | WordGroup | None = None,
    description: str = '',
    *,
    allow_override: bool = False,
) -> Keyword:
    """
    Registra una palabra clave en el catálogo global del lexer.

    Args:
        name: Nombre de la palabra clave.
        hex_color: Color hexadecimal para resaltado.
        group: Grupo lógico al que se asocia (nombre o instancia WordGroup).
        description: Documentación de la palabra clave.
        allow_override: Si es True, permite sobrescribir una keyword existente.

    Returns:
        La instancia Keyword registrada.
    """
    if not name or not name.strip():
        error.LexerError(
            'Nombre de keyword inválido',
            errors.KEYWORD_INVALID_NAME,
            'El nombre de la palabra clave no puede estar vacío.',
        ).raise_error()

    name = name.strip()

    # Detección de procedencia de plugin
    current_loading = 'native'
    try:
        mod = sys.modules.get('gram.plugins.manager.core')
        if mod is not None and hasattr(mod, 'registry'):
            current_loading = mod.registry.get_current_loading() or 'native'
    except Exception:
        pass

    if name in MAP_KEYWORDS and not allow_override:
        existing_owner = getattr(MAP_KEYWORDS[name], '_source_plugin', 'native')
        error.LexerError(
            'Keyword ya registrada',
            errors.KEYWORD_ALREADY_EXISTS,
            f"La palabra clave {name!r} ya está registrada por '{existing_owner}'.",
            "Use allow_override=True para reemplazarla o elija un nombre diferente.",
        ).raise_error()

    group_name = group.name if isinstance(group, WordGroup) else group

    kw = Keyword(
        name=name,
        hex_color=hex_color,
        group=group_name,
        description=description,
    )
    kw._source_plugin = current_loading
    MAP_KEYWORDS[name] = kw

    # Si se especificó un grupo, sincronizar con el gestor de grupos
    if group_name is not None:
        grp = get_group(group_name)
        if grp is None:
            grp = add_group(group_name, allow_override=True)
        grp.add_keyword(kw)

    return kw


def get_keyword(name: str, *, strict: bool = False) -> Keyword | None:
    """
    Obtiene una palabra clave por su nombre exacto.

    Args:
        name: Nombre a buscar.
        strict: Si True, lanza LexerError si la palabra clave no existe.
    """
    kw = MAP_KEYWORDS.get(name)
    if kw is None and strict:
        error.LexerError(
            'Palabra clave no encontrada',
            errors.KEYWORD_NOT_FOUND,
            f"La palabra clave {name!r} no está registrada.",
            "Verifique que la palabra clave haya sido registrada antes de consultarla con strict=True.",
        ).raise_error()
    return kw


def keyword_exists(name: str) -> bool:
    """Indica si una palabra clave está presente en el catálogo."""
    return name in MAP_KEYWORDS


def remove_keyword(name: str, *, strict: bool = False) -> Keyword | None:
    """
    Elimina una palabra clave del catálogo y de todos sus grupos asociados.
    """
    kw = MAP_KEYWORDS.pop(name, None)
    if kw is None:
        if strict:
            error.LexerError(
                'Palabra clave no encontrada',
                errors.KEYWORD_NOT_FOUND,
                f"La palabra clave {name!r} no está registrada.",
            ).raise_error()
        return None

    # Remover también de los grupos que la contengan
    for grp in groups.all().values():
        grp.remove_keyword(name)

    return kw


def all_keywords() -> list[Keyword]:
    """Retorna una lista con todas las instancias de Keyword registradas."""
    return list(MAP_KEYWORDS.values())


def all_keyword_names() -> list[str]:
    """Retorna una lista con todos los nombres de palabras clave registradas."""
    return list(MAP_KEYWORDS.keys())


def is_empty() -> bool:
    """Indica si el catálogo de palabras clave está vacío."""
    return len(MAP_KEYWORDS) == 0


def count_keywords() -> int:
    """Retorna el número de palabras clave registradas."""
    return len(MAP_KEYWORDS)


# ==============================================================================
# 2. CLASE WORDGROUP Y GESTOR DE GRUPOS
# ==============================================================================

class WordGroup:
    """
    ES:
        Representa un conjunto temático o semántico de palabras clave (ej. '$TYPES', '$CONTROL').
        Solo admite asociar Keywords previamente registradas en el catálogo.

    EN:
        Represents a logical or semantic group of keywords (e.g. '$TYPES', '$CONTROL').
    """

    def __init__(
        self,
        name: str,
        values: list[str | Keyword] | None = None,
        color_group: str = '#FFA500',
        description: str = '',
    ) -> None:
        self.name: str = name
        self.color_group: str = color_group
        self.description: str = description
        self._keywords: dict[str, Keyword] = {}

        if values:
            for val in values:
                self.add_keyword(val)

    @property
    def values(self) -> list[str]:
        """Lista de nombres de palabras clave en este grupo."""
        return list(self._keywords.keys())

    @property
    def keywords_list(self) -> list[Keyword]:
        """Lista de objetos Keyword contenidos en este grupo."""
        return list(self._keywords.values())

    def contains(self, keyword_name: str) -> bool:
        """Determina si una palabra clave forma parte del grupo (insensible a mayúsculas)."""
        return keyword_name.lower() in {k.lower() for k in self._keywords}

    def add_keyword(self, item: str | Keyword) -> Keyword:
        """
        Añade una palabra clave al grupo. Debe existir previamente en el catálogo de keywords.
        """
        if isinstance(item, Keyword):
            name = item.name
            kw: Keyword | None = item
            if name not in MAP_KEYWORDS:
                MAP_KEYWORDS[name] = item
        else:
            name = item
            kw = get_keyword(name)

        if kw is None:
            if getattr(config, 'LEXER_ADD_ERROR', True):
                _log_lexer_note(
                    f'Intento de agregar palabra no registrada "{name}" al grupo "{self.name}"',
                    'error',
                )
            error.LexerError(
                f'Palabra clave no registrada: {name!r}',
                errors.WORDGROUP_KEYWORD_NOT_REGISTERED,
                f'La palabra clave "{name}" debe registrarse previamente en el lexer antes de asociarla al grupo "{self.name}".',
            ).raise_error()

        if kw.group is None:
            kw.group = self.name

        self._keywords[name] = kw
        return kw

    def remove_keyword(self, name: str) -> Keyword | None:
        """Elimina una palabra clave del grupo."""
        kw = self._keywords.pop(name, None)
        if kw is not None and kw.group == self.name:
            kw.group = None
        return kw

    def count(self) -> int:
        """Cantidad de palabras clave en el grupo."""
        return len(self._keywords)

    def clear(self) -> None:
        """Vacía el grupo."""
        self._keywords.clear()

    def __repr__(self) -> str:
        return f"WordGroup({self.name!r}, keywords={self.values}, color={self.color_group!r})"

    def __contains__(self, item: str | Keyword) -> bool:
        name = item.name if isinstance(item, Keyword) else item
        return self.contains(name)


class WordGroupManager:
    """
    Administrador centralizado de grupos léxicos.
    """

    def __init__(self) -> None:
        self._groups: dict[str, WordGroup] = {}

    def create(
        self,
        name: str | WordGroup,
        values: list[str | Keyword] | None = None,
        color_group: str = '#FFA500',
        description: str = '',
        *,
        allow_override: bool = False,
    ) -> WordGroup:
        """Crea y registra un nuevo grupo léxico."""
        group_name = name.name if isinstance(name, WordGroup) else str(name)
        if group_name in self._groups and not allow_override:
            if getattr(config, 'LEXER_ADD_ERROR', True):
                _log_lexer_note(f'El grupo {group_name!r} ya está registrado', 'error')
            error.LexerError(
                'Grupo ya existente',
                errors.WORDGROUP_ALREADY_EXISTS,
                f'El grupo de palabras clave "{group_name}" ya fue creado. Use allow_override=True para sobrescribirlo.',
            ).raise_error()

        group = WordGroup(
            name=group_name,
            values=values,
            color_group=color_group,
            description=description,
        )
        self._groups[group_name] = group

        if getattr(config, 'LEXER_ADD_INFO', True):
            _log_lexer_note(f'Grupo de palabras creado: {group_name!r}', 'success')

        return group

    def get(self, name: str | WordGroup, *, strict: bool = False) -> WordGroup | None:
        """Obtiene un grupo por su nombre o instancia."""
        group_name = name.name if isinstance(name, WordGroup) else name
        group = self._groups.get(group_name)
        if group is None and strict:
            if getattr(config, 'LEXER_ADD_ERROR', True):
                _log_lexer_note(f'Grupo no encontrado: {group_name!r}', 'error')
            error.LexerError(
                'Grupo no encontrado',
                errors.WORDGROUP_NOT_FOUND,
                f'El grupo de palabras clave "{group_name}" no está registrado.',
            ).raise_error()
        return group

    def exists(self, name: str | WordGroup) -> bool:
        """Indica si el grupo existe."""
        group_name = name.name if isinstance(name, WordGroup) else name
        return group_name in self._groups

    def remove(self, name: str | WordGroup) -> WordGroup | None:
        """Elimina un grupo."""
        group_name = name.name if isinstance(name, WordGroup) else name
        return self._groups.pop(group_name, None)

    def all(self) -> dict[str, WordGroup]:
        """Devuelve una copia del diccionario de grupos registrados."""
        return dict(self._groups)

    def all_names(self) -> list[str]:
        """Devuelve los nombres de todos los grupos registrados."""
        return list(self._groups.keys())

    def clear(self) -> None:
        """Limpia todos los grupos registrados."""
        self._groups.clear()


# Instancia singleton del gestor de grupos
groups: WordGroupManager = WordGroupManager()


def add_group(
    name: str | WordGroup,
    values: list[str | Keyword] | None = None,
    color_group: str = '#FFA500',
    description: str = '',
    *,
    allow_override: bool = False,
) -> WordGroup:
    """Crea y registra un nuevo grupo de palabras clave."""
    return groups.create(
        name=name,
        values=values,
        color_group=color_group,
        description=description,
        allow_override=allow_override,
    )


create_group = add_group


def get_group(name: str | WordGroup, *, strict: bool = False) -> WordGroup | None:
    """Obtiene un grupo por nombre."""
    return groups.get(name, strict=strict)


def group_exists(name: str | WordGroup) -> bool:
    """Indica si un grupo está registrado."""
    return groups.exists(name)


def remove_group(name: str | WordGroup) -> WordGroup | None:
    """Elimina un grupo registrado."""
    group_name = name.name if isinstance(name, WordGroup) else name
    grp = groups.remove(group_name)
    if grp is not None:
        for kw in grp.keywords_list:
            if kw.group == grp.name:
                kw.group = None
    return grp


def all_groups() -> dict[str, WordGroup]:
    """Retorna todos los grupos registrados."""
    return groups.all()


def all_group_names() -> list[str]:
    """Retorna los nombres de todos los grupos registrados."""
    return groups.all_names()


def exists_in_group(keyword_name: str | Keyword, group_name: str | WordGroup) -> bool:
    """Comprueba si una palabra clave pertenece a un grupo específico."""
    grp = get_group(group_name)
    if grp is None:
        return False
    kw_str = keyword_name.name if isinstance(keyword_name, Keyword) else str(keyword_name)
    return grp.contains(kw_str)


def clear_all() -> None:
    """
    Restablece y vacía completamente el catálogo de palabras clave y el registro de grupos.
    Indispensable para aislamiento en pruebas unitarias.
    """
    MAP_KEYWORDS.clear()
    groups.clear()


__all__ = [
    # Clases
    'Keyword',
    'WordGroup',
    'WordGroupManager',
    'groups',
    # Operaciones de Keywords
    'add_keyword',
    'get_keyword',
    'keyword_exists',
    'remove_keyword',
    'all_keywords',
    'all_keyword_names',
    'is_empty',
    'count_keywords',
    # Operaciones de Grupos
    'add_group',
    'create_group',
    'get_group',
    'group_exists',
    'remove_group',
    'all_groups',
    'all_group_names',
    'exists_in_group',
    # Utilidad Global
    'clear_all',
]
