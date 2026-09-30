"""
Catálogo Centralizado de Errores Formales del Framework Gram.
=============================================================
Define todos los objetos CodeError estructurados según el estándar formal OSGDC
de 5 dimensiones:
  [O] Origen (Origin): Procedencia del emisor (Native=1, Plugin=2, Unknown=0).
  [S] Alcance (Scope): Subsistema donde ocurrió el fallo (Lexer=1, Parser=2, Grammar=3, Semantic=4, Compilation=5).
  [G] Gravedad (Gravity): Impacto funcional (Minor=0, Implementation=1, Obsolete=2, Internal=3, Fatal=4).
  [D] Documentación (Documentation): Nivel de documentación (Documented=0, Documented & Traceable=1, Not Documented=2).
  [C] Condición (Condition): Usabilidad del resultado (Usable=0, Requires Repair=1, Should Repair=2).

Regla de Arquitectura:
----------------------
Ningún módulo de lógica debe instanciar códigos de error arbitrarios ni utilizar
números mágicos dispersos. Todos los componentes del framework Gram deben importar
y consumir exclusivamente los errores de este catálogo oficial.

Uso Típico:
-----------
>>> from gram.utilities.error import Error
>>> from gram import errors
>>> err = Error("Carácter no admitido", errors.LEXER_UNEXPECTED_CHARACTER, "Revise la sintaxis.")
>>> err.raise_error(exit=False)
"""
from __future__ import annotations

import sys

from gram.utilities import error

codes = error.codes.Codes
coderr = error.codes.CodeError

# Inicialización estricta del mapa de grupos y límites para el estándar OSGDC de 5 dígitos:
# O: max 2, S: max 5, G: max 4, D: max 2, C: max 2
error.codes.set_map_codes(
    origin=[2],
    scope=[5],
    gravity=[4],
    documentation=[2],
    condition=[2],
)

# ==============================================================================
# SÍMBOLO COMODÍN / POR DEFECTO
# ==============================================================================

UNKNOWN: error.codes.Codes = error.codes.Codes('unknown', 0, 'default')
"""Símbolo comodín por defecto para rellenar posiciones omitidas."""


# ==============================================================================
# DIMENSIONES DEL ESTÁNDAR OSGDC (GRUPOS Y LÍMITES)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. ORIGEN (O - Origin): Procedencia del componente emisor
# ------------------------------------------------------------------------------
UNKNOWN_ORIGIN: error.codes.Codes = codes('unknown', 0, 'origin')
"""Origen indeterminado o no rastreable (O = 0)."""

NATIVE_ERROR: error.codes.Codes = codes('native', 1, 'origin')
"""Error originado en el núcleo o componentes nativos de Gram (O = 1)."""

PLUGIN_ERROR: error.codes.Codes = codes('plugin', 2, 'origin')
"""Error originado dentro de un plugin o extensión externa (O = 2)."""


# ------------------------------------------------------------------------------
# 2. ALCANCE (S - Scope): Subsistema o fase del pipeline de procesamiento
# ------------------------------------------------------------------------------
UNKNOWN_SCOPE: error.codes.Codes = codes('unknown', 0, 'scope')
"""Alcance no especificado o genérico (S = 0)."""

LEXER_ERROR: error.codes.Codes = codes('lexer', 1, 'scope')
"""Fase léxica: escaneo de caracteres, palabras clave, números y strings (S = 1)."""

PARSER_ERROR: error.codes.Codes = codes('parser', 2, 'scope')
"""Fase de análisis sintáctico: tokens inesperados, fin prematuro (EOF) (S = 2)."""

GRAMMAR_ERROR: error.codes.Codes = codes('grammar', 3, 'scope')
"""Definición y evaluación de reglas, combinadores y nodos del AST (S = 3)."""

SEMANTIC_ERROR: error.codes.Codes = codes('semantic', 4, 'scope')
"""Fase de análisis semántico: compatibilidad de tipos, ámbito y símbolos (S = 4)."""

COMPILATION_ERROR: error.codes.Codes = codes('compilation', 5, 'scope')
"""Fase de compilación, inclusión de especificaciones y DSL GramLang (S = 5)."""


# ------------------------------------------------------------------------------
# 3. GRAVEDAD (G - Gravity): Impacto funcional en la ejecución
# ------------------------------------------------------------------------------
MINOR: error.codes.Codes = codes('minor', 0, 'gravity')
"""Advertencia o fallo menor que no interrumpe el análisis ni la ejecución (G = 0)."""

IMPLEMENTATION_ERROR: error.codes.Codes = codes('implementation error', 1, 'gravity')
"""Característica, combinador o funcionalidad aún no implementada (G = 1)."""

OBSOLETE_ERROR: error.codes.Codes = codes('obsolete error', 2, 'gravity')
"""Sintaxis, función o componente deprecado u obsoleto (G = 2)."""

INTERNAL: error.codes.Codes = codes('internal', 3, 'gravity')
"""Inconsistencia del estado interno del framework o motor de análisis (G = 3)."""

FATAL: error.codes.Codes = codes('fatal', 4, 'gravity')
"""Error crítico que aborta inmediatamente el análisis de la rama actual (G = 4)."""


# ------------------------------------------------------------------------------
# 4. DOCUMENTACIÓN (D - Documentation): Nivel de documentación y trazabilidad
# ------------------------------------------------------------------------------
DOCUMENTED: error.codes.Codes = codes('documented', 0, 'documentation')
"""Error formalmente catalogado con ficha descriptiva estándar (D = 0)."""

