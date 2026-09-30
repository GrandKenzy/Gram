"""
Palabras Clave y Grupos del Lenguaje Declarativo GLANG (`gram.glang.keywords`).
=============================================================================
Registra en el motor léxico de Gram los grupos y palabras clave reservadas
para la especificación formal de gramáticas mediante la sintaxis GLANG (.glang).

Este módulo se importa automáticamente al usar ``LanguageCompiler.from_dsl()``
o ``LanguageCompiler.from_file()``. No necesita importarse manualmente.
"""
from __future__ import annotations

from gram.core.lexer.words import add_group, add_keyword


def register_glang_keywords() -> None:
    """Registra o re-registra todos los grupos y palabras clave de GLang en el motor léxico."""
    # Grupos de palabras clave de GLang
    add_group("KEYWORD_PROPERTIE", allow_override=True)
    add_group("CLN_COMBINATOR_MAIN", allow_override=True)
    add_group("COMBINATOR_MATCH", allow_override=True)
    add_group("CLN_SUBCOMBINATOR_NAME", allow_override=True)
    add_group("COMBINATOR_ARG", allow_override=True)

    # Directivas base
    add_keyword("include", "#FF00FF", description="Directiva para importar gramáticas y reglas de plugins cargados.", allow_override=True)
    add_keyword("define", "#FF00FF", description="Declara una regla sintáctica con su nombre y código numérico único.", allow_override=True)
    add_keyword("Keyword", "#FF00FF", description="Bloque declarativo para registrar una nueva palabra clave reservada con sus atributos.", allow_override=True)
    add_keyword("description", "#02573F", group="KEYWORD_PROPERTIE", description="Propiedad de documentación textual para la palabra clave o regla.", allow_override=True)
    add_keyword("color", "#02573F", group="KEYWORD_PROPERTIE", description="Color hexadecimal (#RRGGBB) para resaltado de sintaxis en el editor.", allow_override=True)
    add_keyword("group", "#02573F", group="KEYWORD_PROPERTIE", description="Asigna la palabra clave a un grupo temático lógico (WordGroup).", allow_override=True)
    add_keyword("pass", "#F90000", description="Instrucción nula o vacía (no-op) en una regla sintáctica.", allow_override=True)

    # Combinadores principales
    add_keyword("Many",      "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de repetición: cero o más (*).", allow_override=True)
    add_keyword("Alt",       "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de alternativa: prueba múltiples ramas en orden.", allow_override=True)
    add_keyword("Some",      "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de repetición: una o más (+).", allow_override=True)
    add_keyword("Seq",       "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de secuencia: todos los elementos en orden.", allow_override=True)
    add_keyword("Opt",       "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador opcional: cero o uno (?).", allow_override=True)
    add_keyword("optional",  "#08D453", group="CLN_COMBINATOR_MAIN", description="Variante opcional de coincidencia.", allow_override=True)
    add_keyword("Separator", "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de secuencias delimitadas por separador.", allow_override=True)
    add_keyword("separator", "#08D453", group="CLN_COMBINATOR_MAIN", description="Variante del combinador de secuencias delimitadas.", allow_override=True)
    add_keyword("Tokenize",  "#08D453", group="CLN_COMBINATOR_MAIN", description="Combinador de tokenización de secuencias léxicas.", allow_override=True)
    add_keyword("tokenize",  "#08D453", group="CLN_COMBINATOR_MAIN", description="Variante del combinador de tokenización.", allow_override=True)
    add_keyword("New",       "#08D453", group="CLN_COMBINATOR_MAIN", description="Instanciación de nueva regla o estructura léxica.", allow_override=True)
    add_keyword("Item",      "#08D453", group="CLN_COMBINATOR_MAIN", description="Elemento unitario dentro de un combinador Separator.", allow_override=True)
    add_keyword("item",      "#08D453", group="CLN_COMBINATOR_MAIN", description="Variante en minúscula de Item.", allow_override=True)

    # Combinadores para expresiones hijas
    add_keyword("reference", "#08D453", group="CLN_SUBCOMBINATOR_NAME", description="Referencia por nombre o código a otra regla.", allow_override=True)
    add_keyword("tokens",    "#355044", group="COMBINATOR_MATCH", description="Coincidencia con un tipo de token específico (tokens.IDENT).", allow_override=True)
    add_keyword("words",     "#355044", group="COMBINATOR_MATCH", description="Coincidencia con una palabra o literal textual exacto.", allow_override=True)
    add_keyword("groups",    "#355044", group="COMBINATOR_MATCH", description="Coincidencia con cualquier palabra clave de un grupo.", allow_override=True)
    add_keyword("literal",   "#355044", group="COMBINATOR_MATCH", description="Coincidencia de valores literales constantes.", allow_override=True)
    add_keyword("seqsym",    "#355044", group="COMBINATOR_MATCH", description="Coincidencia de secuencia de símbolos o caracteres.", allow_override=True)
    add_keyword("regex",     "#355044", group="COMBINATOR_MATCH", description="Coincidencia de patrones léxicos por expresión regular.", allow_override=True)
    add_keyword("any",       "#355044", group="COMBINATOR_MATCH", description="Coincide con cualquier token individual.", allow_override=True)
    add_keyword("anygrammar","#355044", group="COMBINATOR_MATCH", description="Coincide con cualquier producción gramatical válida.", allow_override=True)

    # Argumentos de combinadores
    add_keyword("exclude",   "#20C7D6", group="COMBINATOR_ARG", description="Excluye tokens o patrones específicos.", allow_override=True)
    add_keyword("only",      "#20C7D6", group="COMBINATOR_ARG", description="Restringe la coincidencia exclusivamente a los elementos dados.", allow_override=True)
    add_keyword("sep",       "#20C7D6", group="COMBINATOR_ARG", description="Especifica el delimitador (ej. coma, punto y coma).", allow_override=True)
    add_keyword("join",      "#20C7D6", group="COMBINATOR_ARG", description="Une los tokens resultantes en una unidad semántica.", allow_override=True)
    add_keyword("symbols",   "#20C7D6", group="COMBINATOR_ARG", description="Lista de símbolos permitidos en la evaluación.", allow_override=True)
    add_keyword("name",      "#20C7D6", group="COMBINATOR_ARG", description="Nombre o alias asignado al elemento gramatical.", allow_override=True)
    add_keyword("values",    "#20C7D6", group="COMBINATOR_ARG", description="Lista de valores permitidos en el combinador.", allow_override=True)


# Auto-registro en importación
register_glang_keywords()

__all__ = [
    "register_glang_keywords",
]
