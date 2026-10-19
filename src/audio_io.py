"""Conversión de audio y validación de datos para SonoLab."""
from pathlib import Path
import math
import shutil
import subprocess
import sys
import numpy as np


def parse_number(text, name='Distancia'):
    try:
        value = float(str(text).strip().replace(',', '.'))
    except ValueError:
        raise ValueError(f'{name}: ingresá un número válido.') from None
    if not math.isfinite(value):
        raise ValueError(f'{name}: ingresá un número finito.')
    return value


def ffmpeg_path():
    name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
    bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / name
    path = str(bundled) if bundled.is_file() else shutil.which('ffmpeg')
    if not path:
        raise ValueError('No se encontró ffmpeg. Usá la distribución completa de SonoLab.')
    return path


def convert_audio(original, destination):
    process = subprocess.run(
        [ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
         '-i', str(original), '-vn', '-ac', '1', '-ar', '48000',
         '-acodec', 'pcm_s16le', str(destination)],
        capture_output=True, text=True, errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if process.returncode:
        raise ValueError('No se pudo leer o convertir el archivo. ' + process.stderr.strip()[-1200:])


def sanitize_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, (float, np.floating)) and not math.isfinite(obj):
        return None
    return obj