DOCUMENTED_AND_TRACEABLE: error.codes.Codes = codes('documented and traceable', 1, 'documentation')
"""Error formal con causas documentadas, traza completa y sugerencias de reparación (D = 1)."""

NOT_DOCUMENTED: error.codes.Codes = codes('not documented', 2, 'documentation')
"""Error ad-hoc sin documentación técnica oficial asignada (D = 2)."""


# ------------------------------------------------------------------------------
# 5. CONDICIÓN (C - Condition): Estado del artefacto resultante y reparabilidad
# ------------------------------------------------------------------------------
USABLE: error.codes.Codes = codes('usable', 0, 'condition')
"""El artefacto o token generado es operable y el análisis puede continuar (C = 0)."""

REQUIRES_REPAIR: error.codes.Codes = codes('requires repair', 1, 'condition')
"""El código fuente analizado contiene un defecto que debe ser reparado por el usuario (C = 1)."""

SHOULD_REPAIR: error.codes.Codes = codes('should repair', 2, 'condition')
"""Se recomienda encarecidamente reparar el código para evitar inconsistencias futuras (C = 2)."""


# ==============================================================================
# 1. ANALIZADOR LÉXICO (Scope: LEXER_ERROR = 1)
# ==============================================================================

EMPTY_KEYWORDS: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.EmptyKeywords',
)
"""
ES:
    Señalado cuando el analizador léxico se inicializa sin ninguna palabra clave registrada.
    Código OSGDC: S-11010 · Gram.Lexer.EmptyKeywords.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when the lexer is initialized without any registered keywords.
    OSGDC Code: S-11010 · Gram.Lexer.EmptyKeywords.
"""

KEYWORD_ALREADY_EXISTS: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.KeywordAlreadyExists',
)
"""
ES:
    Señalado al intentar registrar una palabra clave cuyo identificador ya existe en la tabla léxica.
    Código OSGDC: S-11010 · Gram.Lexer.KeywordAlreadyExists.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when attempting to register a keyword that is already registered in the lexer table.
    OSGDC Code: S-11010 · Gram.Lexer.KeywordAlreadyExists.
"""

KEYWORD_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.KeywordNotFound',
)
"""
ES:
    Señalado cuando se solicita una palabra clave que no se encuentra en el catálogo del lexer.
    Código OSGDC: S-11010 · Gram.Lexer.KeywordNotFound.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when a requested keyword is not found in the lexer catalog.
    OSGDC Code: S-11010 · Gram.Lexer.KeywordNotFound.
"""

GROUP_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.GroupNotFound',
)
"""
ES:
    Señalado cuando se hace referencia a un grupo léxico que no existe.
    Código OSGDC: S-11010 · Gram.Lexer.GroupNotFound.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when referring to a lexical group that does not exist.
    OSGDC Code: S-11010 · Gram.Lexer.GroupNotFound.
"""

KEYWORD_INVALID_NAME: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.InvalidKeywordName',
)
"""
ES:
    Señalado cuando un identificador de palabra clave no cumple con las reglas sintácticas requeridas.
    Código OSGDC: S-11010 · Gram.Lexer.InvalidKeywordName.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when a keyword identifier contains invalid characters or does not meet naming rules.
    OSGDC Code: S-11010 · Gram.Lexer.InvalidKeywordName.
"""

LEXER_UNEXPECTED_CHARACTER: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Lexer.UnexpectedCharacter',
)
"""
ES:
    Señalado cuando el lexer encuentra un carácter ilegal no reconocido por ningún visitor.
    Código OSGDC: S-11411 · Gram.Lexer.UnexpectedCharacter.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when the lexer encounters an unexpected character unsupported by any visitor.
    OSGDC Code: S-11411 · Gram.Lexer.UnexpectedCharacter.
"""

LEXER_UNCLOSED_STRING: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Lexer.UnclosedString',
)
"""
ES:
    Señalado cuando una cadena literal no se cierra antes del final de línea o de archivo.
    Código OSGDC: S-11411 · Gram.Lexer.UnclosedString.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a string literal is left unclosed before end-of-line or end-of-file.
    OSGDC Code: S-11411 · Gram.Lexer.UnclosedString.
"""

LEXER_INDENTATION_MISMATCH: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Lexer.IndentationMismatch',
)
"""
ES:
    Señalado cuando los niveles de indentación no coinciden con la pila de bloques léxicos.
    Código OSGDC: S-11411 · Gram.Lexer.IndentationMismatch.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when indentation levels do not match the expected indentation stack.
    OSGDC Code: S-11411 · Gram.Lexer.IndentationMismatch.
"""

LEXER_INVALID_NUMBER: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Lexer.InvalidNumber',
)
"""
ES:
    Señalado cuando un literal numérico está mal formado (múltiples puntos, prefijo erróneo, etc.).
    Código OSGDC: S-11411 · Gram.Lexer.InvalidNumber.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a numeric literal has an invalid format.
    OSGDC Code: S-11411 · Gram.Lexer.InvalidNumber.
"""

WORDGROUP_ALREADY_EXISTS: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.WordGroupAlreadyExists',
)
"""
ES:
    Señalado cuando se intenta registrar un grupo de palabras cuyo nombre ya se encuentra en uso.
    Código OSGDC: S-11010 · Gram.Lexer.WordGroupAlreadyExists.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when attempting to create a word group whose name is already taken.
    OSGDC Code: S-11010 · Gram.Lexer.WordGroupAlreadyExists.
"""

WORDGROUP_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.WordGroupNotFound',
)
"""
ES:
    Señalado cuando se intenta acceder o vincular a un grupo de palabras inexistente.
    Código OSGDC: S-11010 · Gram.Lexer.WordGroupNotFound.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when referring to a word group that does not exist in the lexer.
    OSGDC Code: S-11010 · Gram.Lexer.WordGroupNotFound.
"""

