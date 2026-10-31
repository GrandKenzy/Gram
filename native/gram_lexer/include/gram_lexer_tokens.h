#ifndef GRAM_LEXER_TOKENS_H
#define GRAM_LEXER_TOKENS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRAM_LEXER_ABI_MAJOR 1
#define GRAM_LEXER_ABI_MINOR 1

/**
 * Built-in lexical token kinds matching gram.core.lexer.tokens.Token ordinals (0..84).
 * Custom session-registered symbols may use IDs >= GRAM_TOKEN_CUSTOM_BASE (1000).
 */
typedef enum {
    GRAM_TOKEN_EOF              = 0,
    GRAM_TOKEN_NEWLINE          = 1,
    GRAM_TOKEN_IDENT            = 2,
    GRAM_TOKEN_INDENT           = 3,
    GRAM_TOKEN_DEDENT           = 4,
    GRAM_TOKEN_COMMENT          = 5,
    GRAM_TOKEN_KEYWORD          = 6,
    GRAM_TOKEN_STRING           = 7,
    GRAM_TOKEN_NUMBER           = 8,
    GRAM_TOKEN_BOOL             = 9,
    GRAM_TOKEN_NULL             = 10,
    GRAM_TOKEN_PLUS             = 11,
    GRAM_TOKEN_MINUS            = 12,
    GRAM_TOKEN_STAR             = 13,
    GRAM_TOKEN_SLASH            = 14,
    GRAM_TOKEN_PERCENT          = 15,
    GRAM_TOKEN_POW              = 16,
    GRAM_TOKEN_FLOOR_DIV        = 17,
    GRAM_TOKEN_INCREMENT        = 18,
    GRAM_TOKEN_DECREMENT        = 19,
    GRAM_TOKEN_ASSIGN           = 20,
    GRAM_TOKEN_PLUS_ASSIGN      = 21,
    GRAM_TOKEN_MINUS_ASSIGN     = 22,
    GRAM_TOKEN_STAR_ASSIGN      = 23,
    GRAM_TOKEN_SLASH_ASSIGN     = 24,
    GRAM_TOKEN_PERCENT_ASSIGN   = 25,
    GRAM_TOKEN_POW_ASSIGN       = 26,
    GRAM_TOKEN_FLOOR_DIV_ASSIGN = 27,
    GRAM_TOKEN_AND_ASSIGN       = 28,
    GRAM_TOKEN_OR_ASSIGN        = 29,
    GRAM_TOKEN_XOR_ASSIGN       = 30,
    GRAM_TOKEN_SHL_ASSIGN       = 31,
    GRAM_TOKEN_SHR_ASSIGN       = 32,
    GRAM_TOKEN_WALRUS           = 33,
    GRAM_TOKEN_EQUAL            = 34,
    GRAM_TOKEN_NOT_EQUAL        = 35,
    GRAM_TOKEN_LESS             = 36,
    GRAM_TOKEN_GREATER          = 37,
    GRAM_TOKEN_LESS_EQUAL       = 38,
    GRAM_TOKEN_GREATER_EQUAL    = 39,
    GRAM_TOKEN_NOT              = 40,
    GRAM_TOKEN_NOT_LOGIC        = 41,
    GRAM_TOKEN_AND_LOGIC        = 42,
    GRAM_TOKEN_OR_LOGIC         = 43,
    GRAM_TOKEN_AND              = 44,
    GRAM_TOKEN_OR               = 45,
    GRAM_TOKEN_XOR              = 46,
    GRAM_TOKEN_SHL              = 47,
    GRAM_TOKEN_SHR              = 48,
    GRAM_TOKEN_LPAREN           = 49,
    GRAM_TOKEN_RPAREN           = 50,
    GRAM_TOKEN_LBRACKET         = 51,
    GRAM_TOKEN_RBRACKET         = 52,
    GRAM_TOKEN_LBRACE           = 53,
    GRAM_TOKEN_RBRACE           = 54,
    GRAM_TOKEN_COMMA            = 55,
    GRAM_TOKEN_DOT              = 56,
    GRAM_TOKEN_COLON            = 57,
    GRAM_TOKEN_SEMICOLON        = 58,
    GRAM_TOKEN_AT               = 59,
    GRAM_TOKEN_HASH             = 60,
    GRAM_TOKEN_DOLLAR           = 61,
    GRAM_TOKEN_QUESTION         = 62,
    GRAM_TOKEN_QUESTION_ASSIGN  = 63,
    GRAM_TOKEN_EXCLAMATION      = 64,
    GRAM_TOKEN_BACKSLASH        = 65,
    GRAM_TOKEN_UNDERSCORE       = 66,
    GRAM_TOKEN_ARROW            = 67,
    GRAM_TOKEN_FAT_ARROW        = 68,
    GRAM_TOKEN_LEFT_ARROW       = 69,
    GRAM_TOKEN_DOUBLE_ARROW     = 70,
    GRAM_TOKEN_LOGIC_AND        = 71,
    GRAM_TOKEN_LOGIC_OR         = 72,
    GRAM_TOKEN_LOGIC_NOT        = 73,
    GRAM_TOKEN_SQRT             = 74,
    GRAM_TOKEN_INFINITY         = 75,
    GRAM_TOKEN_DEGREE           = 76,
    GRAM_TOKEN_MIDDLE_DOT       = 77,
    GRAM_TOKEN_BULLET           = 78,
    GRAM_TOKEN_SECTION          = 79,
    GRAM_TOKEN_THREE_DOTS       = 80,
    GRAM_TOKEN_ERROR            = 81,
    GRAM_TOKEN_UNKNOWN          = 82,
    GRAM_TOKEN_EMPTY_LINE       = 83,
    GRAM_TOKEN_DECIMAL          = 84,
    GRAM_TOKEN_CUSTOM_BASE      = 1000
} GramTokenKind;

/**
 * Bitwise token metadata flags matching gram.core.lexer.flags.TokenFlags.
 */
typedef enum {
    GRAM_TOKEN_FLAG_NONE         = 0,
    GRAM_TOKEN_FLAG_SIMPLE_QUOTE = 1 << 0,
    GRAM_TOKEN_FLAG_CHAR         = 1 << 1,
    /* Internal/extended hint flags (masked out when projecting to Python TokenFlags) */
    GRAM_TOKEN_FLAG_HAS_ESCAPES  = 1 << 8,
    GRAM_TOKEN_FLAG_MULTILINE    = 1 << 9,
    GRAM_TOKEN_FLAG_BOOL_TRUE    = 1 << 10,
    GRAM_TOKEN_FLAG_NUMERIC_SUFF = 1 << 11,
    GRAM_TOKEN_FLAG_BLOCK_COMMENT = 1 << 12
} GramTokenFlags;

#define GRAM_TOKEN_PUBLIC_FLAGS_MASK 0x03u

/**
 * Return the canonical ASCII name of a built-in GramTokenKind (or "CUSTOM" / "UNKNOWN").
 */
const char *gram_token_kind_name(uint32_t kind);

#ifdef __cplusplus
}
#endif

#endif /* GRAM_LEXER_TOKENS_H */
