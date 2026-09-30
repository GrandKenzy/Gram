from typing import Literal


line = '━'
left = '├'

ARESET: str = '\033[0m'

# Estilos
ABOLD: str = '\033[1m'
ADIM: str = '\033[2m'
AITALIC: str = '\033[3m'
AUNDERLINE: str = '\033[4m'

# Colores Estándar
ARED: str = '\033[31m'
AGREEN: str = '\033[32m'
AYELLOW: str = '\033[33m'
ABLUE: str = '\033[34m'
AMAGENTA: str = '\033[35m'
ACYAN: str = '\033[36m'
AWHITE: str = '\033[37m'

# Colores Brillantes
ABRIGHT_RED: str = '\033[91m'
ABRIGHT_GREEN: str = '\033[92m'
ABRIGHT_YELLOW: str = '\033[93m'
ABRIGHT_BLUE: str = '\033[94m'
ABRIGHT_MAGENTA: str = '\033[95m'
ABRIGHT_CYAN: str = '\033[96m'
ABRIGHT_WHITE: str = '\033[97m'
LogType = Literal[
    'warn',
    'advice',
    'success',
    'fatal',
    'error',
    'normal',
]

log_type_color_map = {
    'normal': '\033[37m',    # Blanco estándar
    'success': '\033[32m',   # Verde
    'warn': '\033[33m',      # Amarillo
    'error': '\033[31m',     # Rojo
    'advice': '\033[34m',    # Azul
    'fatal': '\033[38;5;52m'
}

log_type_icon_map = {
    'normal':  '◦ ',  # (U+25E6) Círculo hueco pequeño (o mantén el '· ')
    'success': '✓ ',  # (U+2713) Check ligero (mucho más elegante que ✔)
    'warn':    '△ ',  # (U+25B3) Triángulo hueco
    'error':   '✕ ',  # (U+2715) Cruz de multiplicación fina
    'advice':  '✦ ',  # (U+2726) Estrella de 4 puntas (Elegante y no intrusivo)
    'fatal':   '⊗ ',  # (U+2297) Cruz dentro de un círculo (Da la sensación de sistema colapsado)
}  

ONLY_SHOW_TYPES: list[LogType] = ['normal', 'advice', 'error', 'fatal', 'success', 'warn']
MAX_PRIORITY = 1000
def LogTypeColor(t: str):
    default = log_type_color_map['normal']
    return log_type_color_map.get(t.lower(), default)

def LogTypeIcon(t: str):
    default = log_type_icon_map['normal']
    return log_type_icon_map.get(t.lower(), default)