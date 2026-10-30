"""OSGDC code primitives used by the standalone error utilities."""

from __future__ import annotations


class Codes:
    """Represent and register one validated symbol in a code group.

    The ``default`` group is stored as the global fallback used by
    :class:`CodeError` when a configured group has no explicit symbol.
    """

    GROUPS: dict[str, dict[str, Codes]] = {}
    MAP_LIMITS: dict[str, set[str]] = {}
    DEFAULT: Codes | None = None
    ALPHABET: str = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    name: str
    group: str
    value_str: str

    def __init__(self, name: str, value: int | str, group: str) -> None:
        """Validate and register a single code symbol.

        Args:
            name: Human-readable symbol name.
            value: One numeric or alphanumeric symbol.
            group: Existing group name or ``"default"``.

        Raises:
            ValueError: If ``value`` is not one allowed character.
            KeyError: If ``group`` is not registered.

        Complexity: O(1).
        """
        self.name = name
        self.group = group

        value_str = str(value).upper()
        if not value_str or len(value_str) != 1:
            raise ValueError(
                'ES: El valor del código debe ser un único carácter.\n'
                'EN: The code value must be a single character.'
            )

        if value_str not in self.ALPHABET:
            raise ValueError(
                f'ES: El código solo puede contener estos caracteres: {self.ALPHABET}\n'
                f'EN: The code can only contain these characters: {self.ALPHABET}'
            )

        self.value_str = value_str
        if self.group == 'default':
            Codes.DEFAULT = self
            return

        if self.group not in Codes.GROUPS:
            raise KeyError(
                f'ES: El grupo "{self.group}" no existe. Usa set_map_codes primero.\n'
                f'EN: The group "{self.group}" does not exist. Use set_map_codes first.'
            )
        Codes.GROUPS[self.group][self.value_str] = self

    def __repr__(self) -> str:
        """Return the formal representation of this symbol."""
        return f"Codes(name={self.name!r}, value={self.value_str!r}, group={self.group!r})"


def _expand_limit(limit: str | int) -> set[str]:
    """Expand one numeric or alphabetic group limit into allowed characters.

    Args:
        limit: Inclusive integer, decimal string, or alphabetic bound.

    Returns:
        A set containing every permitted character.

    Raises:
        ValueError: If a string limit is unsupported.
        TypeError: If ``limit`` is not an integer or string.

    Complexity: O(K), where K is the expanded range size.
    """
    if isinstance(limit, int):
        return {str(index) for index in range(limit + 1)}

    if isinstance(limit, str):
        limit_upper = limit.upper()
        if limit_upper.isdigit():
            return {str(index) for index in range(int(limit_upper) + 1)}
        if 'A' <= limit_upper <= 'Z':
            return {
                chr(index)
                for index in range(ord('A'), ord(limit_upper) + 1)
            }
        raise ValueError(
            f"ES: Límite de carácter no soportado: {limit}\n"
            f"EN: Unsupported character limit: {limit}"
        )

    raise TypeError(
        f"ES: Tipo de límite no soportado: {type(limit)}\n"
        f"EN: Unsupported limit type: {type(limit)}"
    )


def set_map_codes(**kwargs: list[str | int] | str | int) -> None:
    """Atomically configure ordered code groups and allowed symbols.

    Each keyword defines one group. A limit may be an integer, a decimal string,
    an alphabetic bound, or a list combining those forms. All limits are validated
    before the public registries are replaced, so a failed call leaves the previous
    configuration intact.

    Raises:
        ValueError: If a string limit is unsupported.
        TypeError: If a limit is not an integer or string.

    Complexity: O(K), where K is the total number of expanded limit values.
    """
    new_groups: dict[str, dict[str, Codes]] = {}
    new_limits: dict[str, set[str]] = {}

    for group_name, limits in kwargs.items():
        limits_list = limits if isinstance(limits, list) else [limits]
        allowed_chars: set[str] = set()
        for limit in limits_list:
            allowed_chars.update(_expand_limit(limit))
        new_groups[group_name] = {}
        new_limits[group_name] = allowed_chars

    # Keep the public dictionary identities stable for external consumers.
    Codes.GROUPS.clear()
    Codes.GROUPS.update(new_groups)
    Codes.MAP_LIMITS.clear()
    Codes.MAP_LIMITS.update(new_limits)


