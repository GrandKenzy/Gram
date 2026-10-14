from pathlib import Path

from gram import *

config.LEXER_ADD_INFO = True
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True
config.LEXER_COMMENT_TOKEN = ';'
lexer.add_group('types')
lexer.add_keyword('int', group='types', color='#8BE9FD', description='Integer type', documentation='Signed 64-bit integer type.')
lexer.add_keyword('str', group='types', color='#F1FA8C', description='String type', documentation='UTF-8 encoded string.')

lexer.add_group('special_keywords')
lexer.add_keyword('return', group='special_keywords', color='#FF79C6', description='Return statement', documentation='Exits the current function and returns a value.')
lexer.add_keyword('block', group='special_keywords', color='#BD93F9', description='Block declaration', documentation='Declares an isolated module or namespace block.')
lexer.add_keyword('end', group='special_keywords', color='#BD93F9', description='End block', documentation='Closes a previously opened block.')
lexer.add_keyword('import', group='special_keywords', color='#FF79C6', description='Import module', documentation='Imports symbols from an external module.')


def get_gram_directories():
    """Inspect subdirectories and standard modules for import completion suggestions."""
    gram_dir = Path(__file__).resolve().parent / 'gram'
    modules = ['compiler', 'core', 'http', 'json', 'math', 'os', 'parser', 'sys', 'utilities', 'vsix']
    if gram_dir.exists() and gram_dir.is_dir():
        for p in gram_dir.iterdir():
            if p.is_dir() and not p.name.startswith(('.', '__')):
                if p.name not in modules:
                    modules.append(p.name)
    return sorted(modules)


class CALL_DECL(combinators.RuleItem):
    nodeable = True


class VALUE(combinators.RuleItem):
    grammar = combinators.Alt(
        combinators.DualExpr(
            lexer.Token.IDENT, lexer.Token.NUMBER, lexer.Token.STRING, combinators.Ref(CALL_DECL), lexer.Token.BOOL
        ),
        combinators.MatchToken('STRING'),
        combinators.MatchToken('IDENT'),
        combinators.MatchToken('NUMBER'),
        combinators.MatchToken('DOCSTRING'),
        combinators.Ref(CALL_DECL)
    )
    nodeable = True


class VAR_ASSIGN(combinators.RuleItem):
    grammar = combinators.Seq(
        combinators.MatchToken('ASSIGN'),
        combinators.Ref(VALUE)
    )


class VAR_DECL(combinators.RuleItem):
    colors = {
        'types': 'storage.type'
    }
    autocomplete = ['int', 'str']
    hints = '<type> <identifier> [= <value>]'
    grammar = combinators.Seq(
        combinators.MatchGroup('types'),
        combinators.MatchToken('IDENT'),
        combinators.Opt(combinators.Ref(VAR_ASSIGN))
    )
    nodeable = True


class ARG_PAIRS(combinators.RuleItem):
    grammar = combinators.Seq(
        combinators.MatchToken('IDENT'),
        combinators.MatchToken('COLON'),
        combinators.MatchGroup('types')
    )
    nodeable = True


class ARGUMENTS(combinators.RuleItem):
    grammar = combinators.Enclosed(
        open=lexer.Token.LPAREN,
        content=combinators.Separator(
            values=[combinators.Ref(ARG_PAIRS)],
            sep=lexer.Token.COMMA,
            allow_trailing=True
        ),
        close=lexer.Token.RPAREN
    )
    nodeable = True


class RETURN_DECL(combinators.RuleItem):
    nodeable = True
    colors = {
        'return': 'keyword.control.flow'
    }
    autocomplete = ['return']
    hints = 'return <expression>'
    grammar = combinators.Seq(
        combinators.MatchKeyword('return'),
        combinators.Ref(VALUE)
    )


class FUNC_BODY(combinators.RuleItem):
    nodeable = True
    grammar = combinators.Seq(
        combinators.MatchToken('INDENT'),
        combinators.Alt(
            combinators.Ref(RETURN_DECL),
            combinators.Ref(VAR_DECL)
        ),
        combinators.MatchToken('DEDENT')
    )


