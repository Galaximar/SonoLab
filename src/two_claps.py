"""Dos grabaciones independientes, dos pulsos y tiempo de vuelo directo.

A esta junto al primer pulso; B junto al segundo. Nunca se usa la distancia
ni una velocidad esperada para localizar los pulsos.
"""
from pathlib import Path
from dataclasses import asdict
import csv
import hashlib
import json

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfiltfilt

import sound_math
from audio_io import convert_audio, sanitize_json, parse_number
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from uncertainty import uncertainty_budget, explain_uncertainty, validate_config, format_speed


def _sound_groups(env, fs):
    """Agrupa actividad y descarta energía insignificante, sin datos del ensayo."""
    noise = float(np.median(env))
    mad = float(np.median(np.abs(env-noise)))
    threshold = max(.04*float(env.max()), noise+10*mad, 3*noise)
    if env.max() <= 0 or threshold >= .7*env.max():
        return [], 0
    active_samples = np.flatnonzero(env > threshold)
    if not len(active_samples):
        return [], 0
    groups = np.split(active_samples, np.flatnonzero(np.diff(active_samples) > .12*fs)+1)
    energies = [float(np.sum(np.maximum(env[g[0]:g[-1]+1]**2-noise**2, 0))) for g in groups]
    if len(groups) < 2:
        return groups, 0
    reference = sorted(energies, reverse=True)[1]
    retained = [g for g, e in zip(groups, energies) if e >= .10*reference]
    return retained, len(groups)-len(retained)