WORDGROUP_KEYWORD_NOT_REGISTERED: coderr = coderr(
    (
        NATIVE_ERROR,
        LEXER_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Lexer.KeywordNotRegistered',
)
"""
ES:
    Señalado cuando se intenta añadir a un grupo una palabra clave que aún no ha sido registrada.
    Código OSGDC: S-11010 · Gram.Lexer.KeywordNotRegistered.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when attempting to add an unregistered keyword to a word group.
    OSGDC Code: S-11010 · Gram.Lexer.KeywordNotRegistered.
"""


# ==============================================================================
# 2. MOTOR DEL PARSER (Scope: PARSER_ERROR = 2)
# ==============================================================================

PARSER_UNEXPECTED_TOKEN: coderr = coderr(
    (
        NATIVE_ERROR,
        PARSER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Parser.UnexpectedToken',
)
"""
ES:
    Señalado cuando el parser recibe un token que no satisface ninguna regla gramatical esperada.
    Código OSGDC: S-12411 · Gram.Parser.UnexpectedToken.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when the parser encounters a token that does not match any expected grammar rule.
    OSGDC Code: S-12411 · Gram.Parser.UnexpectedToken.
"""

PARSER_EARLY_EOF: coderr = coderr(
    (
        NATIVE_ERROR,
        PARSER_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Parser.EarlyEOF',
)
"""
ES:
    Señalado cuando el flujo de tokens finaliza (EOF) prematuramente antes de completar una regla obligatoria.
    Código OSGDC: S-12411 · Gram.Parser.EarlyEOF.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when token stream unexpectedly reaches EOF while evaluating a mandatory rule.
    OSGDC Code: S-12411 · Gram.Parser.EarlyEOF.
"""

PARSER_NOT_STARTED: coderr = coderr(
    (
        NATIVE_ERROR,
        PARSER_ERROR,
        INTERNAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Parser.NotStarted',
)
"""
ES:
    Señalado cuando se intentan consumir o consultar tokens en un parser no inicializado.
    Código OSGDC: S-12311 · Gram.Parser.NotStarted.
    Gravedad: Interno (INTERNAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to consume tokens on an unstarted or uninitialized parser.
    OSGDC Code: S-12311 · Gram.Parser.NotStarted.
"""


# ==============================================================================
# 3. REGLAS Y COMBINADORES (Scope: GRAMMAR_ERROR = 3)
# ==============================================================================

ANY_NOT_IMPLEMENTED: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        IMPLEMENTATION_ERROR,
        DOCUMENTED,
        SHOULD_REPAIR,
    ),
    'Gram.Combinator.NotImplemented',
)
"""
ES:
    Señalado al invocar el combinador Any o características experimentales no disponibles aún.
    Código OSGDC: S-13102 · Gram.Combinator.NotImplemented.
    Gravedad: Implementación (IMPLEMENTATION_ERROR). Condición: Se sugiere reparar (SHOULD_REPAIR).
EN:
    Raised when using the Any combinator or features not yet implemented in the current version.
    OSGDC Code: S-13102 · Gram.Combinator.NotImplemented.
"""

COMBINATOR_FAILED: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Combinator.Failed',
)
"""
ES:
    Señalado ante un fallo recuperable o menor de coincidencia en la ejecución de un combinador.
    Código OSGDC: S-13010 · Gram.Combinator.Failed.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised on a non-fatal recoverable failure during combinator matching.
    OSGDC Code: S-13010 · Gram.Combinator.Failed.
"""

TOKENIZE_EMPTY_COMBINATORS: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Combinator.TokenizeEmpty',
)
"""
ES:
    Señalado cuando se instancia un combinador Tokenize sin proporcionar combinadores secundarios.
    Código OSGDC: S-13411 · Gram.Combinator.TokenizeEmpty.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a Tokenize combinator is instantiated without child combinators.
    OSGDC Code: S-13411 · Gram.Combinator.TokenizeEmpty.
"""

RULE_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Grammar.RuleNotFound',
)
"""
ES:
    Señalado cuando una referencia a regla (Ref) no puede ser resuelta en la gramática activa.
    Código OSGDC: S-13411 · Gram.Grammar.RuleNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a grammar rule reference cannot be resolved in the active grammar.
    OSGDC Code: S-13411 · Gram.Grammar.RuleNotFound.
"""

DUPLICATE_RULE: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Grammar.DuplicateRule',
)
"""
ES:
    Señalado al intentar registrar una regla con un ID o nombre que ya se encuentra registrado.
    Código OSGDC: S-13411 · Gram.Grammar.DuplicateRule.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when registering a grammar rule whose ID or name is already defined.
    OSGDC Code: S-13411 · Gram.Grammar.DuplicateRule.
"""

RULE_PROTECTED_ID: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Grammar.ProtectedRuleId',
)
"""
ES:
    Señalado al intentar sobrescribir o modificar un ID de regla protegido reservado del núcleo (0-20).
    Código OSGDC: S-13411 · Gram.Grammar.ProtectedRuleId.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to override a protected core rule ID (0-20).
    OSGDC Code: S-13411 · Gram.Grammar.ProtectedRuleId.
"""

PROGRAM_RULE_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.AST.ProgramRuleNotFound',
)
"""
ES:
    Señalado cuando la regla raíz PROGRAM no existe en la gramática al construir el AST.
    Código OSGDC: S-13411 · Gram.AST.ProgramRuleNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when the root PROGRAM rule is missing from the grammar when building the AST.
    OSGDC Code: S-13411 · Gram.AST.ProgramRuleNotFound.
"""

