"""Presupuesto condicional para el margen de error del ajuste publicado.

La dispersión residual NO se suma a las mismas fuentes que pueden producirla.
La sensibilidad al umbral no calibra el sesgo absoluto del detector.
"""
import numpy as np
import sound_math
from audio_io import parse_number


EXPERIMENT_CONFIG = dict(resolucion_distancia_m=.001, altura_min_m=.38, altura_max_m=.44,
                         margen_sillas_m=.03, sillas_fijas=True)


def validate_config(config):
    c = {k: parse_number(config.get(k, default), k) for k, default in EXPERIMENT_CONFIG.items() if k != 'sillas_fijas'}
    c['sillas_fijas'] = config.get('sillas_fijas', True)
    if not isinstance(c['sillas_fijas'], bool):
        raise ValueError('Indicá si la posición de los teléfonos en las sillas fue fija.')
    if c['resolucion_distancia_m'] <= 0 or c['margen_sillas_m'] < 0 or not 0 <= c['altura_min_m'] <= c['altura_max_m']:
        raise ValueError('Graduación de cinta positiva y alturas ordenadas, mayores o iguales a cero.')
    return c


def uncertainty_budget(r, config):
    c = validate_config(config)
    analysis_result = dict(config=c, incertidumbre_total=None,
        estado='Cálculo del margen combinado estimado para el ±',
        supuestos=[
            'Cinta: lectura redondeada a la graduación indicada más cercana; distribución uniforme dentro de media división. No incluye calibración, alineación ni colocación.',
            'Manos: verticalmente encima de su micrófono; teléfonos a la misma altura. Altura uniforme dentro del rango indicado. Se supone igual en ambos extremos de cada ensayo y variable entre separaciones.',
            'Detección: cada inicio varía independientemente dentro de un margen simétrico que contiene los candidatos de umbral 0,75–1,5. Modelo exploratorio, sin calibración de exactitud.',
            'Errores de diferentes separaciones independientes. La altura y la lectura de distancia se consideran comunes a las repeticiones de una separación.',
            'Sillas: margen indicado para la separación TOTAL entre micrófonos, no por teléfono; distribución uniforme. Posiciones fijas: un desplazamiento común a todas las distancias; si se acomodaron: desplazamientos independientes.',
            'Se añade solo la dispersión residual no explicada por las entradas (estimación por momentos). No se suma dos veces la misma variabilidad.',
            'Se conserva la velocidad del ajuste sin corregir. El ± es la raíz del error cuadrático medio modelado: combina varianza propagada y el cuadrado del desplazamiento geométrico no aplicado. No es una incertidumbre estándar centrada ni tiene cobertura fija.'],
        pendientes=['Sesgo absoluto al detectar el mismo frente en ambos teléfonos.',
                    'Diferencia de velocidad de los relojes y procesamiento de cada teléfono.',
                    'Calibración y colocación de la cinta; desplazamiento horizontal de manos y diferencia de altura entre micrófonos.',
                    'Correlaciones entre errores, ecos o saturación no cubiertos por variar el umbral.'])
    fit_result = r.get('ajuste')
    if not fit_result:
        analysis_result['detalle'] = 'Se necesita un ajuste válido para propagar las fuentes hasta la velocidad.'
        return analysis_result
    groups = r['grupos']
    d = np.array([g['distancia_m'] for g in groups])
    y = np.array([g['delta_t_medio'] for g in groups])
    sem = np.array([g['delta_t_sem'] for g in groups], dtype=float) if fit_result['ponderado'] else None
    h = (c['altura_min_m']+c['altura_max_m'])/2
    uh = (c['altura_max_m']-c['altura_min_m'])/np.sqrt(12)
    ud = c['resolucion_distancia_m']/np.sqrt(12)
    us = c['margen_sillas_m']/np.sqrt(3)
    q = np.hypot(d, h)-h
    ref = sound_math.linear_fit(q, y, sem)
    if ref.m <= 0:
        analysis_result['detalle'] = 'El escenario geométrico no tiene pendiente positiva.'
        return analysis_result
    # Derivadas de v = 2/m, para m = Sxy/Sxx con intercepto libre.
    w = 1/sem**2 if sem is not None else np.ones(len(d))
    mx, my = np.average(q, weights=w), np.average(y, weights=w)
    sxx = np.sum(w*(q-mx)**2)
    dm_dx = w*((y-my)-2*ref.m*(q-mx))/sxx
    dm_dy = w*(q-mx)/sxx
    dv_dx, dv_dy = -2*dm_dx/ref.m**2, -2*dm_dy/ref.m**2
    u_tape = float(np.linalg.norm(dv_dx*d/np.hypot(d, h)*ud))
    u_hands = float(np.linalg.norm(dv_dx*(h/np.hypot(d, h)-1)*uh))
    dq_dd = d/np.hypot(d, h)
    dq_dh = h/np.hypot(d, h)-1
    chair_covariance = np.outer(dq_dd, dq_dd)*us**2 if c['sillas_fijas'] else np.diag((dq_dd*us)**2)
    u_chairs = float(abs(dv_dx @ dq_dd)*us if c['sillas_fijas'] else np.linalg.norm(dv_dx*dq_dd)*us)
    # En el ajuste original d -> tiempo, un desplazamiento común de d no altera
    # la pendiente. En q(d,h) queda un pequeño efecto por la curvatura geométrica.
    rows = [f for f in r['filas'] if f['velocidad'] is not None]
    times, missing = [], []
    for g in groups:
        variances = []
        for f in (f for f in rows if f['distancia_m'] == g['distancia_m']):
            variance = 0.
            for side in ('a', 'b'):
                det = f['detecciones'][side]
                candidates = det.get('marcas_por_umbral') or det.get('referencia_umbral_manual')
                if not candidates:
                    missing.append(f"{f['nombre']} · {side.upper()}: sin candidatos de inicio")
                    variance = np.nan
                    continue
                for t, alternatives in zip(det['tiempos'], candidates):
                    margin = max(abs(float(other)-t) for other in alternatives)
                    variance += margin**2/3
            variances.append(variance)
        times.append(np.sqrt(np.sum(variances))/len(variances))
    u_t = np.array(times)
    u_detection = float(np.linalg.norm(dv_dy*u_t)) if np.all(np.isfinite(u_t)) else None
    combined = float(np.sqrt(u_tape**2+u_hands**2+u_detection**2+u_chairs**2)) if u_detection is not None else None
    additional, margin, tau2 = None, None, None
    offset = ref.speed-fit_result['velocidad']
    if combined is not None:
        cov_q = np.diag((dq_dd*ud)**2+(dq_dh*uh)**2)+chair_covariance
        cov_y = np.diag(u_t**2)+ref.m**2*cov_q
        # Residuo blanqueado: E(e'We) = tr(M sqrt(W) Cov sqrt(W)).
        # Una dispersión extra común tau² se estima sólo si la observada excede
        # la prevista. Se mantiene el ajuste y sus pesos originales.
        sqrt_weights = np.sqrt(w)
        design = np.column_stack((np.ones(len(q)), q))*sqrt_weights[:, None]
        projector = np.eye(len(q))-design @ np.linalg.pinv(design)
        residual = (y-(ref.m*q+ref.b))*sqrt_weights
        expected = float(np.trace(projector @ (sqrt_weights[:, None]*cov_y*sqrt_weights[None, :])))
        denominator = float(np.sum(np.diag(projector)*w))
        tau2 = max(0., (float(residual @ residual)-expected)/denominator)
        additional = float(np.linalg.norm(dv_dy)*np.sqrt(tau2))
        margin = float(np.sqrt(combined**2+additional**2+offset**2))
    analysis_result.update(velocidad_publicada=fit_result['velocidad'], sigma_recta=fit_result['sigma_velocidad'],
        escenario_geometrico=dict(altura_central_m=h, velocidad=ref.speed, b_s=ref.b,
            cambio_respecto_publicado=offset, aplicado_al_resultado=False),
        u_lectura_distancia_m=float(ud), margen_redondeo_m=c['resolucion_distancia_m']/2,
        u_altura_m=float(uh), u_sillas_m=float(us),
        contribuciones_m_s=dict(cinta=u_tape, manos=u_hands, deteccion=u_detection, sillas=u_chairs),
        u_entradas_modeladas_m_s=combined, u_residual_adicional_m_s=additional,
        varianza_residual_adicional_s2=tau2, margen_error_estimado_m_s=margin,
        deteccion_faltante=missing)
    return analysis_result