def detect_claps(x, fs):
    """Marca el primer frente significativo de cada una de dos emisiones.

    El agrupamiento de 120 ms evita contar oscilaciones y colas como aplausos
    nuevos. Se requiere una separacion de 250 ms; no un segundo exacto.
    Los umbrales son heuristicas de deteccion, no una validacion del experimento.
    """
    x = np.asarray(x, dtype=float)
    if fs <= 0 or x.ndim != 1 or len(x) < fs // 2 or not np.all(np.isfinite(x)):
        raise ValueError('Audio inválido o demasiado corto para dos aplausos separados.')
    env = np.sqrt(np.maximum(uniform_filter1d(x*x, max(3, round(.001*fs))), 0))
    peak = float(env.max())
    noise = float(np.median(env))
    mad = float(np.median(np.abs(env-noise)))
    threshold = max(.04*peak, noise+10*mad, 3*noise)
    if peak <= 0 or threshold >= .7*peak:
        raise ValueError('No se distinguen aplausos del ruido o del sonido continuo.')
    groups, discarded = _sound_groups(env, fs)
    selection = 'banda completa'
    # Los ruidos graves de manipulación pueden tener más energía que el aplauso
    # lejano. Si hay grupos extra, buscamos dos eventos en la banda aguda.
    # Se usa sólo para localizar eventos; los tiempos se miden en el ORIGINAL.
    # Nunca se seleccionan simplemente los dos picos más grandes.
    if len(groups) > 2 or discarded:
        filtered = sosfiltfilt(butter(4, min(1000, .2*fs), btype='highpass', fs=fs, output='sos'), x)
        high_band_envelope = np.sqrt(np.maximum(uniform_filter1d(filtered*filtered, max(3, round(.001*fs))), 0))
        candidates, _ = _sound_groups(high_band_envelope, fs)
        if len(candidates) == 2:
            groups = candidates
            selection = 'banda aguda para separar ruidos graves; inicio en audio original'
        elif len(candidates) > 2:
            raise ValueError('Hay más de dos eventos también en la banda aguda. Selección ambigua; revisá los sonidos o repetí la toma.')
    if len(groups) != 2:
        raise ValueError(f'Se encontraron {len(groups)} grupos de sonido; se necesitan dos. '
                         'Revisá el gráfico o indicá manualmente los cuatro inicios.')
    times, sensitivity, notices = [], [], []
    if selection != 'banda completa':
        notices.append('Se separaron ruidos graves usando la banda aguda. Los inicios se midieron en la señal original; selección automática provisional.')
    if discarded:
        notices.append(f'Se ignoraron {discarded} grupos de energía pequeña frente a las dos emisiones. Revisá la selección.')
    for indices in groups:
        start, end = int(indices[0]), int(indices[-1])
        if start < .005*fs or end >= len(x)-.005*fs:
            raise ValueError('Un pulso está recortado en un extremo del audio.')
        # La duracion de la cola no define el comienzo: un grito puede durar mas
        # de 180 ms. Se recorre hacia adelante desde el fondo anterior, sin
        # retroceder desde el maximo tardio del sonido.
        local = float(np.max(env[start:end+1]))
        search_start = max(0, start-round(.20*fs))
        background = env[search_start:max(search_start+1, start-round(.08*fs))]
        base = float(np.median(background))
        spread = float(np.median(np.abs(background-base)))
        hold_samples = max(2, round(.001*fs))
        markers = []
        for factor in [.75, 1.0, 1.5]:
            level = base + factor*max(8*spread, 3*base, .02*local)
            above_threshold = env[search_start:end+1] > level
            # El frente debe seguir al ultimo tramo de fondo antes del grupo:
            # evita marcar un roce aislado 100–200 ms antes del sonido principal.
            previous_quiet = ~above_threshold[:start-search_start+1]
            quiet_edges = np.diff(np.r_[False, previous_quiet, False].astype(np.int8))
            quiet_starts = np.flatnonzero(quiet_edges == 1)
            quiet_ends = np.flatnonzero(quiet_edges == -1)
            pauses = quiet_ends[quiet_ends-quiet_starts >= round(.01*fs)]
            if not len(pauses):
                raise ValueError('No se distingue un tramo de fondo antes del sonido. Revisá el primer frente manualmente.')
            boundary = int(pauses[-1])
            edges = np.diff(np.r_[False, above_threshold, False].astype(np.int8))
            starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
            candidates = starts[(ends-starts >= hold_samples) & (starts >= boundary)]
            if not len(candidates):
                raise ValueError('No hay un primer frente que sobresalga del fondo durante 1 ms. Revisá el inicio manualmente.')
            j = search_start+int(candidates[0])
            if j <= search_start+1:
                raise ValueError('El sonido ya estaba activo al comenzar la ventana de búsqueda del inicio. Revisá la marca manualmente.')
            markers.append(j/fs)
        times.append(markers[1])
        sensitivity.append(markers)
    if times[1]-times[0] < .25:
        raise ValueError('Los dos pulsos están demasiado próximos: dejá una pausa clara entre ellos.')
    # Cada inicio puede desplazarse de forma independiente. Variar ambos con el
    # mismo factor permite cancelaciones y subestima la sensibilidad del intervalo.
    interval_min = min(sensitivity[1])-max(sensitivity[0])
    interval_max = max(sensitivity[1])-min(sensitivity[0])
    return dict(tiempos=times, intervalo=times[1]-times[0],
                sensibilidad_s=float(interval_max-interval_min),
                marcas_por_umbral=sensitivity,
                intervalo_min_s=interval_min, intervalo_max_s=interval_max,
                origen='automático · primer frente',
                seleccion=selection,
                avisos=notices)


def measure_audio(x, fs, markers=None):
    if markers is None:
        return detect_claps(x, fs)
    if not isinstance(markers, (list, tuple)) or len(markers) != 2:
        raise ValueError('Indicá dos inicios por audio.')
    t1, t2 = [parse_number(t, 'Inicio del aplauso') for t in markers]
    if not 0 <= t1 < t2 < len(x)/fs:
        raise ValueError('Los inicios manuales deben estar ordenados y dentro de su audio.')
    analysis_result = dict(tiempos=[t1, t2], intervalo=t2-t1, sensibilidad_s=None, origen='manual')
    # Editar una fila redondea a seis decimales las marcas automáticas. Conservar
    # su referencia de sensibilidad si siguen siendo las mismas (una muestra).
    # No se cambian marcas manuales ni el control de aceptación del par.
    try:
        automatic = detect_claps(x, fs)
        if np.max(np.abs(np.array(automatic['tiempos'])-[t1, t2])) <= 1/fs:
            analysis_result['referencia_umbral_manual'] = automatic['marcas_por_umbral']
    except ValueError:
        pass
    return analysis_result