PROGRAM_INVALID_COMBINATOR: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.AST.ProgramInvalidCombinator',
)
"""
ES:
    Señalado cuando la regla PROGRAM utiliza un combinador incompatible con la construcción del AST.
    Código OSGDC: S-13010 · Gram.AST.ProgramInvalidCombinator.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when the PROGRAM rule has an invalid combinator for AST generation.
    OSGDC Code: S-13010 · Gram.AST.ProgramInvalidCombinator.
"""

DECLARATION_RULE_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclarationRuleNotFound',
)
"""
ES:
    Señalado cuando la regla DECLARATION no se encuentra en el catálogo gramatical del AST.
    Código OSGDC: S-13411 · Gram.AST.DeclarationRuleNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when the DECLARATION rule is not found in the AST grammar catalog.
    OSGDC Code: S-13411 · Gram.AST.DeclarationRuleNotFound.
"""

DECLARATOR_INVALID_TYPE: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclaratorInvalidType',
)
"""
ES:
    Señalado cuando un declarador del AST recibe o evalúa un tipo no soportado.
    Código OSGDC: S-13411 · Gram.AST.DeclaratorInvalidType.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an AST declarator has an invalid or unsupported type.
    OSGDC Code: S-13411 · Gram.AST.DeclaratorInvalidType.
"""

DECLARATOR_INVALID_ELEMENT: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclaratorInvalidElement',
)
"""
ES:
    Señalado cuando un declarador del AST contiene un elemento hijo incompatible o corrupto.
    Código OSGDC: S-13411 · Gram.AST.DeclaratorInvalidElement.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an AST declarator contains an invalid child element.
    OSGDC Code: S-13411 · Gram.AST.DeclaratorInvalidElement.
"""

COMBINATOR_UNSUPPORTED: coderr = coderr(
    (
        NATIVE_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Combinator.Unsupported',
)
"""
ES:
    Señalado cuando se invoca una operación combinatoria no admitida por la gramática en ejecución.
    Código OSGDC: S-13411 · Gram.Combinator.Unsupported.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an unsupported combinator operation is invoked during execution.
    OSGDC Code: S-13411 · Gram.Combinator.Unsupported.
"""


# ==============================================================================
# 4. ANÁLISIS SEMÁNTICO (Scope: SEMANTIC_ERROR = 4)
# ==============================================================================

SEMANTIC_TYPE_MISMATCH: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.TypeMismatch',
)
"""
ES:
    Señalado cuando existe una discrepancia o incompatibilidad de tipos en expresiones o asignaciones.
    Código OSGDC: S-14411 · Gram.Semantic.TypeMismatch.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when there is an incompatible type mismatch in expressions or assignments.
    OSGDC Code: S-14411 · Gram.Semantic.TypeMismatch.
"""

SEMANTIC_UNDEFINED_SYMBOL: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.UndefinedSymbol',
)
"""
ES:
    Señalado al hacer referencia a un identificador, símbolo o regla que no ha sido declarado.
    Código OSGDC: S-14411 · Gram.Semantic.UndefinedSymbol.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when referencing an undefined variable, rule, or symbol in the current scope.
    OSGDC Code: S-14411 · Gram.Semantic.UndefinedSymbol.
"""

SEMANTIC_DUPLICATE_SYMBOL: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.DuplicateSymbol',
)
"""
ES:
    Señalado al intentar redeclarar un símbolo o identificador ya existente en el mismo ámbito léxico.
    Código OSGDC: S-14411 · Gram.Semantic.DuplicateSymbol.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when redeclaring a symbol or identifier within the same lexical scope.
    OSGDC Code: S-14411 · Gram.Semantic.DuplicateSymbol.
"""

SEMANTIC_INVALID_OPERATION: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.InvalidOperation',
)
"""
ES:
    Señalado al intentar ejecutar una operación incompatible entre tipos de datos no admitidos.
    Código OSGDC: S-14411 · Gram.Semantic.InvalidOperation.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting an operation not supported by operand types.
    OSGDC Code: S-14411 · Gram.Semantic.InvalidOperation.
"""

SEMANTIC_SCOPE_VIOLATION: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.ScopeViolation',
)
"""
ES:
    Señalado cuando se intenta acceder o capturar un símbolo fuera de su ámbito de visibilidad permitido.
    Código OSGDC: S-14411 · Gram.Semantic.ScopeViolation.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to access a symbol outside its legal scope boundaries.
    OSGDC Code: S-14411 · Gram.Semantic.ScopeViolation.
"""

