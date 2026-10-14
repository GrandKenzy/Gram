from gram import combinators as cmb
from gram import config, lexer, parser

lexer.words.add_group('types')

lexer.words.add_keyword('int', 'types')
lexer.words.add_keyword('str', 'types')
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True

config.LEXER_ADD_INFO = True

code  = """
int b = 10
str a = 20
int x 
; comentario

int main(x: int, b: int):
    return x
    
res = main(10, 20)
"""
cmb.SetCode(100000)
# RULES
class VAR_DECL(cmb.RuleItem):
    name = 'var declaration'
    code = cmb.AutoCode()
    grammar =  cmb.Seq(
        cmb.MatchGroup('types'),
        cmb.MatchToken('IDENT')   
    )

class DECL_ENTRYPOINT(cmb.RuleItem):
    name = 'entrypoint'
    code = cmb.AutoCode()
    grammar = cmb.Alt(
        cmb.Ref(VAR_DECL)
    )


l = lexer.Lexer(code.splitlines(keepends=True))
r = l.process()

p = parser.Parser(r)
r = p.parse(DECL_ENTRYPOINT)
print('nothing')
print(r)