def calculate_pair(d, a, b):
    d = parse_number(d)
    if d <= 0:
        raise ValueError('La separación debe ser mayor que cero.')
    ta, tb = a['intervalo'], b['intervalo']
    delta = ta-tb
    if delta <= 0:
        raise ValueError('TA debe ser mayor que TB. Revisá las marcas y el orden A/B: '
                         'A está junto al primer aplauso y B junto al segundo. No se toma valor absoluto.')
    # Una sensibilidad a umbrales comparable a la diferencia no permite resolverla.
    sensitivities = [r['sensibilidad_s'] for r in (a, b)]
    sensitivity = sum(s for s in sensitivities if s is not None)
    if sensitivity >= delta:
        raise ValueError('La diferencia TA−TB no se resuelve frente a la variación de las marcas. '
                         'Revisá los inicios o repetí la medición.')
    return dict(ta_s=ta, tb_s=tb, diferencia_s=delta, delta_t_ms=1000*delta,
                velocidad=2*d/delta,
                sensibilidad_s=sensitivity if all(s is not None for s in sensitivities) else None)


def validate_entries(entries, base_folder=None):
    if not entries:
        raise ValueError('Agregá al menos un par de grabaciones.')
    new_entries, seen = [], set()
    base = Path(base_folder) if base_folder is not None else Path.cwd()
    for e in entries:
        d = parse_number(e['distancia_m'])
        if d <= 0:
            raise ValueError('La separación debe ser positiva.')
        a, b = [(base / Path(e[k])).resolve() for k in ('archivo_a', 'archivo_b')]
        if a == b:
            raise ValueError('A y B deben ser grabaciones diferentes.')
        if a in seen or b in seen:
            raise ValueError('Una grabación ya pertenece a otra medición de esta sesión.')
        seen.update((a, b))
        new_entry = dict(e, archivo_a=str(a), archivo_b=str(b), distancia_m=d)
        # Compatibilidad: la antigua casilla no debe filtrar sesiones guardadas.
        new_entry.pop('revisado', None)
        new_entries.append(new_entry)
    return new_entries