SEMANTIC_IMMUTABILITY_VIOLATION: coderr = coderr(
    (
        NATIVE_ERROR,
        SEMANTIC_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Semantic.ImmutabilityViolation',
)
"""
ES:
    Señalado al intentar mutar, reasignar o modificar una constante o símbolo semánticamente inmutable.
    Código OSGDC: S-14411 · Gram.Semantic.ImmutabilityViolation.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to reassign or mutate an immutable semantic symbol.
    OSGDC Code: S-14411 · Gram.Semantic.ImmutabilityViolation.
"""


# ==============================================================================
# 5. DSL Y COMPILACIÓN (Scope: COMPILATION_ERROR = 5)
# ==============================================================================

DSL_SYNTAX_ERROR: coderr = coderr(
    (
        NATIVE_ERROR,
        COMPILATION_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.DSL.SyntaxError',
)
"""
ES:
    Señalado ante discrepancias sintácticas en la especificación del DSL GramLang.
    Código OSGDC: S-15411 · Gram.DSL.SyntaxError.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised on syntax errors while parsing GramLang DSL specifications.
    OSGDC Code: S-15411 · Gram.DSL.SyntaxError.
"""

DSL_INCLUDE_NOT_FOUND: coderr = coderr(
    (
        NATIVE_ERROR,
        COMPILATION_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.DSL.IncludeNotFound',
)
"""
ES:
    Señalado cuando un archivo o módulo incluido mediante directiva `include` no puede ser localizado.
    Código OSGDC: S-15411 · Gram.DSL.IncludeNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an include file or module path specified in GramLang cannot be found.
    OSGDC Code: S-15411 · Gram.DSL.IncludeNotFound.
"""

GLANG_INCLUDE_PLUGIN_NOT_LOADED: coderr = coderr(
    (
        NATIVE_ERROR,
        COMPILATION_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.DSL.IncludePluginNotLoaded',
)
"""
ES:
    Señalado al intentar incluir reglas o símbolos de un plugin que no ha sido cargado en el entorno.
    Código OSGDC: S-15411 · Gram.DSL.IncludePluginNotLoaded.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to include rules from a plugin not loaded in the active environment.
    OSGDC Code: S-15411 · Gram.DSL.IncludePluginNotLoaded.
"""

GLANG_IMMUTABILITY_VIOLATION: coderr = coderr(
    (
        NATIVE_ERROR,
        COMPILATION_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.DSL.ImmutabilityViolation',
)
"""
ES:
    Señalado al intentar sobrescribir o alterar una definición de lenguaje inmutable durante la compilación.
    Código OSGDC: S-15411 · Gram.DSL.ImmutabilityViolation.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to mutate an immutable DSL definition during compilation.
    OSGDC Code: S-15411 · Gram.DSL.ImmutabilityViolation.
"""


# ==============================================================================
# 6. PLUGINS Y MANIFIESTOS (Origin: PLUGIN_ERROR = 2, Scope: GRAMMAR_ERROR = 3)
# ==============================================================================

PLUGIN_MANIFEST_NOT_FOUND: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ManifestNotFound',
)
"""
ES:
    Señalado cuando el archivo manifest.json requerido no existe en la raíz del directorio del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.ManifestNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when manifest.json is missing in the plugin root folder.
    OSGDC Code: S-23411 · Gram.Plugin.ManifestNotFound.
"""

PLUGIN_MANIFEST_INVALID: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ManifestInvalid',
)
"""
ES:
    Señalado cuando el manifiesto de un plugin contiene JSON corrupto o campos obligatorios faltantes.
    Código OSGDC: S-23411 · Gram.Plugin.ManifestInvalid.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a plugin manifest contains invalid JSON or lacks required fields.
    OSGDC Code: S-23411 · Gram.Plugin.ManifestInvalid.
"""

PLUGIN_FOLDER_MISMATCH: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.FolderMismatch',
)
"""
ES:
    Señalado cuando el nombre de la carpeta contenedora no coincide con el identificador `name` del manifiesto.
    Código OSGDC: S-23411 · Gram.Plugin.FolderMismatch.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when plugin folder name does not match the manifest name field.
    OSGDC Code: S-23411 · Gram.Plugin.FolderMismatch.
"""

PLUGIN_INCOMPATIBLE_GRAM_VERSION: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.IncompatibleGramVersion',
)
"""
ES:
    Señalado cuando la versión instalada de Gram no cumple la restricción `gram_version` del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.IncompatibleGramVersion.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when current Gram version does not meet plugin gram_version requirement.
    OSGDC Code: S-23411 · Gram.Plugin.IncompatibleGramVersion.
"""

PLUGIN_VENV_DISALLOWED: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.VenvDisallowed',
)
"""
ES:
    Señalado al intentar instalar dependencias de un plugin en un intérprete global sin un entorno virtual activo.
    Código OSGDC: S-23411 · Gram.Plugin.VenvDisallowed.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to install plugin dependencies without an active virtual environment.
    OSGDC Code: S-23411 · Gram.Plugin.VenvDisallowed.
"""

PLUGIN_DEPENDENCY_NOT_FOUND: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DependencyNotFound',
)
"""
ES:
    Señalado cuando una dependencia externa declarada por el plugin no está instalada en el entorno.
    Código OSGDC: S-23411 · Gram.Plugin.DependencyNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a required plugin dependency cannot be found in the active environment.
    OSGDC Code: S-23411 · Gram.Plugin.DependencyNotFound.
"""

PLUGIN_DEPENDENCY_VERSION_MISMATCH: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DependencyVersionMismatch',
)
"""
ES:
    Señalado cuando la versión instalada de una dependencia no satisface los requisitos de versión del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.DependencyVersionMismatch.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when installed dependency version fails to satisfy plugin version constraints.
    OSGDC Code: S-23411 · Gram.Plugin.DependencyVersionMismatch.
"""

PLUGIN_CAPABILITY_MISSING: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.CapabilityMissing',
)
"""
ES:
    Señalado cuando un plugin intenta ejecutar una operación sin declarar la capacidad requerida en su manifiesto.
    Código OSGDC: S-23411 · Gram.Plugin.CapabilityMissing.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a plugin attempts an action without declaring the required capability.
    OSGDC Code: S-23411 · Gram.Plugin.CapabilityMissing.
"""

PLUGIN_MAIN_NOT_FOUND: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.MainNotFound',
)
"""
ES:
    Señalado cuando el archivo de entrada principal (main.py) declarado en el manifiesto no existe.
    Código OSGDC: S-23411 · Gram.Plugin.MainNotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when main entrypoint file specified in plugin manifest cannot be found.
    OSGDC Code: S-23411 · Gram.Plugin.MainNotFound.
"""

