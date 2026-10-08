"""
Gestor de Códigos y Asignación Automática de Identificadores (`gram.core.rules.codes`).
=====================================================================================
EN:
    Provides automatic, non-colliding numeric code generation for grammatical rules (RuleItem).
    `SetCode()` defines or resets the starting numeric base.
    `AutoCode()` monotonically increments and returns unique numeric codes, dynamically
    skipping any codes already allocated or registered manually.

ES:
    Proporciona generación automática de códigos numéricos sin colisiones para reglas gramaticales (RuleItem).
    `SetCode()` define o reinicia la base numérica de inicio.
    `AutoCode()` incrementa monotónicamente y devuelve códigos numéricos únicos, omitiendo
    dinámicamente cualquier código ya asignado o registrado manualmente.
"""
from __future__ import annotations

import threading
import warnings
from typing import Any


class CodeManager:
    """
    EN:
        Central thread-safe coordinator for grammatical rule identifiers.
        Guarantees that automatically allocated codes never collide with
        manually specified rule codes or protected framework ranges.

    ES:
        Coordinador central y seguro entre hilos para identificadores de reglas gramaticales.
        Garantiza que los códigos asignados automáticamente nunca colisionen con
        códigos de reglas manuales ni con rangos protegidos del framework.
    """

    DEFAULT_BASE_CODE: int = 10000
    PROTECTED_MAX: int = 20

    def __init__(self, base_code: int = DEFAULT_BASE_CODE, step: int = 1) -> None:
        self._lock = threading.Lock()
        self._base_code: int = base_code
        self._current_code: int = base_code
        self._step: int = step
        # Rangos protegidos nativos de Gram (0 a 20)
        self._used_codes: set[int] = set(range(0, self.PROTECTED_MAX + 1))
        self._rule_by_code: dict[int, Any] = {}

    @property
    def current_code(self) -> int:
        """Devuelve el valor actual del puntero de código."""
        with self._lock:
            return self._current_code

    @property
    def step(self) -> int:
        """Devuelve el incremento por defecto."""
        with self._lock:
            return self._step

    @property
    def used_codes(self) -> set[int]:
        """Devuelve una copia del conjunto de códigos utilizados."""
        with self._lock:
            return set(self._used_codes)

    def set_code(self, code: int = DEFAULT_BASE_CODE, step: int | None = None) -> int:
        """
        Establece el código base para la secuencia de generación automática.

        Args:
            code: Código numérico inicial.
            step: Incremento numérico entre códigos sucesivos (opcional).

        Returns:
            int: El código establecido.
        """
        if not isinstance(code, int):
            raise TypeError(f"SetCode espera un entero (int), recibido: {type(code).__name__}")
        if code < 0:
            raise ValueError(f"SetCode no admite códigos negativos: {code}")

        if 0 <= code <= self.PROTECTED_MAX:
            warnings.warn(
                f"El código {code} se encuentra dentro del rango protegido de Gram (0-{self.PROTECTED_MAX}). "
                f"Se recomienda usar valores >= 100 para plugins o >= 10000 para reglas de usuario.",
                UserWarning,
                stacklevel=2,
            )

        with self._lock:
            self._current_code = code
            self._base_code = code
            if step is not None:
                if not isinstance(step, int) or step <= 0:
                    raise ValueError(f"El step debe ser un entero positivo, recibido: {step}")
                self._step = step
            else:
                self._step = 1
            return self._current_code

    def next_code(self, step: int | None = None) -> int:
        """
        Calcula y reserva el siguiente código numérico disponible, garantizando la no colisión.

        Args:
            step: Incremento específico para esta llamada (opcional).

        Returns:
            int: Código numérico único y no colisionante.
        """
        with self._lock:
            s = self._step if step is None else int(step)
            if s <= 0:
                s = 1

            candidate = self._current_code
            while candidate in self._used_codes:
                candidate += s

            self._used_codes.add(candidate)
            self._current_code = candidate + s
            return candidate

    def peek(self, step: int | None = None) -> int:
        """
        Previsualiza el siguiente código que sería asignado sin consumirlo ni reservarlo.
        """
        with self._lock:
            s = self._step if step is None else int(step)
            if s <= 0:
                s = 1

            candidate = self._current_code
            while candidate in self._used_codes:
                candidate += s
            return candidate

    def is_used(self, code: int) -> bool:
        """Verifica si un código numérico ya está reservado o en uso."""
        with self._lock:
            return code in self._used_codes

    def register(self, code: int, rule: Any = None) -> None:
        """
        Registra un código numérico como utilizado (por ejemplo, asignado manualmente en una regla).
        """
        if not isinstance(code, int):
            return

        with self._lock:
            from gram import config
            if getattr(config, "RULES_WARN_COLLISION", False) and code in self._used_codes and code > self.PROTECTED_MAX:
                existing = self._rule_by_code.get(code)
                if (
                    existing is not None
                    and rule is not None
                    and existing is not rule
                    and getattr(existing, "__name__", "") != getattr(rule, "__name__", "")
                ):
                    rule_name = getattr(rule, "__name__", str(rule))
                    existing_name = getattr(existing, "__name__", str(existing))
                    warnings.warn(
                        f"Posible colisión de códigos en Gram: la regla '{rule_name}' utiliza el código {code}, "
                        f"que ya había sido registrado por '{existing_name}'.",
                        UserWarning,
                        stacklevel=2,
                    )

            self._used_codes.add(code)
            if rule is not None:
                self._rule_by_code[code] = rule

    def reset(self, code: int = DEFAULT_BASE_CODE, clear_used: bool = False) -> int:
        """
        Reinicia el generador a su código base inicial.

        Args:
            code: Nuevo código base (por defecto 10000).
            clear_used: Si es True, limpia todos los códigos registrados excepto el rango protegido 0-20.
        """
        with self._lock:
            self._base_code = code
            self._current_code = code
            self._step = 1
            if clear_used:
                self._used_codes = set(range(0, self.PROTECTED_MAX + 1))
                self._rule_by_code.clear()
            return self._current_code


