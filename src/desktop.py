"""Abrir archivos con la aplicación del escritorio en Windows y Linux."""
from pathlib import Path
import os
import shutil
import subprocess
import sys


def open_path(path):
    target = str(Path(path).resolve(strict=True))
    if sys.platform == 'win32':
        os.startfile(target)
        return
    command = 'open' if sys.platform == 'darwin' else 'xdg-open'
    executable = shutil.which(command)
    if not executable:
        raise OSError(f'No se encontró {command}. En Linux, instalá el paquete xdg-utils.')
    env = os.environ.copy()
    # El visor del sistema necesita sus bibliotecas, no las de PyInstaller.
    if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
        original = env.get('LD_LIBRARY_PATH_ORIG')
        if original is not None:
            env['LD_LIBRARY_PATH'] = original
        else:
            env.pop('LD_LIBRARY_PATH', None)
    return subprocess.Popen([executable, target], env=env)