PLUGIN_LOADED_ERROR: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.LoadedError',
)
"""
ES:
    Señalado ante una excepción no controlada ocurrida durante la carga e importación del módulo del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.LoadedError.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an unexpected error occurs while loading or importing the plugin module.
    OSGDC Code: S-23411 · Gram.Plugin.LoadedError.
"""

PLUGIN_PROCESSED_ERROR: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ProcessedError',
)
"""
ES:
    Señalado ante una falla durante el ciclo de procesamiento o registro de reglas del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.ProcessedError.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when an error occurs during the rule processing cycle of a plugin.
    OSGDC Code: S-23411 · Gram.Plugin.ProcessedError.
"""

PLUGIN_CONFIG_MUTATION_DENIED: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ConfigMutationDenied',
)
"""
ES:
    Señalado cuando un plugin intenta modificar atributos de configuración protegidos de Gram.
    Código OSGDC: S-23411 · Gram.Plugin.ConfigMutationDenied.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a plugin attempts to mutate protected Gram framework configuration.
    OSGDC Code: S-23411 · Gram.Plugin.ConfigMutationDenied.
"""

PLUGIN_CONFIG_REQUIREMENT_FAILED: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ConfigRequirementFailed',
)
"""
ES:
    Señalado cuando la configuración del entorno actual no cumple con las exigencias del plugin.
    Código OSGDC: S-23411 · Gram.Plugin.ConfigRequirementFailed.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when global environment configuration fails to meet plugin required_config constraints.
    OSGDC Code: S-23411 · Gram.Plugin.ConfigRequirementFailed.
"""

PLUGIN_DUPLICATE_FOUND: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        MINOR,
        DOCUMENTED_AND_TRACEABLE,
        USABLE,
    ),
    'Gram.Plugin.DuplicateFound',
)
"""
ES:
    Señalado cuando se detecta un plugin duplicado; la instancia repetida es descartada o ignorada.
    Código OSGDC: S-23010 · Gram.Plugin.DuplicateFound.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Raised when a duplicate plugin is detected during discovery.
    OSGDC Code: S-23010 · Gram.Plugin.DuplicateFound.
"""

PLUGIN_VERSION_MISMATCH_USE_INSTALL: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.VersionMismatchUseInstall',
)
"""
ES:
    Señalado ante incompatibilidad de versión que requiere una reinstalación explícita mediante CLI.
    Código OSGDC: S-23411 · Gram.Plugin.VersionMismatchUseInstall.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised on plugin version mismatch requiring explicit re-installation through the CLI.
    OSGDC Code: S-23411 · Gram.Plugin.VersionMismatchUseInstall.
"""

PLUGIN_PROTECTED_VIOLATION: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ProtectedViolation',
)
"""
ES:
    Señalado al intentar sobrescribir o alterar un plugin marcado como esencial o protegido del sistema.
    Código OSGDC: S-23411 · Gram.Plugin.ProtectedViolation.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when attempting to override or modify a protected system plugin.
    OSGDC Code: S-23411 · Gram.Plugin.ProtectedViolation.
"""

PLUGIN_SYNTAX_ERROR: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.SyntaxError',
)
"""
ES:
    Señalado cuando el código fuente de una regla o combinador del plugin contiene un error de sintaxis.
    Código OSGDC: S-23411 · Gram.Plugin.SyntaxError.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when code inside a plugin contains syntax errors.
    OSGDC Code: S-23411 · Gram.Plugin.SyntaxError.
"""

PLUGIN_DUPLICATE_DEPENDENCY: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DuplicateDependency',
)
"""
ES:
    Señalado cuando un plugin declara dependencias duplicadas o conflictivas en su manifiesto.
    Código OSGDC: S-23411 · Gram.Plugin.DuplicateDependency.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when duplicate or conflicting dependencies are declared in plugin manifest.
    OSGDC Code: S-23411 · Gram.Plugin.DuplicateDependency.
"""

PLUGIN_REQUIREMENT_FILE_MISSING: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.RequirementFileMissing',
)
"""
ES:
    Señalado cuando el archivo `requirements.txt` especificado en el manifiesto no existe.
    Código OSGDC: S-23411 · Gram.Plugin.RequirementFileMissing.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when the requirements.txt file declared in the manifest is missing.
    OSGDC Code: S-23411 · Gram.Plugin.RequirementFileMissing.
"""

PLUGIN_VALIDATION_FAILED: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ValidationFailed',
)
"""
ES:
    Señalado cuando la verificación de integridad estructural o de seguridad del plugin falla.
    Código OSGDC: S-23411 · Gram.Plugin.ValidationFailed.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when plugin validation checks fail.
    OSGDC Code: S-23411 · Gram.Plugin.ValidationFailed.
"""

PLUGIN_NOT_FOUND: coderr = coderr(
    (
        PLUGIN_ERROR,
        GRAMMAR_ERROR,
        FATAL,
        DOCUMENTED_AND_TRACEABLE,
        REQUIRES_REPAIR,
    ),
    'Gram.Plugin.NotFound',
)
"""
ES:
    Señalado cuando se solicita un plugin que no se encuentra instalado ni registrado en las rutas activas.
    Código OSGDC: S-23411 · Gram.Plugin.NotFound.
    Gravedad: Fatal (FATAL). Condición: Requiere Reparación (REQUIRES_REPAIR).
EN:
    Raised when a requested plugin cannot be found in search paths.
    OSGDC Code: S-23411 · Gram.Plugin.NotFound.
"""


# ==============================================================================
# 7. ERRORES DE SISTEMA / GENÉRICOS (Scope: UNKNOWN_SCOPE = 0)
# ==============================================================================