class FUNC_DECL(combinators.RuleItem):
    colors = {
        'types': 'storage.type'
    }
    hints = '<type> <name>(<args>):\n    <body>'
    grammar = combinators.Seq(
        combinators.MatchGroup('types'),
        combinators.MatchToken('IDENT'),
        combinators.Ref(ARGUMENTS),
        combinators.MatchToken('COLON'),
        combinators.Ref(FUNC_BODY)
    )
    nodeable = True


class BLOCK_BODY(combinators.RuleItem):
    nodeable = True
    grammar = combinators.Seq(
        combinators.MatchToken('INDENT'),
        combinators.Many(combinators.Ref(VAR_DECL)),
        combinators.MatchToken('DEDENT')
    )


class BLOCK_DECL(combinators.RuleItem):
    nodeable = True
    colors = {
        'block': 'keyword.control.block',
        'end': 'keyword.control.block'
    }
    autocomplete = ['block', 'end']
    hints = 'block <name>:\n    <statements>\nend <name>'
    grammar = combinators.Seq(
        combinators.MatchKeyword('block'),
        combinators.MatchToken('IDENT'),
        combinators.MatchToken('COLON'),
        combinators.Ref(BLOCK_BODY),
        combinators.MatchKeyword('end'),
        combinators.MatchToken('IDENT')
    )


class IMPORT_DECL(combinators.RuleItem):
    nodeable = True
    colors = {
        'import': 'keyword.control.import'
    }
    autocomplete = ['import']
    suggestions = get_gram_directories
    hints = 'import <module>'
    grammar = combinators.Seq(
        combinators.MatchKeyword('import'),
        combinators.MatchToken('IDENT')
    )


class PROGRAM(combinators.RuleItem):
    grammar = combinators.Alt(
        combinators.Ref(BLOCK_DECL),
        combinators.Ref(IMPORT_DECL),
        combinators.Ref(FUNC_DECL),
        combinators.Ref(VAR_DECL)
    )


class PARAMS(combinators.RuleItem):
    grammar = combinators.Enclosed(
        open=lexer.Token.LPAREN,
        close=lexer.Token.RPAREN,
        content=combinators.Separator(
            sep=lexer.Token.COMMA,
            values=[combinators.Ref(VALUE)]
        )
    )
    nodeable = True


CALL_DECL.grammar = combinators.Seq(
    combinators.MatchToken('IDENT'),
    combinators.Ref(PARAMS)
)

if __name__ == '__main__':
    source_path = Path('source.gram') if Path('source.gram').exists() else Path('source.txt')
    prev_exit = config.ERROR_EXIT_ON_ERROR
    config.ERROR_EXIT_ON_ERROR = False
    try:
        L = lexer.Lexer(source_path)
        R = L.process()
        P = parser.Parser(R)
        R = P.parse(PROGRAM)
        print('Parsed AST:', R)
        t = P.analyzer_ast_instance.raytracing.stringify()
        p = P.analyzer_ast_instance.raytracing.path_tracing()
        print(t)
        print(p)
    except BaseException as err:
        print('CLI compilation notice for', source_path, ':', err)
    finally:
        config.ERROR_EXIT_ON_ERROR = prev_exit

    # analyzer = vsix.VSIXAnalyzer(output='default')
    # data = analyzer.process(PROGRAM)

    # for d, t in data.items():
    #     print(d, ':', t)

    # vsix.declare_info(
    #     name='gram-language',
    #     display_name='Gram Language Official Support',
    #     description='Comprehensive language tooling and syntax support for Gram DSL.',
    #     version='0.2.0',
    #     publisher='gram-framework',
    #     author='Kentucky & Gram Community',
    #     license='MIT',
    #     repository='https://github.com/Kentucky/Gram',
    #     homepage='https://github.com/Kentucky/Gram#readme',
    #     language_id='gram',
    #     language_name='Gram',
    #     file_extensions=['.gram', '.g'],
    #     keywords=['gram', 'compiler', 'dsl', 'parser', 'vsix']
    # )

    # generator = vsix.VSIXGenerator(data)
    # extension_files = generator.export('./vscode_extension')

    # print('Generated VS Code extension files:')
    # for key, filepath in extension_files.items():
    #     print(key, '->', filepath)

    # status = vsix.up(generator)
    # print('VSIX Up status:')
    # print('Packaged VSIX file:', status['vsix_file'])
    # print('Installed extension ID:', status['install_info']['extension_id'])