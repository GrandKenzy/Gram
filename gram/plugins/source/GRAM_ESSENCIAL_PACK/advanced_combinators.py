"""
Combinadores avanzados para GRAM_ESSENCIAL_PACK.
=================================================
Incluye:
- Skip: Interrumpe limpiamente una secuencia.
- ErrorCombinator: Inspecciona y captura errores del stack de Gram.
- If: Condicional con afirmaciones, bifurcación ok/fail y lookahead seguro.
- Peek: Lookahead positivo (ancho cero).
- Not: Lookahead negativo (ancho cero).
- Until: Consumo hasta combinador objetivo.
- Req: Requerimientos fluidos de validación y transformación de tokens.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gram.core.ast.analyzer import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.mods import register_custom_mod
from gram.core.combinators.signals import SkipFlowSignal
from gram.utilities.error.codes import CodeError
from gram.utilities import error
from gram.utilities.error.stack import StackError


class Skip(Combinator):
    """
    Combinador que detiene el flujo actual de una Secuencia (Seq).
    Cuando el Parser alcanza Skip(), interrumpe la evaluación de los
    siguientes combinadores y considera la Secuencia terminada con éxito.
    """

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        target_node = self._get_node(analyzer)
        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("Skip() alcanzado: interrumpiendo flujo de secuencia.", "Advice")

        raise SkipFlowSignal()


class ErrorCombinator(Combinator):
    """
    Atrapa errores previos en el procesamiento.
    length=0 atrapa todos los errores actuales en el stack.
    length=N atrapa hasta N errores recientes.
    """

    def __init__(self, length: int = 1):
        super().__init__()
        self.length = length

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        target_node = self._get_node(analyzer)
        total_errors = StackError.count()

        if total_errors == 0:
            if ignore_errors:
                return None
            err_code = errors.COMBINATOR_FAILED
            error.ParserError(
                "El combinador ErrorCombinator no encontró ningún fallo para atrapar.",
                err_code,
            ).raise_error()

        all_errors = StackError.all()
        to_catch = total_errors if self.length == 0 else min(self.length, total_errors)
        caught_errors = all_errors[-to_catch:]

        # Limpiar y restaurar errores no capturados
        StackError.clear()
        for err in all_errors[:-to_catch]:
            StackError.add(err)

        caught_errors.reverse()
        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"ErrorCombinator atrapó {len(caught_errors)} errores.", "Success")

        return caught_errors


class Req(Combinator):
    """
    Combinador fluido para requerir, validar y transformar tokens.
    Ejemplo: Req('IDENT').is_lower().length(10)
    """

    def __init__(self, target_token: str):
        super().__init__()
        self.target_token = target_token
        self._operations: list[Callable[[TokenType], TokenType]] = []

    def _add_op(self, op: Callable[[TokenType], TokenType]) -> Req:
        self._operations.append(op)
        return self

    # --- Validaciones ---

    def is_lower(self) -> Req:
        def op(t: TokenType) -> TokenType:
            if not str(t.value).islower():
                raise ValueError(f"El token '{t.value}' no está en minúsculas.")
            return t
        return self._add_op(op)

    def is_upper(self) -> Req:
        def op(t: TokenType) -> TokenType:
            if not str(t.value).isupper():
                raise ValueError(f"El token '{t.value}' no está en mayúsculas.")
            return t
        return self._add_op(op)

    def is_snake_case(self) -> Req:
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            if val != val.lower() or " " in val:
                raise ValueError(f"El token '{t.value}' no es snake_case.")
            return t
        return self._add_op(op)

    def is_camel_case(self) -> Req:
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            if "_" in val or " " in val or not (val and val[0].isalpha()):
                raise ValueError(f"El token '{t.value}' no es camelCase.")
            return t
        return self._add_op(op)

    def startswith(self, prefix: str) -> Req:
        def op(t: TokenType) -> TokenType:
            if not str(t.value).startswith(prefix):
                raise ValueError(f"El token '{t.value}' no empieza con '{prefix}'.")
            return t
        return self._add_op(op)

    def endswith(self, suffix: str) -> Req:
        def op(t: TokenType) -> TokenType:
            if not str(t.value).endswith(suffix):
                raise ValueError(f"El token '{t.value}' no termina con '{suffix}'.")
            return t
        return self._add_op(op)

    def length(self, n: int) -> Req:
        def op(t: TokenType) -> TokenType:
            if len(str(t.value)) != n:
                raise ValueError(f"El token '{t.value}' no tiene longitud {n}.")
            return t
        return self._add_op(op)

    def min(self, n: int | float) -> Req:
        def op(t: TokenType) -> TokenType:
            try:
                val_num = float(t.value)
                if val_num < n:
                    raise ValueError(f"El valor '{t.value}' es menor al mínimo {n}.")
            except ValueError:
                if len(str(t.value)) < n:
                    raise ValueError(f"El token '{t.value}' tiene longitud menor a {n}.")
            return t
        return self._add_op(op)

    def max(self, n: int | float) -> Req:
        def op(t: TokenType) -> TokenType:
            try:
                val_num = float(t.value)
                if val_num > n:
                    raise ValueError(f"El valor '{t.value}' supera el máximo {n}.")
            except ValueError:
                if len(str(t.value)) > n:
                    raise ValueError(f"El token '{t.value}' tiene longitud mayor a {n}.")
            return t
        return self._add_op(op)

    def equal(self, expected: str) -> Req:
        def op(t: TokenType) -> TokenType:
            if str(t.value) != str(expected):
                raise ValueError(f"Se esperaba '{expected}', se recibió '{t.value}'.")
            return t
        return self._add_op(op)

    def unequal(self, not_expected: str) -> Req:
        def op(t: TokenType) -> TokenType:
            if str(t.value) == str(not_expected):
                raise ValueError(f"El token no debe ser igual a '{not_expected}'.")
            return t
        return self._add_op(op)

    def mindig(self, n: int) -> Req:
        def op(t: TokenType) -> TokenType:
            digs = sum(c.isdigit() for c in str(t.value))
            if digs < n:
                raise ValueError(f"El token '{t.value}' tiene menos de {n} dígitos.")
            return t
        return self._add_op(op)

    def maxdig(self, n: int) -> Req:
        def op(t: TokenType) -> TokenType:
            digs = sum(c.isdigit() for c in str(t.value))
            if digs > n:
                raise ValueError(f"El token '{t.value}' excede {n} dígitos.")
            return t
        return self._add_op(op)

    def contains(self, *items: str) -> Req:
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            for item in items:
                if item not in val:
                    raise ValueError(f"El token no contiene '{item}'.")
            return t
        return self._add_op(op)

    def excludes(self, *items: str) -> Req:
        def op(t: TokenType) -> TokenType:
            val = str(t.value)
            for item in items:
                if item in val:
                    raise ValueError(f"El token contiene '{item}' de forma ilegal.")
            return t
        return self._add_op(op)

    # --- Transformaciones ---

    def apply_lower(self) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).lower()
            return t
        return self._add_op(op)

    def apply_upper(self) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).upper()
            return t
        return self._add_op(op)

    def apply_camel(self) -> Req:
        def op(t: TokenType) -> TokenType:
            parts = str(t.value).replace("_", " ").split()
            if not parts:
                return t
            t.value = parts[0].lower() + "".join(x.title() for x in parts[1:])
            return t
        return self._add_op(op)

    def transform(self, target_type: Callable[[Any], Any]) -> Req:
        def op(t: TokenType) -> TokenType:
            try:
                t.value = target_type(t.value)
            except Exception as e:
                raise ValueError(f"No se pudo transformar a {getattr(target_type, '__name__', str(target_type))}: {e}")
            return t
        return self._add_op(op)

    def replace(self, old: str, new: str) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).replace(old, new)
            return t
        return self._add_op(op)

    def change(self, new_val: Any) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = new_val
            return t
        return self._add_op(op)

    def addl(self, prefix: str) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = prefix + str(t.value)
            return t
        return self._add_op(op)

    def addr(self, suffix: str) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value) + suffix
            return t
        return self._add_op(op)

    def apply_zfill(self, width: int) -> Req:
        def op(t: TokenType) -> TokenType:
            t.value = str(t.value).zfill(width)
            return t
        return self._add_op(op)

    # --- Ejecución ---

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        active_token = current if current is not None else parser.consume(node=target_node)
        if active_token is None:
            if ignore_errors:
                return None
            err_code = errors.PARSER_EARLY_EOF
            error.ParserError("Fin de archivo inesperado en combinador Req.", err_code).raise_error()

        token_name = getattr(active_token.token, "name", str(active_token.token))
        if token_name != self.target_token and str(active_token.token) != self.target_token:
            if ignore_errors:
                return None
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note(f"Se esperaba {self.target_token}, se recibió {token_name}", "Error")
            err_code = errors.PARSER_UNEXPECTED_TOKEN
            error.ParserError(
                f"Req esperaba '{self.target_token}' pero encontró '{token_name}'.",
                err_code,
                f"Línea {active_token.line}, Columna {active_token.col}",
            ).raise_error()

        cloned_token = copy.copy(active_token)
        for i, operation in enumerate(self._operations):
            try:
                cloned_token = operation(cloned_token)
            except ValueError as e:
                if ignore_errors:
                    return None
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(f"Req validación fallida (Paso {i + 1}): {e}", "Error")
                err_code = errors.COMBINATOR_FAILED
                error.ParserError(
                    f"Fallo en requerimiento: {e}",
                    err_code,
                    f"Línea {active_token.line}, Columna {active_token.col}",
                ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Req validado exitosamente: {cloned_token.value}", "Success")

        return cloned_token


class If(Combinator):
    """
    Combinador condicional: evalúa 'conditions' y bifurca entre ok y fail.

    - Si todas las condiciones se cumplen:
      - Si restore=False: consume las condiciones y evalúa 'ok'.
      - Si restore=True: restaura el parser al inicio y evalúa 'ok' (modo lookahead).
    - Si alguna condición falla:
      - Restaura el parser a la posición previa.
      - Si se definió 'fail', lo ejecuta.
      - Si no se definió 'fail', retorna None (si ignore_errors) o lanza ParserError.
    """

    code: int = 2005
    name: str = "If"
    description: str = "Combinador condicional: afirma una secuencia de condiciones y bifurca entre ok y fail."
    header_class: bool = True

    def __init__(
        self,
        conditions: list[Any] | tuple[Any, ...] | Any,
        ok: Any = None,
        fail: Any = None,
        *,
        restore: bool = False,
    ):
        super().__init__()
        self.header_class = True
        if not isinstance(conditions, (list, tuple)):
            self.conditions = [conditions]
        else:
            self.conditions = list(conditions)

        if isinstance(ok, (list, tuple)):
            from gram.core.combinators.sequence import Seq
            self.ok = Seq(*ok)
        else:
            self.ok = ok

        if isinstance(fail, (list, tuple)):
            from gram.core.combinators.sequence import Seq
            self.fail = Seq(*fail)
        else:
            self.fail = fail

        self.restore = restore

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        checkpoint = parser.savepoint(node=target_node)

        if not self.conditions:
            if ignore_errors:
                return None
            err_code = errors.COMBINATOR_FAILED
            error.ParserError(
                "El combinador If() requiere al menos una condición.",
                err_code,
            ).raise_error()

        # 1. Evaluar condiciones
        conditions_passed = True
        cond_results: list[Any] = []

        for index, cond in enumerate(self.conditions, start=1):
            active_token = current if index == 1 else None
            try:
                res = self._dispatch_sub(cond, analyzer, active_token, ignore_errors=True)
            except Exception:
                res = None

            if res is None:
                conditions_passed = False
                break
            cond_results.append(res)

        # 2. Si falló alguna condición -> rama fail
        if not conditions_passed:
            parser.restore(checkpoint, node=target_node)

            if self.fail is not None:
                return self._dispatch_sub(self.fail, analyzer, current, ignore_errors=ignore_errors)

            if ignore_errors:
                return None

            err_code = errors.COMBINATOR_FAILED
            curr_peek = parser.peek()
            tok_info = f" en '{curr_peek.value}'" if curr_peek else ""
            error.ParserError(
                f"Condición de If() no cumplida{tok_info}.",
                err_code,
            ).raise_error()

        # 3. Si se cumplieron todas las condiciones -> rama ok
        if self.restore:
            parser.restore(checkpoint, node=target_node)
            if self.ok is not None:
                return self._dispatch_sub(self.ok, analyzer, current, ignore_errors=ignore_errors)
            return cond_results

        if self.ok is not None:
            ok_res = self._dispatch_sub(self.ok, analyzer, None, ignore_errors=ignore_errors)
            if ok_res is None:
                parser.restore(checkpoint, node=target_node)
                return None
            return [*cond_results, ok_res]

        return cond_results


class Peek(Combinator):
    """
    Lookahead positivo (afirmación anticipada).
    Verifica que el combinador interno coincida sin consumir tokens.
    """

    name: str = "Peek"
    code: int = 2010
    description: str = "Lookahead positivo: afirma una condición sin avanzar el cursor."

    def __init__(self, combinator: Any):
        super().__init__()
        self.combinator = combinator

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        checkpoint = parser.savepoint(node=target_node)

        try:
            res = self._dispatch_sub(self.combinator, analyzer, current, ignore_errors=True)
        except Exception:
            res = None

        parser.restore(checkpoint, node=target_node)

        if res is not None:
            return []

        if ignore_errors:
            return None

        err_code = errors.COMBINATOR_FAILED
        error.ParserError(
            f"La afirmación anticipada Peek({self.combinator}) falló.",
            err_code,
        ).raise_error()


class Not(Combinator):
    """
    Lookahead negativo (afirmación negativa).
    Tiene éxito si el combinador interno NO coincide, sin consumir tokens.
    """

    name: str = "Not"
    code: int = 2011
    description: str = "Lookahead negativo: tiene éxito si el combinador interno falla, sin consumir tokens."

    def __init__(self, combinator: Any):
        super().__init__()
        self.combinator = combinator

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        checkpoint = parser.savepoint(node=target_node)

        try:
            res = self._dispatch_sub(self.combinator, analyzer, current, ignore_errors=True)
        except Exception:
            res = None

        parser.restore(checkpoint, node=target_node)

        if res is not None:
            if ignore_errors:
                return None
            err_code = errors.COMBINATOR_FAILED
            error.ParserError(
                f"El combinador Not({self.combinator}) detectó una coincidencia prohibida.",
                err_code,
            ).raise_error()

        return []


class Until(Combinator):
    """
    Consume tokens secuencialmente hasta que el combinador target coincida.
    """

    name: str = "Until"
    code: int = 2012
    description: str = "Consume tokens secuencialmente hasta que el combinador target coincide."

    def __init__(
        self,
        target: Any,
        *,
        consume_target: bool = False,
        max_tokens: int | None = None,
    ):
        super().__init__()
        self.target = target
        self.consume_target = consume_target
        self.max_tokens = max_tokens

    def parse(
        self,
        analyzer: ASTAnalyzer | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        collected: list[Any] = []
        active_token = current if current is not None else parser.consume(node=target_node)

        while active_token is not None:
            chk = parser.savepoint(node=target_node)
            try:
                target_res = self._dispatch_sub(self.target, analyzer, active_token, ignore_errors=True)
            except Exception:
                target_res = None

            if target_res is not None:
                if self.consume_target:
                    if isinstance(target_res, list):
                        collected.extend(target_res)
                    else:
                        collected.append(target_res)
                else:
                    parser.restore(chk, node=target_node)
                return collected

            parser.restore(chk, node=target_node)
            collected.append(active_token)

            if self.max_tokens is not None and len(collected) >= self.max_tokens:
                break

            if not parser.not_empty():
                break

            active_token = parser.consume(node=target_node)

        if ignore_errors:
            return collected

        err_code = errors.COMBINATOR_FAILED
        error.ParserError(
            f"Until({self.target}) alcanzó el final sin encontrar el objetivo.",
            err_code,
        ).raise_error()


# Registrar los combinadores
for c in (Skip, ErrorCombinator, Req, If, Peek, Not, Until):
    register_custom_mod(c)

__all__ = [
    "Skip",
    "ErrorCombinator",
    "Req",
    "If",
    "Peek",
    "Not",
    "Until",
]