UNKNOWN_ERROR: coderr = coderr(
    (
        UNKNOWN_ORIGIN,
        UNKNOWN_SCOPE,
        MINOR,
        NOT_DOCUMENTED,
        USABLE,
    ),
    'Gram.System.UnknownError',
)
"""
ES:
    Error genérico para fallos no clasificados o excepciones que carecen de especificación formal.
    Código OSGDC: S-00020 · Gram.System.UnknownError.
    Gravedad: Menor (MINOR). Condición: Operable (USABLE).
EN:
    Generic fallback error for unclassified failures lacking formal specification.
    OSGDC Code: S-00020 · Gram.System.UnknownError.
"""


# ==============================================================================
# FUNCIONES DE CONSULTA Y CATÁLOGO
# ==============================================================================

def all_errors() -> list[coderr]:
    """
    ES:
        Retorna la lista de todos los objetos CodeError definidos en el catálogo oficial.
        Garantiza unicidad de instancias en la lista resultante.

    EN:
        Returns a list of all CodeError instances defined in the official catalog.
        Guarantees instance uniqueness in the resulting list.

    Returns:
        list[coderr]: Lista con todas las instancias de CodeError registradas.
    """
    current_module = sys.modules[__name__]
    seen_ids: set[int] = set()
    result: list[coderr] = []
    for item in current_module.__dict__.values():
        if isinstance(item, coderr):
            if id(item) not in seen_ids:
                seen_ids.add(id(item))
                result.append(item)
    return result


def get_error_by_code(code: int | tuple[int | str, ...] | str | coderr) -> coderr | None:
    """
    ES:
        Busca un error en el catálogo oficial según su código numérico, tupla OSGDC o cadena.

        Formatos aceptados:
            - Entero: 11010, 11411, 23411
            - Tupla: (1, 1, 0, 1, 0) o ('1', '1', '0', '1', '0')
            - Cadena: "11010", "S-11010", "S-11010 · Gram.Lexer.EmptyKeywords"
            - Instancia: Otra instancia de CodeError

    EN:
        Looks up an error in the official catalog by its numeric code, OSGDC tuple, or string.

        Supported formats:
            - Integer: 11010, 11411, 23411
            - Tuple: (1, 1, 0, 1, 0) or ('1', '1', '0', '1', '0')
            - String: "11010", "S-11010", "S-11010 · Gram.Lexer.EmptyKeywords"
            - Instance: Another CodeError instance

    Args:
        code: Identificador en cualquiera de los formatos soportados.

    Returns:
        coderr | None: Instancia de CodeError correspondiente, o None si no existe.
    """
    if isinstance(code, coderr):
        for err in all_errors():
            if err == code:
                return err
        return None

    target_digits: str | None = None

    if isinstance(code, int):
        target_digits = f"{code:05d}"
    elif isinstance(code, tuple):
        target_digits = "".join(str(item) for item in code)
    elif isinstance(code, str):
        clean: str = code.strip()
        if '-' in clean:
            after_dash: str = clean.split('-', 1)[1].strip()
            target_digits = after_dash.split()[0].split('·')[0].strip()
        else:
            target_digits = clean.split()[0].split('·')[0].strip()

    if target_digits is not None:
        for err in all_errors():
            if err.code_string == target_digits:
                return err

    return None


def get_error_by_name(name: str) -> coderr | None:
    """
    ES:
        Busca un error en el catálogo por su nombre canónico cualificado.
        Soporta búsqueda exacta y búsqueda insensible a mayúsculas/minúsculas.

    EN:
        Searches the catalog for an error by its canonical qualified name.
        Supports exact match and case-insensitive fallback.

    Args:
        name: Nombre del error (ej. 'Gram.Lexer.EmptyKeywords' o 'EmptyKeywords').

    Returns:
        coderr | None: Instancia de CodeError correspondiente, o None si no existe.
    """
    name_clean: str = name.strip()
    name_lower: str = name_clean.lower()

    for err in all_errors():
        if err.name == name_clean:
            return err

    for err in all_errors():
        if err.name.lower() == name_lower or err.name.lower().endswith(f".{name_lower}"):
            return err

    return None


def get_errors_by_scope(scope: error.codes.Codes | str | int) -> list[coderr]:
    """
    ES:
        Filtra y retorna todos los errores pertenecientes a un alcance (scope) específico.

    EN:
        Filters and returns all errors belonging to a specific scope.

    Args:
        scope: Código del scope (ej. LEXER_ERROR), nombre ('lexer') o valor numérico (1).

    Returns:
        list[coderr]: Lista de errores que pertenecen al ámbito solicitado.
    """
    target_val: str
    if isinstance(scope, error.codes.Codes):
        target_val = scope.value_str
    elif isinstance(scope, int):
        target_val = str(scope)
    elif isinstance(scope, str):
        scope_map = {
            'unknown': '0',
            'lexer': '1',
            'parser': '2',
            'grammar': '3',
            'semantic': '4',
            'compilation': '5',
        }
        target_val = scope_map.get(scope.lower(), scope)
    else:
        return []

    result: list[coderr] = []
    for err in all_errors():
        if len(err.code_string) >= 2 and err.code_string[1] == target_val:
            result.append(err)
    return result