def explain_uncertainty(p):
    if not p:
        return 'No hay configuración de incertidumbre para esta sesión.'
    c = p['config']
    text = [p['estado'], '',
        f"Cinta: divisiones de {c['resolucion_distancia_m']*100:g} cm.",
        f"Manos: rango {c['altura_min_m']*100:g}–{c['altura_max_m']*100:g} cm sobre el micrófono.", '']
    text += [f"Sillas: ±{c['margen_sillas_m']*100:g} cm en la separación total; "
              + ('desplazamiento común (posiciones fijas).' if c['sillas_fijas'] else 'variación independiente entre mediciones.'), '']
    if 'contribuciones_m_s' in p:
        text += [f"Redondeo de lectura: ±{p['margen_redondeo_m']*100:g} cm; incertidumbre estándar {p['u_lectura_distancia_m']*100:.3f} cm.", '',
                  'APORTES A LA VELOCIDAD (incertidumbres estándar según los supuestos)']
        for k, v in p['contribuciones_m_s'].items():
            text.append(f"{k.capitalize()}: {v:.2f} m/s" if v is not None else f'{k.capitalize()}: no evaluada en todas las marcas')
        combined = p['u_entradas_modeladas_m_s']
        text += ['', f"Combinación de las cuatro fuentes: {combined:.2f} m/s." if combined is not None
                  else 'Combinación incompleta: faltan datos de detección.',
                  f"Error estadístico de la recta publicada: {p['sigma_recta']:.2f} m/s, informado aparte. No se suma automáticamente.", '']
        margin = p.get('margen_error_estimado_m_s')
        if margin is not None:
            text += ['EL ± MOSTRADO JUNTO A LA VELOCIDAD',
                f"{p['velocidad_publicada']:.2f} ± {margin:.2f} m/s (margen combinado estimado, RMS)",
                f"Dispersión residual adicional no explicada: {p['u_residual_adicional_m_s']:.2f} m/s.",
                'Margen = √(u_cinta² + u_manos² + u_detección² + u_sillas² + u_residual_adicional² + desplazamiento_geométrico²).',
                'La parte fija de la distancia se absorbe en gran medida en b; no se trata como seis errores independientes. '
                'El margen incluye el desplazamiento geométrico modelado sin cambiar el valor central. '
                'RMS significa raíz del error cuadrático medio estimado. No asegura cubrir todos los errores.', '']
        geo = p['escenario_geometrico']
        text += ['EFECTO SISTEMÁTICO DE LA GEOMETRÍA',
            f"Escenario con manos a {geo['altura_central_m']*100:g} cm: ajuste {geo['velocidad']:.2f} m/s "
            f"(cambio {geo['cambio_respecto_publicado']:+.2f} m/s respecto del publicado).",
            'Es un escenario para evaluar el error: NO reemplaza el ajuste principal. Los aportes anteriores se propagan en este modelo geométrico.', '',
            'La variación de las manos no es lo mismo que el desplazamiento por su altura media. '
            'La sensibilidad al umbral no garantiza detectar el instante físico exacto.', '']
    else:
        text += [p.get('detalle', ''), '']
    if p.get('deteccion_faltante'):
        text += ['MARCAS SIN REFERENCIA DE SENSIBILIDAD', *p['deteccion_faltante'], '']
    text += ['SUPUESTOS', *p['supuestos'], '', 'FUENTES TODAVÍA SIN CUANTIFICAR', *p['pendientes'], '',
              'Método: propagación de incertidumbres (NIST TN 1297). Para un intervalo uniforme, u = semiancho/√3. '
              'La propagación incluye la covarianza del desplazamiento común de las sillas. '
              'La raíz del error cuadrático medio (RMS) añade el sesgo modelado no corregido; es un criterio de margen estimado, no un intervalo de cobertura NIST.',
              'Referencia: https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty']
    return '\n'.join(text)


def format_speed(fit_result, decimals=1):
    if not fit_result:
        return 'Sin ajuste'
    error = fit_result.get('error_mostrado', fit_result['sigma_velocidad'])
    if error is None:
        return f"{fit_result['velocidad']:.{decimals}f} m/s · ± pendiente"
    return f"{fit_result['velocidad']:.{decimals}f} ± {error:.{decimals}f} m/s"
