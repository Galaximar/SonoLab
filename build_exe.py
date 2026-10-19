"""Construye SonoLab para el sistema actual: Windows o Linux."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import argparse
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', '--nombre', dest='name', default='SonoLab', help='Nombre del ejecutable, sin extensión')
parser.add_argument('--dist-dir', type=Path, help='Carpeta de salida; por defecto dist en Windows y dist/linux en Linux')
args = parser.parse_args()
if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.name):
    parser.error('El nombre solo admite letras, números, guion y guion bajo.')
if sys.platform != 'win32' and not sys.platform.startswith('linux'):
    parser.error('La distribución está preparada para Windows y Linux.')
destination = args.dist_dir.resolve() if args.dist_dir else root / 'dist'
if args.dist_dir is None and sys.platform.startswith('linux'):
    destination /= 'linux'
ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    raise SystemExit('Se necesita ffmpeg para construir el ejecutable.')
with TemporaryDirectory(prefix='sonolab-build-') as folder:
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
        '--windowed', '--name', args.name, '--distpath', str(destination),
        '--workpath', folder, '--specpath', folder,
        '--add-binary', f'{ffmpeg}{os.pathsep}.', '--collect-all', 'PIL',
        '--exclude-module', 'pytest', '--exclude-module', 'IPython',
        '--exclude-module', 'pandas', '--exclude-module', 'sympy',
        '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6',
        '--exclude-module', 'PySide6', '--exclude-module', 'notebook',
        str(root / 'src' / 'paired_app.py'),
    ], check=True, cwd=root)
suffix = '.exe' if sys.platform == 'win32' else ''
print(f'Ejecutable listo: {destination / (args.name + suffix)}')