def plot_pair(recordings, detections, path, heading=None):
    fig, axes = plt.subplots(3, 2, figsize=(12, 8))
    for c, side in enumerate(('a', 'b')):
        if side not in recordings:
            for ax in axes[:, c]:
                ax.text(.5, .5, f'Audio {side.upper()} no disponible', ha='center', transform=ax.transAxes)
            continue
        fs, x = recordings[side]
        t = np.arange(len(x))/fs
        ax = axes[0, c]
        step = max(1, len(x)//50000)
        ax.plot(t[::step], x[::step], lw=.5, color='#176e80')
        ax.set(title=f'Celular {side.upper()} · grabación completa', xlabel='Tiempo de su archivo (s)')
        markers = detections.get(side, {}).get('tiempos', [])
        for k in range(2):
            zoom = axes[k+1, c]
            if len(markers) != 2:
                zoom.text(.5, .5, 'Sin dos marcas válidas\nUsá la revisión manual', ha='center', transform=zoom.transAxes)
                continue
            marker = markers[k]
            ax.axvline(marker, color='#c24e29', lw=1)
            mask = (t >= marker-.02) & (t <= marker+.04)
            zoom.plot(t[mask], x[mask], lw=.6, color='#176e80')
            zoom.axvline(marker, color='#c24e29')
            zoom.set(title=f'Aplauso {k+1}: {marker:.6f} s', xlabel='Tiempo de su archivo (s)')
            zoom.grid(alpha=.2)
    fig.suptitle(heading or 'Una medición: dos audios completos y ampliaciones de sus dos aplausos')
    fig.tight_layout()
    fig.savefig(path, dpi=135)
    plt.close(fig)


def analyze_pairs(entries, output, temperature=None, progress=None, uncertainty_config=None):
    entries = validate_entries(entries)
    if uncertainty_config is not None:
        uncertainty_config = validate_config(uncertainty_config)
    if temperature is not None:
        temperature = parse_number(temperature, 'Temperatura')
        if not -20 <= temperature <= 40:
            raise ValueError('Temperatura fuera del intervalo de la referencia aproximada.')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output/'wav').mkdir()
    (output/'senales').mkdir()
    rows = []
    for i, e in enumerate(entries, 1):
        if progress:
            progress(i-1, len(entries), f'Analizando par {i}/{len(entries)}')
        row = dict(e, nombre=f"{Path(e['archivo_a']).name} / {Path(e['archivo_b']).name}",
                    estado='Sin medición', avisos=[], velocidad=None, delta_t_ms=None,
                    ta_s=None, tb_s=None, diferencia_s=None, detecciones={}, grafico=None)
        recordings, detections, fingerprints = {}, {}, []
        # Se intenta leer ambos incluso si uno falla, para conservar el diagnostico.
        for side in ('a', 'b'):
            try:
                wav = output/'wav'/f'{i:03d}_{side}.wav'
                convert_audio(e[f'archivo_{side}'], wav)
                fs, x = sound_math.load_wav(str(wav))
                recordings[side] = (fs, x)
                fingerprints.append(hashlib.sha256(x.tobytes()).hexdigest())
                detections[side] = measure_audio(x, fs, e.get(f'marcas_{side}'))
            except (ValueError, OSError, sound_math.AudioError) as exc:
                row['avisos'].append(f'{side.upper()}: {exc}')
        row['detecciones'] = detections
        if 'a' in detections:
            row['ta_s'] = detections['a']['intervalo']
        if 'b' in detections:
            row['tb_s'] = detections['b']['intervalo']
        if len(detections) == 2:
            row['diferencia_s'] = row['ta_s']-row['tb_s']
            row['delta_t_ms'] = 1000*row['diferencia_s']
        if len(fingerprints) == 2 and fingerprints[0] == fingerprints[1]:
            row['avisos'].append('Los dos archivos contienen el mismo audio. Se necesitan dos grabaciones independientes.')
        if len(detections) == 2 and not row['avisos']:
            try:
                analysis_result = calculate_pair(e['distancia_m'], detections['a'], detections['b'])
                row.update(analysis_result)
                row['estado'] = 'Provisional'
                for side, det in detections.items():
                    row['avisos'].extend(f'{side.upper()}: {notice}' for notice in det.get('avisos', []))
                if analysis_result['sensibilidad_s'] is None:
                    row['avisos'].append('Marcas manuales: sensibilidad temporal no evaluada. Revisarlas no garantiza exactitud física.')
                elif analysis_result['sensibilidad_s'] > .20*analysis_result['diferencia_s']:
                    row['avisos'].append('La marca del inicio es sensible al umbral frente al tiempo de viaje. El resultado requiere revisión.')
                if not 250 <= analysis_result['velocidad'] <= 450:
                    row['avisos'].append('Velocidad alejada de la habitual en aire: revisá distancia y marcas. '
                                          'Este aviso no cambió la detección ni el cálculo.')
            except ValueError as exc:
                row['avisos'].append(str(exc))
        if recordings:
            path = output/'senales'/f'{i:03d}.png'
            plot_pair(recordings, detections, path,
                         heading=f"Medición {i} de {len(entries)} · Separación: {e['distancia_m']:g} m\n"
                         'Arriba: audios completos · Medio: primer aplauso · Abajo: segundo aplauso')
            row['grafico'] = str(path)
        rows.append(row)

    groups = []
    valid_rows = [f for f in rows if f['velocidad'] is not None]
    distances = sorted({f['distancia_m'] for f in valid_rows})
    for d in distances:
        values = np.array([f['diferencia_s'] for f in valid_rows if f['distancia_m'] == d])
        sem = float(values.std(ddof=1)/np.sqrt(len(values))) if len(values) > 1 else None
        groups.append(dict(distancia_m=d, n=len(values), delta_t_medio=float(values.mean()), delta_t_sem=sem))
    fit, fit_plot = None, None
    if len(groups) >= 3:
        d = np.array([g['distancia_m'] for g in groups])
        dt = np.array([g['delta_t_medio'] for g in groups])
        sem = np.array([g['delta_t_sem'] if g['delta_t_sem'] is not None else np.nan for g in groups])
        weighted = bool(np.all(np.isfinite(sem)) and np.all(sem > 0))
        fit_result = sound_math.linear_fit(d, dt, sem if weighted else None)
        if fit_result.m > 0 and np.isfinite(fit_result.m):
            fit = dict(asdict(fit_result), velocidad=fit_result.speed, sigma_velocidad=fit_result.sigma_speed,
                          ponderado=weighted, provisional=True, pares_utilizados=len(valid_rows))
            # Conserva el formato de los resultados exportados.
            fit['por_origen'] = fit.pop('through_origin')
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.errorbar(d, dt*1000, yerr=np.nan_to_num(sem)*1000, fmt='o', capsize=4,
                        color='#1976a3', label='Mediciones (promedio si hay repeticiones)')
            xx = np.linspace(0, max(d)*1.05, 100)
            ax.plot(xx, (fit_result.m*xx+fit_result.b)*1000, color='#e87919', label='Recta de mínimos cuadrados')
            ax.grid(alpha=.18)
            ax.legend(loc='upper left', fontsize=9)
            ax.set(xlabel='Separación entre celulares (m)', ylabel='TA − TB (ms)',
                   title='Ajuste provisional · todas las mediciones calculadas')
            fig.text(.5, .025, f'TA−TB (ms) = {fit_result.m*1000:.4f} × d (m) {fit_result.b*1000:+.4f}    |    '
                     f'v = 2 / {fit_result.m:.8f} s/m = {fit_result.speed:.1f} m/s', ha='center', fontsize=10)
            fig.tight_layout(rect=(0, .06, 1, 1))
            fit_plot = str(output/'ajuste.png')
            fig.savefig(fit_plot, dpi=135)
            plt.close(fig)
    r = sanitize_json(dict(filas=rows, grupos=groups, ajuste=fit, grafico_ajuste=fit_plot,
                    metodo='dos aplausos', temperatura=temperature,
                    teorica=sound_math.reference_speed(temperature) if temperature is not None else None,
                    mensaje='', salida=str(output)))
    r['presupuesto_incertidumbre'] = sanitize_json(uncertainty_budget(r, uncertainty_config)) if uncertainty_config is not None else None
    if r['presupuesto_incertidumbre']:
        if r['ajuste']:
            r['ajuste']['error_mostrado'] = r['presupuesto_incertidumbre'].get('margen_error_estimado_m_s')
            r['ajuste']['tipo_error'] = 'margen RMS estimado; sin cobertura fija'
        (output/'incertidumbre.md').write_text('# Fuentes de incertidumbre\n\n'+explain_uncertainty(r['presupuesto_incertidumbre']), encoding='utf-8')
        (output/'incertidumbre.json').write_text(json.dumps(r['presupuesto_incertidumbre'], ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (output/'resumen.json').write_text(json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    fields = ['archivo_a', 'archivo_b', 'distancia_m', 'ta_s', 'tb_s', 'diferencia_s', 'velocidad', 'estado', 'avisos']
    with (output/'mediciones.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in r['filas']:
            writer.writerow(dict(row, avisos=' | '.join(row['avisos'])))
    lines = ['# SonoLab · dos aplausos', '', 'v = 2d / (TA − TB). A está junto al primer aplauso.', '',
             '| Par | d (m) | TA (s) | TB (s) | TA−TB (ms) | v (m/s) | Estado |', '|---|---:|---:|---:|---:|---:|---|']
    for i, f in enumerate(r['filas'], 1):
        values = [f[k] for k in ('distancia_m', 'ta_s', 'tb_s', 'delta_t_ms', 'velocidad')]
        lines.append('| '+str(i)+' | '+' | '.join('—' if v is None else f'{v:.6g}' for v in values)+f" | {f['estado']} |")
        lines.extend(['', f"A: {f['archivo_a']}", f"B: {f['archivo_b']}", *f['avisos'], ''])
    if fit:
        kind = r['ajuste'].get('tipo_error', 'error estándar estadístico')
        lines.extend(['', f"Ajuste provisional: {format_speed(r['ajuste'], 2)} ({kind})."])
    if r['presupuesto_incertidumbre']:
        lines.extend(['', '## Fuentes de incertidumbre', '', explain_uncertainty(r['presupuesto_incertidumbre'])])
    (output/'resumen.md').write_text('\n'.join(lines), encoding='utf-8')
    if progress:
        progress(len(rows), len(rows), 'Análisis terminado')
    return r