class CodeError:
    """Build and validate an ordered structured error code."""

    codes_tuple: tuple[Codes, ...]
    name: str
    code_string: str
    _codes_by_group: dict[str, Codes]

    def __init__(
        self,
        codes_tuple: tuple[Codes, ...],
        error_name: str = "UnknownError",
    ) -> None:
        """Build the code string and index the first symbol for each group.

        Args:
            codes_tuple: Tuple of code symbols supplied by the catalog.
            error_name: Human-readable error name.

        Raises:
            TypeError: If ``codes_tuple`` is not a tuple of :class:`Codes`.

        Complexity: O(C + G), where C is the tuple length and G is the number
        of configured groups.
        """
        if not isinstance(codes_tuple, tuple) or not all(
            isinstance(code, Codes) for code in codes_tuple
        ):
            raise TypeError(
                'ES: El argumento debe ser una tupla de instancias de Codes.\n'
                'EN: The argument must be a tuple of Codes instances.'
            )

        self.codes_tuple = codes_tuple
        self.name = error_name
        self._codes_by_group = {}
        for code in codes_tuple:
            self._codes_by_group.setdefault(code.group, code)
        self.code_string = self._build_code_string()

    def _build_code_string(self) -> str:
        """Assemble symbols in configured group order using the default fallback.

        Raises:
            RuntimeError: If no map or default code is configured.
            ValueError: If a group has no symbol and no default exists.

        Complexity: O(G).
        """
        if not Codes.MAP_LIMITS:
            if Codes.DEFAULT is not None:
                return Codes.DEFAULT.value_str
            raise RuntimeError(
                'ES: El mapa de códigos no ha sido inicializado. Llama a `set_map_codes()` primero.\n'
                'EN: The code map has not been initialized. Call `set_map_codes()` first.'
            )

        result: list[str] = []
        for group_name in Codes.MAP_LIMITS:
            code_for_group = self._codes_by_group.get(group_name, Codes.DEFAULT)
            if code_for_group is None:
                raise ValueError(
                    f'ES: Falta definir un código para el grupo "{group_name}" y no existe default.\n'
                    f'EN: Missing code for group "{group_name}" and no default exists.'
                )
            result.append(code_for_group.value_str)
        return ''.join(result)

    @property
    def safe(self) -> bool:
        """Return whether every configured symbol is within its group limits.

        Complexity: O(G), using O(1) set membership per configured group.
        """
        if not Codes.MAP_LIMITS:
            return True

        for group_name, allowed_chars in Codes.MAP_LIMITS.items():
            code_for_group = self._codes_by_group.get(group_name, Codes.DEFAULT)
            if code_for_group is None:
                return False
            if code_for_group.value_str not in allowed_chars:
                return False
        return True

    @property
    def type(self) -> str:
        """Return ``"S"`` for safe codes and ``"U"`` for unsafe codes."""
        return "S" if self.safe else "U"

    def stringify(self) -> str:
        """Return the human-readable type, code, and error name."""
        return f"{self.type}-{self.code_string} · {self.name}"

    def __repr__(self) -> str:
        """Return the formal representation of this structured code."""
        return f'CodeError(code={self.code_string!r}, name={self.name!r})'

    def __eq__(self, other: object) -> bool:
        """Compare codes by assembled code string and error name."""
        if not isinstance(other, CodeError):
            return NotImplemented
        return self.code_string == other.code_string and self.name == other.name

    def __hash__(self) -> int:
        """Return a hash derived from the assembled code and error name."""
        return hash((self.code_string, self.name))


UNKNOWN = Codes('unknown', 0, 'default')
