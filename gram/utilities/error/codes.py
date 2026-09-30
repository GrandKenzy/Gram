from __future__ import annotations

class Codes:
    """
    ES:
        Representa un símbolo individual que pertenece a un grupo específico de códigos.
        
        Esta clase gestiona la validación y el registro de símbolos de un solo carácter
        utilizando un alfabeto alfanumérico estricto base-36 (0-9, A-Z). Cada instancia
        se asocia a un grupo definido previamente. Si se asigna al grupo 'default', 
        esta instancia se utilizará como comodín para llenar posiciones vacías al 
        ensamblar un código completo.

    EN:
        Represents an individual symbol belonging to a specific code group.
        
        This class handles the validation and registration of single-character symbols
        using a strict base-36 alphanumeric alphabet (0-9, A-Z). Each instance is
        associated with a previously defined group. If assigned to the 'default' group,
        this instance acts as a fallback wildcard to fill empty positions when
        assembling a complete code string.
    """

    GROUPS: dict[str, dict[str, Codes]] = {}
    MAP_LIMITS: dict[str, set[str]] = {}
    DEFAULT: Codes | None = None
    ALPHABET: str = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    name: str
    group: str
    value_str: str

    def __init__(self, name: str, value: int | str, group: str) -> None:
        """
        ES:
            Inicializa un nuevo código validando su longitud y sus caracteres permitidos.
            Si el grupo es 'default', se establece como código por defecto global.
            De lo contrario, se almacena en el registro de grupos bajo la llave de su valor.

        EN:
            Initializes a new code, validating its length and allowed characters.
            If the group is 'default', it is set as the global default code.
            Otherwise, it is stored in the groups registry under its value key.
        """
        self.name = name
        self.group = group

        value_str: str = str(value).upper()

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
        else:
            if self.group not in Codes.GROUPS:
                raise KeyError(
                    f'ES: El grupo "{self.group}" no existe. Usa set_map_codes primero.\n'
                    f'EN: The group "{self.group}" does not exist. Use set_map_codes first.'
                )
            Codes.GROUPS[self.group][self.value_str] = self

    def __repr__(self) -> str:
        """
        ES: Retorna una representación formal del código.
        EN: Returns a formal string representation of the code.
        """
        return f"Codes(name={self.name!r}, value={self.value_str!r}, group={self.group!r})"


def set_map_codes(**kwargs: list[str | int] | str | int) -> None:
    """
    ES:
        Define el orden de los grupos y calcula los límites de caracteres permitidos.
        
        Se encarga de inicializar el sistema de grupos, aceptando un número variable
        de argumentos por palabra clave. Cada argumento representa un grupo y su límite,
        el cual puede ser un número entero, una letra (string), o una lista combinada.
        Convierte estos límites en un conjunto (set) de caracteres explícitamente 
        permitidos (0-N o A-Letra) para validaciones de seguridad en O(1).

        Ejemplos soportados:
            set_map_codes(gravity=[3], documentation=[4])
            set_map_codes(tipo=['F'])
            set_map_codes(variado=[1, 'F'])

    EN:
        Defines the group order and calculates the allowed character limits.
        
        Initializes the grouping system by accepting an arbitrary number of keyword
        arguments. Each argument represents a group and its boundary, which can be
        an integer, a letter (string), or a combined list. It translates these boundaries
        into a set of explicitly allowed characters (0-N or A-Letter) for O(1) safety checks.

        Supported examples:
            set_map_codes(gravity=[3], documentation=[4])
            set_map_codes(tipo=['F'])
            set_map_codes(variado=[1, 'F'])
    """
    Codes.GROUPS.clear()
    Codes.MAP_LIMITS.clear()

    for group_name, limits in kwargs.items():
        allowed_chars: set[str] = set()
        limits_list: list[str | int]

        if isinstance(limits, list):
            limits_list = limits
        else:
            limits_list = [limits]

        for limit in limits_list:
            if isinstance(limit, int):
                for i in range(limit + 1):
                    allowed_chars.add(str(i))
            
            elif isinstance(limit, str):
                limit_upper: str = limit.upper()
                
                if limit_upper.isdigit():
                    for i in range(int(limit_upper) + 1):
                        allowed_chars.add(str(i))
                elif 'A' <= limit_upper <= 'Z':
                    for i in range(ord('A'), ord(limit_upper) + 1):
                        allowed_chars.add(chr(i))
                else:
                    raise ValueError(
                        f"ES: Límite de carácter no soportado: {limit}\n"
                        f"EN: Unsupported character limit: {limit}"
                    )
            else:
                raise TypeError(
                    f"ES: Tipo de límite no soportado: {type(limit)}\n"
                    f"EN: Unsupported limit type: {type(limit)}"
                )

        Codes.GROUPS[group_name] = {}
        Codes.MAP_LIMITS[group_name] = allowed_chars


