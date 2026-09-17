"""Construye un único ejecutable con Python, bibliotecas y ffmpeg incluidos."""
from pathlib import Path
import shutil
import subprocess
import sys
import argparse
from tempfile import TemporaryDirectory

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', '--nombre', dest='name', default='SonoLab', help='Nombre del ejecutable, sin extensión')
args = parser.parse_args()
if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.name):
    parser.error('El nombre solo admite letras, números, guion y guion bajo.')
ffmpeg = shutil.which('ffmpeg')
if not ffmpeg:
    raise SystemExit('Se necesita ffmpeg para construir el ejecutable.')
with TemporaryDirectory(prefix='sonolab-build-') as folder:
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
        '--windowed', '--name', args.name, '--distpath', str(root / 'dist'),
        '--workpath', folder, '--specpath', folder,
        '--add-binary', f'{ffmpeg};.', '--collect-all', 'PIL',
        '--exclude-module', 'pytest', '--exclude-module', 'IPython',
        '--exclude-module', 'pandas', '--exclude-module', 'sympy',
        '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6',
        '--exclude-module', 'PySide6', '--exclude-module', 'notebook',
        str(root / 'src' / 'paired_app.py'),
    ], check=True, cwd=root)
print(f'Ejecutable listo: {root / "dist" / (args.name + ".exe")}')
