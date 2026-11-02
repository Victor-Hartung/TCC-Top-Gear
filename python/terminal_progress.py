"""Barra solida colorida em uma linha, sem dependencias adicionais."""
import os
import re
import shutil
import sys

_width = 0


def _color_enabled():
    if not sys.stdout.isatty() or 'NO_COLOR' in os.environ:
        return False
    if os.name != 'nt':
        return os.environ.get('TERM') != 'dumb'
    # Habilita sequencias ANSI no console Windows sem alterar configuracoes globais.
    try:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.GetStdHandle(-11)
        mode = wintypes.DWORD()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return bool(kernel.SetConsoleMode(handle, mode.value | 0x0004))
        return bool(os.environ.get('WT_SESSION') or os.environ.get('TERM_PROGRAM'))
    except (AttributeError, OSError):
        return False


def _render_bar(text, color):
    def replace(match):
        filled, empty = match.group(1), match.group(2)
        if color:
            # Fundo continuo: nao depende de fonte com simbolos de bloco.
            fill_color = '46' if not empty else '45'
            return (' ' + f'\x1b[48;5;{fill_color}m' + ' ' * len(filled) +
                    '\x1b[48;5;238m' + ' ' * len(empty) + '\x1b[0m ')
        try:
            ('█' + '░').encode(sys.stdout.encoding or 'utf-8')
            return ' ' + '█' * len(filled) + '░' * len(empty) + ' '
        except UnicodeEncodeError:
            return match.group(0)
    return re.sub(r'\[(#*)(-*)\]', replace, text)


def clear_progress():
    global _width
    if _width:
        sys.stdout.write('\r' + ' ' * _width + '\r')
        sys.stdout.flush()
        _width = 0


def write_progress(text):
    global _width
    columns = max(1, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
    # Recorta antes de inserir ANSI para contar colunas visiveis corretamente.
    visible = text[:columns]
    if _width > columns:
        clear_progress()
    rendered = _render_bar(visible, _color_enabled())
    sys.stdout.write('\r' + rendered + ' ' * max(0, _width - len(visible)))
    sys.stdout.flush()
    _width = len(visible)


def finish_progress():
    global _width
    if _width:
        sys.stdout.write('\n')
        sys.stdout.flush()
        _width = 0