class CodeError:
    """
    ES:
        Representa un error estructurado, validado y ensamblado dinámicamente a 
        partir de una colección de instancias de `Codes`.

        Se encarga de construir la cadena final en el orden estricto definido 
        por `set_map_codes`. Si alguna posición no es proporcionada, intentará
        inyectar la instancia 'default'. Además, evalúa si todos los caracteres
        cumplen con los límites establecidos para definir el error como Estándar
        (S / Seguro) o No Estándar (U / Inseguro). Si el mapa no fue inicializado,
        proporciona un fallback al default o levanta un error descriptivo.

    EN:
        Represents a structured error dynamically validated and assembled from 
        a collection of `Codes` instances.

        Responsible for building the final string in the strict order defined 
        by `set_map_codes`. If any position is omitted, it attempts to inject
        the 'default' instance. It also evaluates if all characters fall within 
        their allowed bounds to classify the error as Standard (S / Safe) or 
        Unstandard (U / Unsafe). If the map was never initialized, it provides
        a fallback to the default or raises a descriptive error.
    """

    codes_tuple: tuple[Codes, ...]
    name: str
    code_string: str

    def __init__(self, codes_tuple: tuple[Codes, ...], error_name: str = "UnknownError") -> None:
        """
        ES: Inicializa el error construyendo el string de código subyacente.
        EN: Initializes the error by building the underlying code string.
        """
        if not isinstance(codes_tuple, tuple) or not all(isinstance(c, Codes) for c in codes_tuple):
            raise TypeError(
                'ES: El argumento debe ser una tupla de instancias de Codes.\n'
                'EN: The argument must be a tuple of Codes instances.'
            )

        self.codes_tuple = codes_tuple
        self.name = error_name
        self.code_string = self._build_code_string()

    def _build_code_string(self) -> str:
        """
        ES: 
            Concatena los símbolos en el orden registrado, rellenando con default.
            Incluye protecciones en caso de que la librería sea utilizada sin
            inicializar el mapa de grupos.
        EN: 
            Concatenates symbols in the registered order, injecting defaults where missing.
            Includes fallbacks in case the library is used without initializing 
            the group map.
        """
        if not Codes.MAP_LIMITS:
            if Codes.DEFAULT is not None:
                return Codes.DEFAULT.value_str
            raise RuntimeError(
                'ES: El mapa de códigos no ha sido inicializado. Llama a `set_map_codes()` primero.\n'
                'EN: The code map has not been initialized. Call `set_map_codes()` first.'
            )

        result: list[str] = []
        
        for group_name in Codes.MAP_LIMITS.keys():
            code_for_group: Codes | None = next(
                (c for c in self.codes_tuple if c.group == group_name), 
                Codes.DEFAULT
            )

            if code_for_group is None:
                raise ValueError(
                    f'ES: Falta definir un código para el grupo "{group_name}" y no existe default.\n'
                    f'EN: Missing code for group "{group_name}" and no default exists.'
                )

            result.append(code_for_group.value_str)

        return "".join(result)

    @property
    def safe(self) -> bool:
        """
        ES: Comprueba en O(1) si cada dígito del error pertenece al conjunto permitido de su grupo.
        EN: Checks in O(1) if every error digit belongs to the allowed set of its group.
        """
        if not Codes.MAP_LIMITS:
            return True

        for group_name, allowed_chars in Codes.MAP_LIMITS.items():
            code_for_group: Codes | None = next(
                (c for c in self.codes_tuple if c.group == group_name), 
                Codes.DEFAULT
            )

            if code_for_group is None:
                return False

            if code_for_group.value_str not in allowed_chars:
                return False

        return True

    @property
    def type(self) -> str:
        """
        ES: Devuelve "S" si el código respeta los límites, "U" si los rompe.
        EN: Returns "S" if the code respects bounds, "U" if it breaks them.
        """
        return "S" if self.safe else "U"

    def is_standard(self) -> str:
        """
        ES: Alias de la propiedad type.
        EN: Alias for the type property.
        """
        return self.type

    def stringify(self) -> str:
        """
        ES: Formatea el error de manera legible, e.g., S-002A · ParserError.
        EN: Formats the error into a human-readable string, e.g., S-002A · ParserError.
        """
        return f"{self.type}-{self.code_string} · {self.name}"

    def __repr__(self) -> str:
        """
        ES: Retorna una representación formal del error.
        EN: Returns a formal string representation of the error.
        """
        return f'CodeError(code={self.code_string!r}, name={self.name!r})'

    def __eq__(self, other: object) -> bool:
        """
        ES: Dos errores son iguales si comparten la misma cadena ensamblada y nombre.
        EN: Two errors are equal if they share the same assembled string and name.
        """
        if not isinstance(other, CodeError):
            return NotImplemented
        return self.code_string == other.code_string and self.name == other.name

    def __hash__(self) -> int:
        """
        ES: Genera un hash determinista para diccionarios y conjuntos.
        EN: Generates a deterministic hash for dictionaries and sets.
        """
        return hash((self.code_string, self.name))

UNKNOWN = Codes('unknown', 0, 'default')