def get_errors_by_origin(origin: error.codes.Codes | str | int) -> list[coderr]:
    """
    ES:
        Filtra y retorna todos los errores pertenecientes a un origen específico (Native o Plugin).

    EN:
        Filters and returns all errors belonging to a specific origin (Native or Plugin).

    Args:
        origin: Código de origen (ej. NATIVE_ERROR), nombre ('native') o valor numérico (1).

    Returns:
        list[coderr]: Lista de errores asociados a la procedencia solicitada.
    """
    target_val: str
    if isinstance(origin, error.codes.Codes):
        target_val = origin.value_str
    elif isinstance(origin, int):
        target_val = str(origin)
    elif isinstance(origin, str):
        origin_map = {
            'unknown': '0',
            'native': '1',
            'plugin': '2',
        }
        target_val = origin_map.get(origin.lower(), origin)
    else:
        return []

    result: list[coderr] = []
    for err in all_errors():
        if len(err.code_string) >= 1 and err.code_string[0] == target_val:
            result.append(err)
    return result


__all__ = [
    # Códigos Base: Origen
    'UNKNOWN_ORIGIN',
    'NATIVE_ERROR',
    'PLUGIN_ERROR',
    # Códigos Base: Alcance (Scope)
    'UNKNOWN_SCOPE',
    'LEXER_ERROR',
    'PARSER_ERROR',
    'GRAMMAR_ERROR',
    'SEMANTIC_ERROR',
    'COMPILATION_ERROR',
    # Códigos Base: Gravedad (Gravity)
    'MINOR',
    'IMPLEMENTATION_ERROR',
    'OBSOLETE_ERROR',
    'INTERNAL',
    'FATAL',
    # Códigos Base: Documentación
    'DOCUMENTED',
    'DOCUMENTED_AND_TRACEABLE',
    'NOT_DOCUMENTED',
    # Códigos Base: Condición
    'USABLE',
    'REQUIRES_REPAIR',
    'SHOULD_REPAIR',
    # Catálogo: Analizador Léxico (Scope: 1)
    'EMPTY_KEYWORDS',
    'KEYWORD_ALREADY_EXISTS',
    'KEYWORD_NOT_FOUND',
    'GROUP_NOT_FOUND',
    'KEYWORD_INVALID_NAME',
    'LEXER_UNEXPECTED_CHARACTER',
    'LEXER_UNCLOSED_STRING',
    'LEXER_INDENTATION_MISMATCH',
    'LEXER_INVALID_NUMBER',
    'WORDGROUP_ALREADY_EXISTS',
    'WORDGROUP_NOT_FOUND',
    'WORDGROUP_KEYWORD_NOT_REGISTERED',
    # Catálogo: Motor del Parser (Scope: 2)
    'PARSER_UNEXPECTED_TOKEN',
    'PARSER_EARLY_EOF',
    'PARSER_NOT_STARTED',
    # Catálogo: Reglas, Combinadores y AST (Scope: 3)
    'ANY_NOT_IMPLEMENTED',
    'COMBINATOR_FAILED',
    'TOKENIZE_EMPTY_COMBINATORS',
    'RULE_NOT_FOUND',
    'DUPLICATE_RULE',
    'RULE_PROTECTED_ID',
    'PROGRAM_RULE_NOT_FOUND',
    'PROGRAM_INVALID_COMBINATOR',
    'DECLARATION_RULE_NOT_FOUND',
    'DECLARATOR_INVALID_TYPE',
    'DECLARATOR_INVALID_ELEMENT',
    'COMBINATOR_UNSUPPORTED',
    # Catálogo: Análisis Semántico (Scope: 4)
    'SEMANTIC_TYPE_MISMATCH',
    'SEMANTIC_UNDEFINED_SYMBOL',
    'SEMANTIC_DUPLICATE_SYMBOL',
    'SEMANTIC_INVALID_OPERATION',
    'SEMANTIC_SCOPE_VIOLATION',
    'SEMANTIC_IMMUTABILITY_VIOLATION',
    # Catálogo: DSL y Compilación (Scope: 5)
    'DSL_SYNTAX_ERROR',
    'DSL_INCLUDE_NOT_FOUND',
    'GLANG_INCLUDE_PLUGIN_NOT_LOADED',
    'GLANG_IMMUTABILITY_VIOLATION',
    # Catálogo: Plugins y Manifiestos (Scope: 3, Origin: 2)
    'PLUGIN_MANIFEST_NOT_FOUND',
    'PLUGIN_MANIFEST_INVALID',
    'PLUGIN_FOLDER_MISMATCH',
    'PLUGIN_INCOMPATIBLE_GRAM_VERSION',
    'PLUGIN_VENV_DISALLOWED',
    'PLUGIN_DEPENDENCY_NOT_FOUND',
    'PLUGIN_DEPENDENCY_VERSION_MISMATCH',
    'PLUGIN_CAPABILITY_MISSING',
    'PLUGIN_MAIN_NOT_FOUND',
    'PLUGIN_LOADED_ERROR',
    'PLUGIN_PROCESSED_ERROR',
    'PLUGIN_CONFIG_MUTATION_DENIED',
    'PLUGIN_CONFIG_REQUIREMENT_FAILED',
    'PLUGIN_DUPLICATE_FOUND',
    'PLUGIN_VERSION_MISMATCH_USE_INSTALL',
    'PLUGIN_PROTECTED_VIOLATION',
    'PLUGIN_SYNTAX_ERROR',
    'PLUGIN_DUPLICATE_DEPENDENCY',
    'PLUGIN_REQUIREMENT_FILE_MISSING',
    'PLUGIN_VALIDATION_FAILED',
    'PLUGIN_NOT_FOUND',
    # Catálogo: Errores de Sistema
    'UNKNOWN_ERROR',
    # Funciones de Consulta y Utilidad
    'all_errors',
    'get_error_by_code',
    'get_error_by_name',
    'get_errors_by_scope',
    'get_errors_by_origin',
]
