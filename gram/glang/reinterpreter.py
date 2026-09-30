"""
Motor de Re-interpretación del AST de GLANG (`gram.glang.reinterpreter`).
========================================================================
Transforma el AST generado al analizar especificaciones `.glang` en
combinadores ejecutables (`dict[RuleType, Combinator]`) para el analizador sintáctico.
Permite generación dinámica de reglas, resolución de referencias circulares / hacia adelante,
fusión de gramáticas de plugins y construcción de analizadores de lenguaje completos.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from gram import config, errors
from gram.core.ast import ASTNode, ASTProgram
from gram.core.combinators import (
    Alt,
    AnyGrammar,
    Combinator,
    Item,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    Opt,
    Ref,
    RuleItem,
    Separator,
    Seq,
    Some,
    Tokenize,
)
from gram.core.lexer import Lexer
from gram.core.lexer.tokens import Token
from gram.core.lexer.words import add_group as lexer_add_group, add_keyword as lexer_add_keyword
from gram.core.parser import Parser
from gram.native.rules import (
    BLOCK,
    DECLARATION,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
    PASS,
    PROGRAM,
)
from gram.utilities import error
from gram.utilities.info import Node as InfoNode, Note

# Builder signature: (node: ASTNode, engine: ReinterpreterEngine) -> Combinator | None
CombinatorBuilderFn = Callable[["ASTNode", "ReinterpreterEngine"], "Combinator | None"]


class CombinatorBuilderRegistry:
    """
    Registro extensible de constructores de combinadores para el reinterpreter de GLang.

    Cada entrada asocia un nombre de nodo AST (str) con una función:
        builder(node: ASTNode, engine: ReinterpreterEngine) -> Combinator | None

    Uso desde un plugin o extensión:
        from gram.glang.reinterpreter import combinator_builders

        @combinator_builders.register("MY_NODE")
        def build_my_node(node, engine):
            return MyCustomCombinator(...)
    """

    def __init__(self) -> None:
        self._builders: dict[str, CombinatorBuilderFn] = {}

    def register(self, node_name: str) -> Callable[[CombinatorBuilderFn], CombinatorBuilderFn]:
        """Decorador para registrar un builder por nombre de nodo AST."""
        def decorator(fn: CombinatorBuilderFn) -> CombinatorBuilderFn:
            self._builders[node_name] = fn
            return fn
        return decorator

    def register_fn(self, node_name: str, fn: CombinatorBuilderFn) -> None:
        """Registra un builder directamente sin decorador."""
        self._builders[node_name] = fn

    def build(self, node: "ASTNode", engine: "ReinterpreterEngine") -> "Combinator | None":
        """Invoca el builder registrado para el nodo dado, o retorna None si no existe."""
        builder = self._builders.get(node.name)
        if builder is not None:
            return builder(node, engine)
        return None

    def has(self, node_name: str) -> bool:
        return node_name in self._builders


# Instancia global — importable por plugins
combinator_builders = CombinatorBuilderRegistry()


class DynamicRuleRegistry:
    """
    Registro dinámico de reglas sintácticas (RuleItems) generadas al vuelo
    a partir del AST del lenguaje GLang. Soporta forward-references por nombre o código.
    """

    def __init__(self) -> None:
        self.rules: dict[str, type[RuleItem]] = {}
        self.codes: dict[str, int] = {}
        self.descriptions: dict[str, str] = {}
        self._init_builtins()

    def _init_builtins(self) -> None:
        """Registra reglas predefinidas del núcleo de Gram."""
        self.rules['PASS'] = PASS
        self.codes['PASS'] = getattr(PASS, 'code', 999)
        self.rules['PROGRAM'] = PROGRAM
        self.codes['PROGRAM'] = PROGRAM.code
        self.rules['DECLARATION'] = DECLARATION
        self.codes['DECLARATION'] = DECLARATION.code
        self.rules['ENDLINE'] = ENDLINE
        self.codes['ENDLINE'] = ENDLINE.code
        self.rules['BLOCK'] = BLOCK
        self.codes['BLOCK'] = BLOCK.code
        self.rules['DOCSTRING'] = DOCSTRING
        self.codes['DOCSTRING'] = getattr(DOCSTRING, 'code', 5)
        self.rules['HEXADECIMAL'] = HEXADECIMAL
        self.codes['HEXADECIMAL'] = getattr(HEXADECIMAL, 'code', 6)

    def register(self, name: str, code: int | None = None, description: str = "") -> type[RuleItem]:
        """Registra o actualiza una regla por su nombre."""
        if name in self.rules:
            rule_cls = self.rules[name]
            if code is not None:
                rule_cls.code = code
                self.codes[name] = code
            if description:
                rule_cls.description = description
                self.descriptions[name] = description
            return rule_cls

        if code is None:
            code = 1000 + len(self.rules)

        rule_cls = type(name, (RuleItem,), {
            'name': name,
            'code': code,
            'description': description,
            'grammar': None,
        })
        self.rules[name] = rule_cls
        self.codes[name] = code
        self.descriptions[name] = description
        return rule_cls

    def get(self, identifier: str | int) -> type[RuleItem]:
        """
        Obtiene una regla por su identificador (nombre o código numérico).
        Permite:
            reference 1 (o '1') -> DECLARATION
            reference DECLARATION -> DECLARATION
            reference 1000 (o '1000') -> Regla con code=1000
            reference 'MY_RULE' -> Regla por su nombre
        Si no existe preventivamente, la crea como forward reference.
        """
        num_code: int | None = None
        if isinstance(identifier, int):
            num_code = identifier
        elif isinstance(identifier, str) and identifier.isdigit():
            num_code = int(identifier)

        # 1. Búsqueda por código numérico
        if num_code is not None:
            for rule_name, code_val in self.codes.items():
                if code_val == num_code and rule_name in self.rules:
                    return self.rules[rule_name]
            for rule_cls in self.rules.values():
                if getattr(rule_cls, 'code', None) == num_code:
                    return rule_cls

        str_ident = str(identifier)

        # 2. Búsqueda por clave directa en self.rules
        if str_ident in self.rules:
            return self.rules[str_ident]

        # 3. Búsqueda por __name__ o atributo 'name'
        for rule_cls in self.rules.values():
            if getattr(rule_cls, '__name__', '') == str_ident or getattr(rule_cls, 'name', '') == str_ident:
                return rule_cls

        # 4. Si fue un número no encontrado, registrar preventivamente con ese código
        if num_code is not None:
            synth_name = f"RULE_{num_code}"
            return self.register(synth_name, code=num_code)

        # 5. Registrar forward reference por nombre
        return self.register(str_ident)

    def has(self, identifier: str | int) -> bool:
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            code = int(identifier)
            return code in self.codes.values() or any(getattr(r, 'code', None) == code for r in self.rules.values())
        str_ident = str(identifier)
        if str_ident in self.rules:
            return True
        return any(
            getattr(r, '__name__', '') == str_ident or getattr(r, 'name', '') == str_ident
            for r in self.rules.values()
        )


class ReinterpreterEngine:
    """
    Motor de Re-interpretación del AST de GLang:
    Transforma un ASTProgram devuelto por el parser DSL en una gramática
    ejecutable de combinadores y reglas de producción.
    """

    def __init__(self, node: InfoNode | None = None):
        self.registry = DynamicRuleRegistry()
        self.includes: list[str] = []
        self.keywords: list[dict[str, Any]] = []
        self.grammar: dict[type[RuleItem], Combinator] = {}
        self.entry_rule_name: str | None = None
        self.rule_origins: dict[str, str] = {}
        self.plugin_combinators: list[Any] = []
        self.node = node or InfoNode('GLANG', 'Motor DSL GLang', priority=1)

    def compile(self, ast: ASTProgram) -> dict[type[RuleItem], Combinator]:
        """
        Compila el AST del DSL en un diccionario de gramática ejecutable:
        `dict[RuleType, Combinator]`.
        """
        # Fase 1: Recolectar metadatos (defines, includes, keywords, programa raíz)
        declarations: list[ASTNode] = []

        for node in ast.body:
            name = node.name

            if name == 'INCLUDE':
                self._process_include(node)
            elif name == 'DEFINE':
                self._process_define(node)
            elif name == 'KEYWORD':
                self._process_keyword(node)
            elif name == 'PROGRAM':
                self._process_program_entry(node)
            elif name == 'DECLARATION':
                declarations.append(node)
                self._pre_register_declaration(node)

        # Fase 2: Fusión de extensiones y plugins incluidos mediante include "plugin"
        self._merge_included_plugins()

        # Fase 3: Compilar cuerpos de combinadores para cada declaración
        for decl_node in declarations:
            self._compile_declaration(decl_node)

        # Fase 4: Configurar reglas raíz (PROGRAM y DECLARATION)
        self._setup_root_grammar()

        return self.grammar

    def _process_include(self, node: ASTNode) -> None:
        strings = node.strings
        if strings:
            self.includes.append(strings[0])
        elif node.values:
            for v in node.values:
                if str(v) != 'include':
                    self.includes.append(str(v))
                    break

    def _merge_included_plugins(self) -> None:
        """
        Fase de Fusión de Extensiones y Plugins:
        Itera sobre todos los plugins declarados mediante `include` en el DSL.
        Verifica que hayan sido cargados previamente de forma convencional.
        Extrae los combinadores (`plugin.get_combinators()`) y gramática (`plugin.get_grammar()`).
        Fusiona la gramática verificando colisiones e inmutabilidad estricta (prefijo GRAM_).
        """
        from gram.plugins.manager import Plugins
        from gram.plugins.registry import record_glang_collision

        for inc in self.includes:
            canonical = inc.strip().strip('"\'')
            if canonical == "ESSENCIAL_PACK":
                canonical = "GRAM_ESSENCIAL_PACK"
            elif canonical.startswith("plugins."):
                canonical = canonical[len("plugins."):]

            # 1. Verificar que el plugin esté previamente cargado
            plugin = Plugins.find(canonical)
            if plugin is None:
                error.CompilationError(
                    "Plugin no cargado",
                    errors.GLANG_INCLUDE_PLUGIN_NOT_LOADED,
                    f"El plugin '{inc}' referenciado en 'include' no ha sido cargado previamente.",
                    f"Asegúrese de cargar el plugin '{canonical}' antes de compilar código GLang que lo incluya.",
                ).raise_error()

            # 2. Extraer combinadores expuestos por el plugin
            try:
                exposed_combs = plugin.get_combinators()
            except Exception:
                exposed_combs = []

            if exposed_combs:
                self.plugin_combinators.extend(exposed_combs)
                for comb in exposed_combs:
                    comb_name = getattr(comb, 'name', getattr(comb, '__name__', None))
                    if comb_name and isinstance(comb_name, str):
                        comb_id = f"comb_{comb_name}"
                        if comb_id in self.rule_origins:
                            prev_comb_owner = self.rule_origins[comb_id]
                            record_glang_collision(
                                kind='combinator',
                                identifier=comb_name,
                                from_plugin=prev_comb_owner,
                                to_plugin=plugin.name,
                                resolved_by=plugin.name,
                            )
                            warn_msg = (
                                f"Colisión de combinador '{comb_name}': combinador de '{prev_comb_owner}' "
                                f"ha sido sobreescrito por el plugin '{plugin.name}'."
                            )
                            self.node.note(warn_msg, 'Warn')
                            if not config.LOG_HIDE_CONSOLE:
                                note_obj = Note(warn_msg, 'Warn')
                                print(note_obj.stringify(level=0, with_ansi=config.INFO_SUPPORT_ANSI))
                        self.rule_origins[comb_id] = plugin.name

            # 3. Extraer gramática expuesta por el plugin
            try:
                plugin_grammar = plugin.get_grammar()
            except Exception:
                plugin_grammar = {}

            # 4. Fusionar gramática y analizar colisiones
            for rule_key, combinator in plugin_grammar.items():
                rule_name = getattr(rule_key, 'name', str(rule_key))
                if rule_name in ('PROGRAM', 'DECLARATION'):
                    continue
                rule_code = getattr(rule_key, 'code', None)
                rule_desc = getattr(rule_key, 'description', '')

                # Caso 1: Violación de Inmutabilidad de GLang (prefijo GRAM_)
                if rule_name in self.rule_origins:
                    prev_origin = self.rule_origins[rule_name]
                    if rule_name.startswith('GRAM_'):
                        error.CompilationError(
                            "Violación de inmutabilidad en GLang",
                            errors.GLANG_IMMUTABILITY_VIOLATION,
                            f"El plugin '{plugin.name}' intentó sobrescribir la regla inmutable '{rule_name}'.",
                            "Las reglas de GLang con prefijo 'GRAM_' son estrictamente inmutables y no pueden ser modificadas por plugins.",
                        ).raise_error()

                    # Caso 2: Colisión entre extensiones o reglas no protegidas
                    record_glang_collision(
                        kind='rule_name',
                        identifier=rule_name,
                        from_plugin=prev_origin,
                        to_plugin=plugin.name,
                        resolved_by=plugin.name,
                    )
                    warn_msg = (
                        f"Colisión de regla '{rule_name}': regla proveniente de '{prev_origin}' "
                        f"ha sido sobreescrita por el plugin '{plugin.name}'."
                    )
                    self.node.note(warn_msg, 'Warn')
                    if not config.LOG_HIDE_CONSOLE:
                        note_obj = Note(warn_msg, 'Warn')
                        print(note_obj.stringify(level=0, with_ansi=config.INFO_SUPPORT_ANSI))

                elif rule_name.startswith('GRAM_'):
                    error.CompilationError(
                        "Violación de inmutabilidad en GLang",
                        errors.GLANG_IMMUTABILITY_VIOLATION,
                        f"El plugin '{plugin.name}' intentó definir la regla inmutable '{rule_name}'.",
                        "El prefijo 'GRAM_' está reservado exclusivamente para gramáticas nativas de GLang.",
                    ).raise_error()

                # Registrar / sobreescribir la regla
                self.rule_origins[rule_name] = plugin.name

                if isinstance(rule_key, type) and issubclass(rule_key, RuleItem):
                    rule_cls = rule_key
                    rule_cls.grammar = combinator
                    self.registry.rules[rule_name] = rule_cls
                    if rule_code is not None:
                        self.registry.codes[rule_name] = rule_code
                        rule_cls.code = rule_code
                else:
                    rule_cls = self.registry.register(rule_name, code=rule_code, description=rule_desc)
                    rule_cls.grammar = combinator

                # Limpiar clave previa si existía con nombre homónimo
                keys_to_remove = [k for k in self.grammar if getattr(k, 'name', str(k)) == rule_name]
                for k in keys_to_remove:
                    del self.grammar[k]

                self.grammar[rule_cls] = combinator

    def _process_define(self, node: ASTNode) -> None:
        name = None
        code = None
        description = ""

        # Extraer nombre y código de tokens / values
        for t in node.tokens:
            if t.token == Token.IDENT and name is None and str(t.value) != 'define':
                name = str(t.value)
            elif t.token == Token.NUMBER and code is None:
                code = int(t.value)

        if name is None or code is None:
            for val in node.values:
                if isinstance(val, str) and val != 'define' and name is None:
                    name = val
                elif isinstance(val, (int, float)) and code is None:
                    code = int(val)

        for child in node.children:
            if child.name == 'DOCSTRING':
                for t in child.tokens:
                    if t.token == Token.DOCSTRING:
                        description = str(t.value).strip('"\'\n ')
                        break

        if name:
            self.registry.register(name, code=code if code is not None else 1000, description=description)
            self.rule_origins[name] = 'GLang'

    def _process_keyword(self, node: ASTNode) -> None:
        kw_name = None
        kw_desc = ""
        kw_color = None
        kw_group = None

        for t in node.tokens:
            if t.token == Token.STRING and kw_name is None:
                kw_name = str(t.value)
                break
            elif t.token == Token.IDENT and kw_name is None and str(t.value) != 'Keyword':
                kw_name = str(t.value)

        if not kw_name and node.values:
            for v in node.values:
                if str(v) != 'Keyword':
                    kw_name = str(v)
                    break

        values = node.values
        for i, val in enumerate(values):
            if val == 'description' and i + 1 < len(values):
                kw_desc = str(values[i + 1])
            elif val == 'color' and i + 1 < len(values):
                c_cand = str(values[i + 1])
                if c_cand not in ('description', 'group', 'color'):
                    kw_color = c_cand
            elif val == 'group' and i + 1 < len(values):
                kw_group = str(values[i + 1])

        for child in node.walk():
            if child.name == 'HEXADECIMAL':
                parts = [str(t.value) for t in child.tokens if t.value is not None]
                if parts:
                    raw = "".join(parts).strip("'\"")
                    if not raw.startswith("#"):
                        raw = f"#{raw}"
                    kw_color = raw
            elif child.name == 'KEYWORD' and child is not node:
                for t in child.tokens:
                    if str(t.value).startswith('#'):
                        kw_color = str(t.value)

        if kw_name:
            data = {
                'name': kw_name,
                'description': kw_desc,
                'color': kw_color,
                'group': kw_group,
            }
            self.keywords.append(data)
            try:
                if kw_group:
                    lexer_add_group(kw_group, allow_override=True)
                lexer_add_keyword(kw_name, kw_color or '#FFFFFF', group=kw_group, description=kw_desc, allow_override=True)
            except Exception as exc:
                self.node.note(
                    f"No se pudo registrar la palabra clave '{kw_name}': {exc}",
                    'Warn',
                )

    def _process_program_entry(self, node: ASTNode) -> None:
        for child in node.walk():
            if child.name == 'REFERENCE':
                for t in child.tokens:
                    if t.token in (Token.IDENT, Token.NUMBER) and str(t.value) != 'reference':
                        self.entry_rule_name = str(t.value)
                        return
                for v in child.values:
                    if str(v) != 'reference':
                        self.entry_rule_name = str(v)
                        return

    def _pre_register_declaration(self, node: ASTNode) -> None:
        rule_name = self._get_declaration_rule_name(node)
        if rule_name:
            self.registry.get(rule_name)
            if rule_name not in self.rule_origins:
                self.rule_origins[rule_name] = 'GLang'

    def _get_declaration_rule_name(self, node: ASTNode) -> str | None:
        for t in node.tokens:
            if t.token == Token.IDENT:
                return str(t.value)
        if node.values:
            return str(node.values[0])
        return None

    def _get_combinator_type(self, node: ASTNode) -> str:
        combinator_keywords = {
            'Seq', 'Alt', 'Some', 'Many', 'Opt', 'optional',
            'Separator', 'separator', 'Tokenize', 'tokenize',
            'New', 'Item', 'item',
        }
        for t in node.tokens:
            if t.token in (Token.KEYWORD, Token.IDENT) and str(t.value) in combinator_keywords:
                return str(t.value)
        for v in node.values:
            if str(v) in combinator_keywords:
                return str(v)
        return 'Seq'

    def _compile_declaration(self, node: ASTNode) -> None:
        rule_name = self._get_declaration_rule_name(node)
        if not rule_name:
            return

        rule_cls = self.registry.get(rule_name)
        comb_type = self._get_combinator_type(node)

        child_combinators: list[Combinator] = []
        for child in node.children:
            if child.name == 'VALID_DECLARATION_BODY':
                for stmt in child.children:
                    c = self._build_combinator(stmt)
                    if c is not None:
                        child_combinators.append(c)
            else:
                c = self._build_combinator(child)
                if c is not None:
                    child_combinators.append(c)

        final_comb = self._wrap_combinator(comb_type, child_combinators, node)
        rule_cls.grammar = final_comb
        self.grammar[rule_cls] = final_comb

    def _wrap_combinator(
        self,
        comb_type: str,
        children: list[Combinator],
        node: ASTNode | None = None,
    ) -> Combinator:
        comb_upper = comb_type.lower()

        if comb_upper == 'seq':
            return Seq(*children) if children else Seq()
        elif comb_upper == 'alt':
            return Alt(*children) if children else Alt()
        elif comb_upper == 'some':
            if len(children) == 1:
                return Some(children[0])
            return Some(Seq(*children)) if children else Some(Seq())
        elif comb_upper == 'many':
            if len(children) == 1:
                return Many(children[0])
            return Many(Seq(*children)) if children else Many(Seq())
        elif comb_upper in ('opt', 'optional'):
            if len(children) == 1:
                return Opt(children[0])
            return Opt(Seq(*children)) if children else Opt(Seq())
        elif comb_upper in ('separator',):
            sep = Token.COMMA
            if node:
                sep = self._extract_sep_arg(node)
            return Separator(sep=sep, values=children)
        elif comb_upper in ('tokenize', 'new'):
            name = 'CustomToken'
            join_char = ''
            if node:
                for t in node.tokens:
                    if t.token == Token.STRING:
                        name = str(t.value)
                        break
            return Tokenize(*children, name=name, join_char=join_char) if children else Tokenize(name=name)
        elif comb_upper in ('item',):
            return Item(*children) if children else Item()
        else:
            return Seq(*children)

    def _build_combinator(self, node: ASTNode) -> Combinator | None:
        name = node.name

        if name == 'TOKEN':
            token_enum_name = None
            for t in node.tokens:
                if t.token == Token.IDENT and str(t.value) != 'tokens':
                    token_enum_name = str(t.value)
                    break
            if not token_enum_name:
                for v in node.values:
                    if str(v) != 'tokens':
                        token_enum_name = str(v)
                        break
            if token_enum_name and hasattr(Token, token_enum_name):
                return MatchToken(getattr(Token, token_enum_name))
            elif token_enum_name:
                return MatchToken(token_enum_name)
            return None

        elif name == 'WORD':
            word_str = None
            for t in node.tokens:
                if t.token in (Token.STRING, Token.IDENT) and str(t.value) != 'words':
                    word_str = str(t.value)
                    break
            if not word_str:
                for v in node.values:
                    if str(v) != 'words':
                        word_str = str(v)
                        break
            if word_str is not None:
                from gram.core.lexer.words import add_keyword, keyword_exists
                if not keyword_exists(word_str):
                    add_keyword(word_str, allow_override=True)
                return MatchKeyword(word_str)
            return None

        elif name == 'LITERAL':
            lit_val = None
            for t in node.tokens:
                if str(t.value) != 'literal' and t.token in (
                    Token.STRING, Token.NUMBER, Token.BOOL, Token.CHAR, Token.IDENT
                ):
                    lit_val = t.value
                    break
            if lit_val is None:
                for v in node.values:
                    if str(v) != 'literal':
                        lit_val = v
                        break
            if lit_val is not None:
                return Literal(lit_val)
            return Literal()

        elif name == 'ANY':
            return AnyGrammar()

        elif name == 'REFERENCE':
            ref_name = None
            for t in node.tokens:
                if t.token in (Token.IDENT, Token.NUMBER) and str(t.value) != 'reference':
                    ref_name = t.value
                    break
            if ref_name is None:
                for v in node.values:
                    if str(v) != 'reference':
                        ref_name = v
                        break
            if ref_name is not None:
                target_rule = self.registry.get(ref_name)
                return Ref(target_rule)
            return None

        elif name == 'GROUP':
            group_name = None
            mode = 'exclude'
            keywords: list[Any] = []

            for t in node.tokens:
                if t.token == Token.IDENT and str(t.value) not in ('groups', 'exclude', 'only'):
                    group_name = str(t.value)
                elif t.token == Token.KEYWORD:
                    if str(t.value) in ('exclude', 'only'):
                        mode = str(t.value)

            if not group_name:
                for v in node.values:
                    if str(v) not in ('groups', 'exclude', 'only'):
                        group_name = str(v)
                        break

            tokenlist_child = None
            for ch in node.children:
                if ch.name == 'TOKENLIST':
                    tokenlist_child = ch
                    break
                m = ch.find_first('TOKENLIST')
                if m:
                    tokenlist_child = m
                    break

            if tokenlist_child:
                keywords = self._extract_tokenlist_items(tokenlist_child)

            if group_name:
                if mode == 'exclude':
                    return MatchGroup(group_name, exclude=keywords if keywords else None)
                else:
                    return MatchGroup(group_name, only=keywords if keywords else None)
            return None

        elif name == 'SEQ_SYMBOL':
            regex_pat = None
            symbols_list: list[str] = []

            for t in node.tokens:
                if t.token == Token.STRING:
                    regex_pat = str(t.value)
                    break

            tokenlist_child = None
            for ch in node.children:
                if ch.name == 'TOKENLIST':
                    tokenlist_child = ch
                    break
                m = ch.find_first('TOKENLIST')
                if m:
                    tokenlist_child = m
                    break

            if tokenlist_child:
                items = self._extract_tokenlist_items(tokenlist_child)
                symbols_list = [str(x) for x in items]

            if symbols_list:
                return MatchSeqSymbol(symbols=symbols_list)
            if regex_pat:
                return MatchSeqSymbol(regex=regex_pat)
            return None

        elif name == 'SEPARATOR':
            sep_val = self._extract_sep_arg(node)
            values: list[Any] = []

            tokenlist_child = None
            for ch in node.children:
                if ch.name == 'TOKENLIST':
                    tokenlist_child = ch
                    break
                m = ch.find_first('TOKENLIST')
                if m:
                    tokenlist_child = m
                    break

            if tokenlist_child:
                values = self._extract_tokenlist_items(tokenlist_child)
            else:
                for child in node.children:
                    if child.name == 'VALID_DECLARATION_BODY':
                        for stmt in child.children:
                            c = self._build_combinator(stmt)
                            if c is not None:
                                values.append(c)
                    elif child.name == 'BLOCK':
                        for b_child in child.children:
                            if b_child.name == 'VALID_DECLARATION_BODY':
                                for stmt in b_child.children:
                                    c = self._build_combinator(stmt)
                                    if c is not None:
                                        values.append(c)
                            else:
                                c = self._build_combinator(b_child)
                                if c is not None:
                                    values.append(c)
                    elif child.name not in ('SEP_ARG',):
                        c = self._build_combinator(child)
                        if c is not None:
                            values.append(c)

            return Separator(sep=sep_val, values=values)

        elif name == 'ITEM':
            items: list[Any] = []
            tokenlist_child = None
            for ch in node.children:
                if ch.name == 'TOKENLIST':
                    tokenlist_child = ch
                    break
                m = ch.find_first('TOKENLIST')
                if m:
                    tokenlist_child = m
                    break

            if tokenlist_child:
                extracted = self._extract_tokenlist_items(tokenlist_child)
                converted = []
                for it in extracted:
                    if isinstance(it, Token):
                        converted.append(MatchToken(it))
                    elif isinstance(it, str) and hasattr(Token, it):
                        converted.append(MatchToken(getattr(Token, it)))
                    elif isinstance(it, Combinator):
                        converted.append(it)
                    else:
                        converted.append(Literal(it))
                return Item(*converted)
            else:
                for child in node.children:
                    if child.name == 'VALID_DECLARATION_BODY':
                        for stmt in child.children:
                            c = self._build_combinator(stmt)
                            if c is not None:
                                items.append(c)
                    elif child.name == 'BLOCK':
                        for b_child in child.children:
                            if b_child.name == 'VALID_DECLARATION_BODY':
                                for stmt in b_child.children:
                                    c = self._build_combinator(stmt)
                                    if c is not None:
                                        items.append(c)
                            else:
                                c = self._build_combinator(b_child)
                                if c is not None:
                                    items.append(c)
                    else:
                        c = self._build_combinator(child)
                        if c is not None:
                            items.append(c)
                return Item(*items)

        elif name == 'TOKENIZE':
            name_val = 'CustomToken'
            join_val = ''
            for t in node.tokens:
                if t.token == Token.STRING:
                    name_val = str(t.value)
                    break
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            return Tokenize(*children, name=name_val, join_char=join_val)

        elif name == 'SEQUENCE':
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            return Seq(*children)

        elif name == 'ALTERNATIVE':
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            return Alt(*children)

        elif name == 'SOME':
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            if len(children) == 1:
                return Some(children[0])
            return Some(Seq(*children))

        elif name == 'MANY':
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            if len(children) == 1:
                return Many(children[0])
            return Many(Seq(*children))

        elif name == 'OPTIONAL':
            children = []
            for child in node.children:
                if child.name == 'VALID_DECLARATION_BODY':
                    for stmt in child.children:
                        c = self._build_combinator(stmt)
                        if c is not None:
                            children.append(c)
            if len(children) == 1:
                return Opt(children[0])
            return Opt(Seq(*children))

        elif name == 'PASS':
            return Ref(self.registry.get('PASS'))

        # Extensión: consultar el registry global para combinadores no builtin
        if combinator_builders.has(name):
            return combinator_builders.build(node, self)

        return None

    def _extract_sep_arg(self, node: ASTNode) -> Any:
        """Extrae el token o literal especificado en `sep <ARG>`."""
        sep_arg_node = node.find_first('SEP_ARG')
        if sep_arg_node:
            for t in sep_arg_node.tokens:
                if t.token == Token.IDENT and str(t.value) != 'tokens':
                    name = str(t.value)
                    if hasattr(Token, name):
                        return getattr(Token, name)
                    return name
                elif t.token == Token.STRING:
                    return str(t.value)
            for v in sep_arg_node.values:
                if str(v) != 'tokens':
                    name = str(v)
                    if hasattr(Token, name):
                        return getattr(Token, name)
                    return name
        return Token.COMMA

    def _extract_tokenlist_items(self, node: ASTNode) -> list[Any]:
        """Extrae elementos de una lista delimitada entre corchetes."""
        items: list[Any] = []
        tokens = node.tokens
        i = 0
        while i < len(tokens):
            t = tokens[i]

            if t.token == Token.KEYWORD and str(t.value) == 'tokens':
                if i + 2 < len(tokens) and tokens[i + 1].token == Token.DOT:
                    ident_tok = tokens[i + 2]
                    tok_name = str(ident_tok.value)
                    if hasattr(Token, tok_name):
                        items.append(getattr(Token, tok_name))
                    else:
                        items.append(tok_name)
                    i += 3
                    continue
                i += 1
                continue

            elif t.token == Token.KEYWORD and str(t.value) == 'words':
                if i + 1 < len(tokens):
                    w_name = str(tokens[i + 1].value)
                    from gram.core.lexer.words import add_keyword, keyword_exists
                    if not keyword_exists(w_name):
                        add_keyword(w_name, allow_override=True)
                    items.append(MatchKeyword(w_name))
                    i += 2
                    continue
                i += 1
                continue

            elif t.token == Token.KEYWORD and str(t.value) == 'literal':
                if i + 1 < len(tokens) and tokens[i + 1].token not in (Token.COMMA, Token.RBRACKET):
                    items.append(Literal(tokens[i + 1].value))
                    i += 2
                    continue
                items.append(Literal())
                i += 1
                continue

            elif t.token in (Token.STRING, Token.NUMBER, Token.BOOL, Token.CHAR):
                items.append(t.value)
                i += 1
                continue

            elif t.token == Token.KEYWORD and str(t.value) == 'reference':
                if i + 1 < len(tokens) and tokens[i + 1].token in (Token.IDENT, Token.NUMBER):
                    items.append(Ref(self.registry.get(tokens[i + 1].value)))
                    i += 2
                    continue
                i += 1
                continue

            elif t.token == Token.IDENT and str(t.value) not in ('tokens', 'words', 'literal', 'reference'):
                name = str(t.value)
                if hasattr(Token, name):
                    items.append(getattr(Token, name))
                else:
                    items.append(name)
                i += 1
                continue

            i += 1

        return items

    def _setup_root_grammar(self) -> None:
        """Configura las reglas raíz requeridas (PROGRAM y DECLARATION)."""
        rule_refs = [
            Ref(rule)
            for rule in self.registry.rules.values()
            if rule not in (
                PASS,
                PROGRAM,
                DECLARATION,
                ENDLINE,
                BLOCK,
                DOCSTRING,
                HEXADECIMAL,
            )
            and rule.grammar is not None
        ]

        if rule_refs:
            self.grammar[DECLARATION] = Alt(*rule_refs)
        else:
            self.grammar[DECLARATION] = Alt(Ref(PASS))

        if self.entry_rule_name is not None and self.registry.has(self.entry_rule_name):
            entry_rule = self.registry.get(self.entry_rule_name)
            if entry_rule.grammar is None:
                error.CompilationError(
                    "Regla de entrada sin cuerpo",
                    errors.GLANG_INCLUDE_PLUGIN_NOT_LOADED,
                    f"La regla '{self.entry_rule_name}' declarada en [0]: no tiene cuerpo compilado.",
                    f"Asegúrese de definir el cuerpo de '{self.entry_rule_name}' con un bloque combinador.",
                ).raise_error()
            self.grammar[PROGRAM] = Many(Ref(entry_rule))
        else:
            self.grammar[PROGRAM] = Many(Ref(DECLARATION))


class LanguageCompiler:
    """
    Fachada de alto nivel para compilar gramáticas desde DSL y parsear
    código fuente escrito en el nuevo lenguaje.
    """

    def __init__(self, grammar: dict[type[RuleItem], Combinator], engine: ReinterpreterEngine):
        self.grammar = grammar
        self.engine = engine
        self.node = engine.node

    @classmethod
    def from_ast(cls, ast: ASTProgram) -> 'LanguageCompiler':
        engine = ReinterpreterEngine()
        grammar = engine.compile(ast)
        return cls(grammar, engine)

    @classmethod
    def from_dsl(cls, dsl_source: str) -> 'LanguageCompiler':
        from gram.glang.keywords import register_glang_keywords
        register_glang_keywords()
        from gram.glang.grammar import grammar as dsl_grammar
        dsl_source = dsl_source.lstrip('\ufeff')
        lines = dsl_source.splitlines()
        lex = Lexer(lines, comment_token=';', save_comments=False, ignore_newlines=False)
        tokens = lex.process()
        p = Parser(tokens)
        ast = p.parse(dsl_grammar)
        return cls.from_ast(ast)

    @classmethod
    def from_file(cls, filepath: str | Path) -> 'LanguageCompiler':
        file = Path(filepath)
        with file.open('r', encoding='utf-8-sig') as f:
            content = f.read()
        return cls.from_dsl(content)

    def parse(self, source_or_lines: str | list[str]) -> ASTProgram:
        """Parsea código de usuario según la gramática compilada."""
        if isinstance(source_or_lines, str):
            clean = source_or_lines.lstrip('\ufeff')
            lines = clean.splitlines()
        else:
            lines = [l.lstrip('\ufeff') if isinstance(l, str) else l for l in source_or_lines]

        lex = Lexer(lines)
        tokens = lex.process()
        p = Parser(tokens)
        return p.parse(self.grammar)

    def parse_file(self, filepath: str | Path) -> ASTProgram:
        """Parsea un archivo fuente de usuario según la gramática compilada."""
        file = Path(filepath)
        with file.open('r', encoding='utf-8-sig') as f:
            content = f.read()
        return self.parse(content)


__all__ = [
    'DynamicRuleRegistry',
    'ReinterpreterEngine',
    'LanguageCompiler',
    'CombinatorBuilderRegistry',
    'combinator_builders',
]