# Instancia singleton global del gestor
code_manager: CodeManager = CodeManager()


class AutoCode(int):
    """
    EN:
        Generates and returns an automatic non-colliding numeric code for Gram RuleItems.
        Inherits from `int`, seamlessly supporting all integer operations, formatting,
        and JSON serialization.

    ES:
        Genera y devuelve un código numérico automático sin colisiones para RuleItems de Gram.
        Hereda de `int`, siendo totalmente compatible con operaciones aritméticas, formateo
        y serialización JSON.

    Usage / Uso:
        ```python
        # 1. Dentro de un RuleItem:
        class MiRegla(gram.RuleItem):
            code = gram.AutoCode()

        # 2. Con base establecida por SetCode:
        gram.SetCode(100_000)
        class OtraRegla(gram.RuleItem):
            code = gram.AutoCode()  # -> 100_000
        ```
    """

    def __new__(cls, step: int | None = None) -> AutoCode:
        val = code_manager.next_code(step=step)
        return super().__new__(cls, val)

    @classmethod
    def current(cls) -> int:
        """Retorna el código actual del puntero."""
        return code_manager.current_code

    @classmethod
    def peek(cls, step: int | None = None) -> int:
        """Previsualiza el siguiente código disponible sin consumirlo."""
        return code_manager.peek(step=step)

    @classmethod
    def is_used(cls, code: int) -> bool:
        """Comprueba si un código numérico ya se encuentra registrado."""
        return code_manager.is_used(code)

    @classmethod
    def used_codes(cls) -> set[int]:
        """Devuelve un conjunto con todos los códigos utilizados."""
        return code_manager.used_codes

    @classmethod
    def register(cls, code: int, rule: Any = None) -> None:
        """Registra un código como utilizado."""
        code_manager.register(code, rule=rule)

    @classmethod
    def reset(cls, code: int = CodeManager.DEFAULT_BASE_CODE, clear_used: bool = False) -> int:
        """Reinicia el catálogo y puntero de códigos."""
        return code_manager.reset(code=code, clear_used=clear_used)

    @classmethod
    def set_code(cls, code: int = CodeManager.DEFAULT_BASE_CODE, step: int | None = None) -> int:
        """Establece la base de código."""
        return code_manager.set_code(code=code, step=step)


def SetCode(code: int = CodeManager.DEFAULT_BASE_CODE, step: int | None = None) -> int:
    """
    EN:
        Sets the starting base code for automatic RuleItem code generation.
    ES:
        Establece el código base para la generación automática de códigos de RuleItem.

    Args:
        code: Valor numérico inicial para los códigos generados (por defecto 10000).
        step: Incremento numérico entre códigos sucesivos (opcional).

    Returns:
        int: El código numérico base establecido.

    Usage / Uso:
        ```python
        gram.SetCode(100_000)
        c1 = gram.AutoCode()  # -> 100_000
        c2 = gram.AutoCode()  # -> 100_001
        ```
    """
    return code_manager.set_code(code=code, step=step)


__all__ = [
    "AutoCode",
    "SetCode",
    "CodeManager",
    "code_manager",
]
