"""Carga WAV, referencia de temperatura y ajuste lineal usados por SonoLab."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
from scipy.io import wavfile


def reference_speed(temperature_c: float) -> float:
    """Velocidad del sonido en aire seco segun la aproximacion lineal usual.

        v(T) = 331.3 + 0.606 * T      [m/s, T en grados Celsius]

    Es una linealizacion de v = sqrt(gamma*R*T/M) alrededor de 0 C, valida con
    error < 0.2 % en el rango -20 C a +40 C, que cubre cualquier medicion al
    aire libre.
    """
    return 331.3 + 0.606 * float(temperature_c)


class AudioError(Exception):
    """Problema al leer o interpretar un archivo de audio."""


def load_wav(path: str) -> tuple[int, np.ndarray]:
    """Lee un .wav y devuelve (frecuencia_muestreo, senal_mono_float).

    - Convierte estereo (o mas canales) a mono promediando canales.
    - Normaliza cualquier formato entero al rango [-1, 1].
    - Centra la senal restando el valor medio (elimina offset DC del micro).
    """
    import os

    if not os.path.isfile(path):
        raise AudioError(
            f"No existe el archivo '{path}'.\n"
            "  -> Revisa la ruta en datos/mediciones.csv. Las rutas se "
            "interpretan relativas a la carpeta audio/."
        )
    try:
        fs, data = wavfile.read(path)
    except Exception as exc:  # formato no soportado, archivo corrupto, etc.
        raise AudioError(
            f"No se pudo leer '{path}': {exc}\n"
            "  -> scipy no soporta WAV de 24 bits ni formatos comprimidos. "
            "Reexporta con:\n"
            "     ffmpeg -i entrada.mp4 -vn -ac 1 -ar 48000 -acodec pcm_s16le salida.wav"
        ) from exc

    x = np.asarray(data)
    if x.ndim > 1:                       # estereo o multicanal -> mono
        x = x.mean(axis=1)
    x = x.astype(np.float64)

    # Normalizacion segun el tipo original
    kind = np.asarray(data).dtype
    if np.issubdtype(kind, np.integer):
        x /= float(np.iinfo(kind).max)
    elif np.issubdtype(kind, np.floating):
        peak = np.max(np.abs(x))
        if peak > 1.0:
            x /= peak

    x -= x.mean()                        # quita offset DC
    if x.size < int(0.05 * fs):
        raise AudioError(f"'{path}' dura menos de 50 ms; no hay nada que analizar.")
    if not np.any(x):
        raise AudioError(f"'{path}' es silencio puro (todas las muestras en cero).")
    return int(fs), x


@dataclass
class LinearFit:
    """Resultado de un ajuste lineal dt = m*d + b (o dt = m*d si through_origin)."""
    m: float                 # pendiente [s/m]
    sigma_m: float
    b: float                 # ordenada al origen [s]
    sigma_b: float
    r2: float
    chi2_red: float
    n: int
    through_origin: bool

    @property
    def speed(self) -> float:
        """v = 2/m: la pendiente de dt vs d es 2/v."""
        return 2.0 / self.m

    @property
    def sigma_speed(self) -> float:
        """Propagacion: v = 2/m  =>  sigma_v = 2 sigma_m / m^2 = v * sigma_m/m."""
        return 2.0 * self.sigma_m / (self.m ** 2)


def linear_fit(
    d: np.ndarray,
    dt: np.ndarray,
    sigma_dt: Optional[np.ndarray] = None,
    through_origin: bool = False,
) -> LinearFit:
    """Minimos cuadrados (ponderados si hay sigmas) de dt frente a d.

    Un sesgo aditivo CONSTANTE en dt puede representarse con b. No se supone
    que todo error experimental sea constante: sesgos de inicio que cambian
    con distancia/intensidad tambien pueden alterar la pendiente. En el metodo
    de dos telefonos, una latencia fija de cada grabador se cancela al restar
    los dos instantes dentro de su propio archivo; no debe atribuirse a b.

    Por eso la ordenada al origen se reporta pero no se fuerza a cero: un |b|
    grande frente a los dt medidos puede indicar un sesgo o un modelo inadecuado.
    """
    d = np.asarray(d, dtype=float)
    dt = np.asarray(dt, dtype=float)
    n = d.size
    minimum = 2 if not through_origin else 1
    if n < minimum + 1:
        raise ValueError(
            f"Hacen falta al menos {minimum + 1} distancias distintas para el "
            f"ajuste{'  (por origen)' if through_origin else ''}; hay {n}."
        )
    if np.allclose(d, d[0]):
        raise ValueError("Todas las mediciones estan a la misma distancia: el ajuste es imposible.")

    if sigma_dt is None or not np.all(np.isfinite(sigma_dt)) or np.any(np.asarray(sigma_dt) <= 0):
        w = np.ones(n)
        absolute_weights = False
    else:
        w = 1.0 / np.asarray(sigma_dt, dtype=float) ** 2
        absolute_weights = True

    S = w.sum()
    Sx = (w * d).sum()
    Sy = (w * dt).sum()
    Sxx = (w * d * d).sum()
    Sxy = (w * d * dt).sum()

    if through_origin:
        m = Sxy / Sxx
        b, var_b = 0.0, 0.0
        var_m = 1.0 / Sxx
        dof = max(1, n - 1)
    else:
        D = S * Sxx - Sx * Sx
        m = (S * Sxy - Sx * Sy) / D
        b = (Sxx * Sy - Sx * Sxy) / D
        var_m = S / D
        var_b = Sxx / D
        dof = max(1, n - 2)

    residuals = dt - (m * d + b)
    chi2 = float((w * residuals ** 2).sum())
    chi2_red = chi2 / dof

    # Si los pesos no vienen de sigmas reales, la escala de las incertidumbres
    # sale de la dispersion de los propios residuos.
    if not absolute_weights:
        var_m *= chi2_red
        var_b *= chi2_red

    ss_res = float((residuals ** 2).sum())
    ss_tot = float(((dt - dt.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return LinearFit(
        m=float(m), sigma_m=float(np.sqrt(var_m)),
        b=float(b), sigma_b=float(np.sqrt(var_b)),
        r2=float(r2), chi2_red=float(chi2_red), n=int(n), through_origin=through_origin,
    )
