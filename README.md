# SonoLab

Aplicación de escritorio para estimar la velocidad del sonido con **dos celulares y dos aplausos**. Cada medición usa los dos audios de un mismo ensayo y la separación entre micrófonos. El programa detecta los inicios, calcula los tiempos, ajusta una recta y estima el margen de error.

Este README reúne la documentación de uso, instalación, código y cálculos. La [bitácora](bitacora/bitacora.md) conserva el desarrollo del experimento, sus resultados y los problemas encontrados.

## 1. Probar el ejecutable

En Windows:

1. Abrir [dist/SonoLab.exe](dist/SonoLab.exe).
2. Ir a **Archivo → Abrir sesión** y elegir [sesion_guardada.json](sesion_guardada.json), en la raíz del proyecto.
3. Pulsar **Analizar pares**.

El ejecutable incluye Python, las bibliotecas y FFmpeg. Para usarlo no hace falta instalarlos aparte.

El JSON de ejemplo contiene seis pares a **3; 4; 5; 6; 7 y 7,8 m**, sin marcas manuales. Los doce audios están incluidos en `audios/A` y `audios/B`. La sesión utiliza rutas relativas a su propia ubicación. Para probarla en otra computadora, copiar la carpeta del proyecto conservando esa estructura.

## 2. Iniciar desde el código

### Requisitos

- Windows: la interfaz, la apertura de archivos y el empaquetado están preparados para este sistema.
- Python con Tkinter. El proyecto se ha ejecutado y compilado con **Python 3.12**.
- FFmpeg instalado y disponible en `PATH`.
- Dependencias de [requirements.txt](requirements.txt).

| Dependencia | Uso                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------ |
| NumPy       | Vectores, estadística y álgebra del ajuste.                                                            |
| SciPy       | Lectura WAV, filtros y envolvente de la señal.                                                         |
| Matplotlib  | Gráficos PNG de los audios y del ajuste.                                                               |
| Pillow      | Mostrar y redimensionar los gráficos en la ventana.                                                    |
| Tkinter     | Ventanas, botones, tablas y diálogos; viene con la instalación de Python para Windows que se usa aquí. |
| FFmpeg      | Extraer y convertir audio de WAV, MP4, M4A, MPEG y otros formatos que admita la instalación.           |
| PyInstaller | Crear el ejecutable; solo se necesita para compilar.                                                   |

### Preparación en PowerShell

Abrir una terminal en la carpeta del proyecto. Estos comandos usan un entorno virtual sin necesidad de activarlo:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instalar FFmpeg para Windows y agregar la carpeta que contiene `ffmpeg.exe` al `PATH`. Abrir de nuevo la terminal y comprobar:

```powershell
ffmpeg -version
Get-Command ffmpeg
```

Si no se quiere modificar el `PATH` permanentemente, se puede agregar la carpeta de FFmpeg solo a esa terminal, sustituyendo la ruta por la real:

```powershell
$env:PATH = 'C:\herramientas\ffmpeg\bin;' + $env:PATH
```

Iniciar SonoLab:

```powershell
.\.venv\Scripts\python.exe src/paired_app.py
```

El punto de entrada es **`paired_app.py`**. `app.py` contiene la ventana base y no se ejecuta como aplicación independiente.

## 3. Generar la distribución `dist`

Desde la raíz del proyecto, con FFmpeg accesible en `PATH`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build_exe.py
```

`requirements-build.txt` incluye las dependencias de ejecución y PyInstaller. El script [build_exe.py](build_exe.py):

1. Busca `ffmpeg.exe` con `shutil.which`.
2. Ejecuta PyInstaller sobre `src/paired_app.py` con `--onefile` y `--windowed`.
3. Incluye FFmpeg, Pillow y las dependencias detectadas.
4. Trabaja en una carpeta temporal, que se elimina al terminar.
5. Escribe **`dist/SonoLab.exe`**.

Cerrar SonoLab antes de compilar para que Windows permita reemplazar el ejecutable. No hace falta crear una carpeta `build` en el proyecto.

Para darle otro nombre:

```powershell
.\.venv\Scripts\python.exe build_exe.py --name MiSonoLab
```

El nombre admite letras, números, guion y guion bajo. La salida será `dist/MiSonoLab.exe`.

**El script genera el ejecutable.** `sesion_guardada.json` está en la raíz y los audios en `audios/`, fuera de `dist`; se conservan aunque se borre y reconstruya esa carpeta. Una sesión nueva se crea desde **Archivo → Guardar sesión**. Para entregar el proyecto con el ejemplo, incluir el JSON, `audios/` y el ejecutable de `dist/`.

## 4. Preparar y cargar una medición

1. Apoyar los celulares A y B en posiciones fijas y medir la separación entre micrófonos.
2. Registrar dónde quedan las manos respecto de los micrófonos.
3. Iniciar ambas grabaciones; no hace falta hacerlo al mismo tiempo.
4. Dar un aplauso junto a A y, después de una pausa clara, otro junto a B. La pausa puede ser de uno o dos segundos, sin necesidad de exactitud.
5. Detener las grabaciones después del segundo aplauso. Ambos archivos deben contener los mismos dos sonidos.
6. En **Agregar par A/B**, elegir los dos archivos y escribir la separación en metros.
7. Dejar vacíos los campos de inicio para detección automática y pulsar **Analizar pares**.

[Croquis del montaje](bitacora/anexos/croquis_montaje.svg).

### Controles y paneles

| Elemento                         | Función                                                                                                                                        |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Agregar par A/B                  | Añade una medición con dos archivos y una distancia.                                                                                           |
| Editar / revisar marcas          | Modifica archivos, distancia o los dos inicios de cada audio, expresados en segundos desde su propio comienzo.                                 |
| Quitar                           | Excluye de la sesión las filas seleccionadas.                                                                                                  |
| Temperatura                      | Valor opcional para la referencia teórica; no cambia la detección ni la velocidad medida.                                                      |
| Analizar pares                   | Convierte los audios, detecta, calcula y exporta.                                                                                              |
| Audios A y B · marcas            | Muestra una medición seleccionada: A a la izquierda, B a la derecha; arriba audios completos, en medio primer aplauso y abajo segundo aplauso. |
| Ajuste lineal · puntos y recta   | Muestra tiempos frente a distancia, recta y cálculo de la velocidad.                                                                           |
| Resumen del experimento          | Resume el análisis y sus avisos.                                                                                                               |
| Incertidumbre · fuentes de error | Explica el ± y los aportes calculados. No contiene un botón de configuración.                                                                  |
| Abrir resultados                 | Abre la carpeta con los archivos exportados.                                                                                                   |
| Archivo                          | Guarda y abre sesiones JSON.                                                                                                                   |

Al cambiar una entrada se invalidan los resultados visibles; hay que volver a analizar. Las exportaciones anteriores se conservan. No hay una casilla de revisión: el ajuste usa todos los pares que se pueden calcular. Una velocidad individual no recibe automáticamente un ±.

## 5. Estructura del código

```text
Taller/
├── README.md
├── build_exe.py
├── requirements.txt
├── requirements-build.txt
├── src/
│   ├── paired_app.py
│   ├── app.py
│   ├── two_claps.py
│   ├── audio_io.py
│   ├── sound_math.py
│   └── uncertainty.py
├── sesion_guardada.json
├── audios/
│   ├── A/
│   └── B/
├── dist/
│   └── SonoLab.exe
└── bitacora/
    ├── bitacora.md
    └── anexos/
```

Los audios se seleccionan desde cualquier carpeta; no se deducen sus distancias de los nombres.

| Archivo                                        | Responsabilidad y elementos principales                                                                                                                                                                                                                                                                        |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [paired_app.py](src/paired_app.py)               | Entrada `main()`. `PairDialog` recoge y valida una medición. `SonoLabApp` controla filas, edición, sesiones, análisis y paneles específicos.                                                                                                                                                                  |
| [app.py](src/app.py)                           | Clase base `BaseWindow`: estilo, controles comunes, cola de eventos, bloqueo durante el análisis, visualización de imágenes y cierre.                                                                                                                                                                              |
| [two_claps.py](src/two_claps.py)         | `analyze_pairs()` coordina todo. `validate_entries()` revisa pares; `detect_claps()` busca inicios; `measure_audio()` admite marcas manuales; `calculate_pair()` calcula tiempos y velocidad; `plot_pair()` dibuja señales. También agrupa repeticiones, genera el gráfico del ajuste y exporta archivos. |
| [audio_io.py](src/audio_io.py) | `parse_number()` admite coma o punto decimal y exige valores finitos. `ffmpeg_path()` localiza FFmpeg. `convert_audio()` prepara WAV. `sanitize_json()` convierte valores no finitos a `None` para exportarlos como `null`.                                                                                                     |
| [sound_math.py](src/sound_math.py)                           | `load_wav()` lee y centra la señal; `linear_fit()` calcula la regresión; `LinearFit` contiene resultados y propiedades de velocidad/error; `reference_speed()` calcula la referencia térmica.                                                                                                              |
| [uncertainty.py](src/uncertainty.py)       | `EXPERIMENT_CONFIG` define valores iniciales; `validate_config()` los valida; `uncertainty_budget()` calcula las fuentes de error; `explain_uncertainty()` arma el texto y `format_speed()` muestra el resultado con su ±.                                                                                                    |

El método usa dos sonidos directos: uno cerca de cada celular.

### Recorrido de un análisis

```text
Interfaz: archivos A/B + distancia + temperatura opcional + configuración
  → validar entradas
  → FFmpeg: WAV mono a 48 000 Hz, PCM de 16 bits
  → cargar señal y detectar dos inicios por audio, o usar marcas manuales
  → TA, TB, diferencia D y velocidad individual
  → agrupar D por distancia y ajustar la recta
  → calcular el margen de incertidumbre
  → exportar tablas y gráficos y actualizar la ventana
```

`SonoLabApp.analyze()` ejecuta el cálculo en un hilo para mantener la ventana disponible. Envía progreso, resultados o errores por `self.events`; `BaseWindow.process_events()` procesa esa cola periódicamente desde el hilo de la interfaz.

## 6. Cómo se encuentran los aplausos

La detección recibe **la señal y su frecuencia de muestreo**. No recibe distancia, temperatura ni velocidad esperada.

1. **Preparar la señal.** FFmpeg extrae el audio, lo convierte a mono, 48 kHz y PCM de 16 bits. `load_wav()` lo convierte a números reales, normaliza según el formato y resta su media.
2. **Calcular la envolvente RMS.** Se promedian cuadrados en una ventana de aproximadamente 1 ms y se toma la raíz. Esto representa la intensidad local sin seguir cada oscilación.
3. **Separar grupos.** Con `p = máximo`, `r = mediana` y `MAD = mediana(|envolvente−r|)`, el umbral inicial es `max(0,04p; r+10MAD; 3r)`. Se rechaza una señal sin contraste suficiente. Las regiones activas separadas por más de 120 ms forman grupos diferentes.
4. **Descartar grupos de energía muy pequeña.** Se conserva un grupo si alcanza al menos el 10 % de la energía del segundo grupo más energético. Los descartes se informan.
5. **Resolver ruidos graves adicionales.** Si hay más de dos grupos o se descarta alguno, se intenta localizar dos eventos con un filtro pasaaltos Butterworth de orden 4 y corte `min(1000 Hz, 0,2·fs)`. Con la conversión habitual, el corte es 1000 Hz. Si aparecen exactamente dos candidatos se usan sus zonas; si aparecen más de dos se rechaza la ambigüedad. Si aparecen menos, se conserva la selección previa y se vuelve a exigir que tenga dos grupos.
6. **Marcar el comienzo en la señal original.** Se estima el fondo previo entre aproximadamente 200 y 80 ms antes del grupo. Se busca hacia adelante el primer tramo que supera el umbral al menos 1 ms, después del último tramo de fondo de al menos 10 ms. No se marca simplemente el máximo.
7. **Evaluar sensibilidad.** Se repite con factores `0,75; 1; 1,5`. El nivel es `base + factor·max(8·MAD_local; 3·base; 0,02·pico_local)`. La marca central corresponde al factor 1. Se exige una separación final de al menos 250 ms entre los dos inicios.

Se rechazan audios inválidos, demasiado cortos, pulsos recortados en los extremos y sonidos sin fondo o frente distinguible. Aunque el detector admite emisiones prolongadas, los aplausos breves facilitan identificar el mismo inicio físico en ambos teléfonos.

### Marcas manuales y sensibilidad

Para cada audio se admiten dos tiempos ordenados: `0 ≤ t1 < t2 < duración`. El programa respeta esos tiempos. Si coinciden con la detección automática dentro de una muestra, conserva sus candidatos de umbral para estimar incertidumbre; en otro caso esa referencia queda desconocida.

Para dos marcas con alternativas, el intervalo posible se calcula como:

```text
T_min = mínimo(t2) − máximo(t1)
T_max = máximo(t2) − mínimo(t1)
sensibilidad_s = T_max − T_min
```

Las marcas varían independientemente. Este ancho sirve para controlar si el intervalo está suficientemente definido; no es todavía una incertidumbre estándar.

## 7. Cálculo de la velocidad

### Una medición

Sean `tA1` y `tA2` los inicios en A; `tB1` y `tB2`, en B:

```text
TA = tA2 − tA1
TB = tB2 − tB1
D = TA − TB
v = 2d / D
```

`d` está en metros, los tiempos en segundos y `v` en m/s. La tabla muestra `D` en milisegundos, pero las cuentas internas usan segundos.

Si R es la espera desde que B oye el primer aplauso hasta que emite el segundo, con fuentes próximas a los micrófonos:

```text
TA = d/v + R + d/v
TB = R
TA − TB = 2d/v
```

Se cancela la espera y también el inicio independiente de cada grabación. No se cancelan necesariamente diferencias en el ritmo de sus relojes ni errores al elegir los inicios.

`calculate_pair()` exige distancia positiva y `D > 0`; no toma valor absoluto. Si la suma de los anchos de sensibilidad conocidos de A y B alcanza o supera D, rechaza el cálculo. Una sensibilidad desconocida no se considera evaluada: puede haber velocidad individual, pero quedar pendiente el margen de error.

También se rechazan dos archivos con el mismo audio convertido. Si la velocidad queda fuera de 250–450 m/s se agrega un aviso **sin cambiar ni descartar automáticamente el valor calculado por ese motivo**.

### Varias distancias: ajuste lineal

Las repeticiones de cada separación se agrupan. Para la distancia i, con `n_i` tomas:

```text
y_i = promedio de D en esa distancia
SEM_i = desviación estándar muestral de D / √n_i
```

Con una sola toma, el SEM no está disponible. El programa necesita al menos **tres distancias distintas calculadas** y una pendiente positiva y finita para mostrar el ajuste:

```text
y = m·d + b
v_ajuste = 2/m
```

La pendiente m se expresa en s/m. Si se lee en ms/m sobre el gráfico, la cuenta equivalente es `v = 2000/m_ms`.

**b es la ordenada al origen**, en segundos. Permite un desplazamiento de la recta y no se fuerza a cero. No demuestra la causa física del desplazamiento ni corrige todos los sesgos. La latencia fija de cada grabador ya se cancela al formar TA o TB.

### Fórmulas del ajuste y del error estadístico

Se usan pesos `w_i = 1/SEM_i²` solo cuando todos los SEM son positivos y finitos. Si alguno falta o vale cero, **todo el ajuste usa `w_i = 1`**.

Definiendo:

```text
S = Σw_i           Sx = Σ(w_i d_i)       Sy = Σ(w_i y_i)
Sxx = Σ(w_i d_i²)  Sxy = Σ(w_i d_i y_i)  C = S·Sxx − Sx²

m = (S·Sxy − Sx·Sy) / C
b = (Sxx·Sy − Sx·Sxy) / C
```

Con N distancias y residuos `r_i = y_i − (m d_i+b)`:

- Con SEM válidos: `u_m² = S/C` y `u_b² = Sxx/C`. No se reescalan por los residuos.
- Sin SEM válidos: las dos varianzas anteriores se multiplican por `Σr_i²/(N−2)`.
- Por **propagación de incertidumbres**, `u_v_recta = 2u_m/m²`.
- `R² = 1 − Σr_i² / Σ(y_i−promedio(y))²`; se informa como no disponible si el denominador es cero.
- El campo interno `chi2_red` es `Σ(w_i r_i²)/(N−2)`. Sin pesos de incertidumbre, es una varianza residual y no un chi cuadrado normalizado.

`linear_fit()` también admite `through_origin=True`, pero la aplicación usa el ajuste con intercepto libre. El error estadístico de la recta se informa aparte del margen combinado explicado a continuación.

## 8. Cómo se calcula el error mostrado

La interfaz utiliza `uncertainty_budget()` de `uncertainty.py`. Conserva la velocidad central del ajuste de **D frente a d** y calcula un **margen RMS estimado** que combina variación de las entradas, dispersión adicional y el desplazamiento de un escenario geométrico.

### Entradas y distribuciones

| Parámetro del JSON       | Significado                                                                        | Valor inicial |
| ------------------------ | ---------------------------------------------------------------------------------- | ------------: |
| `resolucion_distancia_m` | Separación entre marcas de la cinta.                                               |       0.001 m |
| `altura_min_m`           | Altura mínima de las manos sobre el micrófono.                                     |        0.38 m |
| `altura_max_m`           | Altura máxima.                                                                     |        0.44 m |
| `margen_sillas_m`        | Margen de un lado, ±a, en la separación total entre micrófonos.                    |        0.03 m |
| `sillas_fijas`           | Desplazamiento común entre separaciones si es `true`; independiente si es `false`. |        `true` |

Con distribución uniforme, un intervalo de ancho L tiene incertidumbre estándar `L/√12`; un margen ±a, `a/√3`. Son la misma fórmula porque `L = 2a`.

```text
u_d = resolución / √12 = 0,000289 m
h = (altura_mínima + altura_máxima)/2 = 0,41 m
u_h = (altura_máxima − altura_mínima)/√12 = 0,01732 m
u_s = margen_sillas/√3 = 0,01732 m
```

Estas son incertidumbres de las entradas, todavía no aportes en m/s. La cinta solo incluye redondeo. Los ±3 cm corresponden a la separación total, no a cada teléfono.

### Geometría y sensibilidad de la velocidad

El escenario supone manos verticalmente sobre sus micrófonos, teléfonos a la misma altura e igual altura de manos en los dos extremos de cada ensayo. La altura puede variar entre separaciones:

```text
q_i = √(d_i²+h²) − h
```

La raíz representa el recorrido al teléfono lejano; h, el recorrido al cercano. Se hace un ajuste auxiliar `y = m_g q + b_g`, con los mismos pesos que el ajuste principal, y se calcula `v_g = 2/m_g`. Este valor auxiliar **no reemplaza la velocidad publicada**.

Para propagar las entradas se calculan derivadas, o coeficientes de sensibilidad. Con medias ponderadas q̄, ȳ y `Q = Σw_i(q_i−q̄)²`:

```text
∂m_g/∂q_i = w_i[(y_i−ȳ) − 2m_g(q_i−q̄)] / Q
∂m_g/∂y_i = w_i(q_i−q̄) / Q

gq_i = ∂v_g/∂q_i = −2/m_g² · ∂m_g/∂q_i
gy_i = ∂v_g/∂y_i = −2/m_g² · ∂m_g/∂y_i

a_i = ∂q_i/∂d_i = d_i/√(d_i²+h²)
c_i = ∂q_i/∂h = h/√(d_i²+h²) − 1
```

De ahí salen los aportes en m/s:

```text
u_cinta = √Σ(gq_i · a_i · u_d)²
u_manos = √Σ(gq_i · c_i · u_h)²
u_sillas_fijas = |Σ(gq_i · a_i)| · u_s
u_sillas_independientes = √Σ(gq_i · a_i · u_s)²
```

Se usa una sola de las dos expresiones de sillas. Si el desplazamiento es común, se propaga conjuntamente; no se cuenta como un error nuevo e independiente en cada distancia. La lectura de cinta y la altura se consideran comunes a las repeticiones de una misma separación.

### Incertidumbre de detección

Para cada inicio, `a_t` es la mayor diferencia absoluta entre su tiempo central y las alternativas obtenidas con los umbrales 0,75; 1 y 1,5:

```text
u_inicio = a_t/√3
u_D² = u_A1² + u_A2² + u_B1² + u_B2²
```

Se suponen independientes los cuatro inicios. Para n repeticiones de una distancia:

```text
u_t_i = √Σ(u_D_de_cada_toma²) / n
u_deteccion = √Σ(gy_i · u_t_i)²
```

Esta sensibilidad al umbral no calibra la exactitud del detector. Si falta la referencia de alguna marca utilizada, el aporte de detección (`u_detection` en el código) queda desconocido y se muestra **«± pendiente»**; no se sustituye por cero.

### Dispersión adicional y margen final

La dispersión alrededor de la recta puede venir de los errores anteriores. Para no contarla dos veces, se añade solo el exceso sobre lo previsto por esas entradas mediante **estimación por momentos**.

El código forma:

```text
Cov_q = diag((a_i u_d)² + (c_i u_h)²) + Cov_sillas
Cov_y = diag(u_t_i²) + m_g² Cov_q
```

Con sillas fijas, `Cov_sillas[i,j] = a_i a_j u_s²`; con posiciones independientes solo conserva la diagonal `a_i² u_s²`. Esta matriz expresa qué errores varían juntos.

Sea `W = diag(w_i)`, `A = √W [1,q]`, `P = I − A·pinv(A)` y `e = √W(y−m_g q−b_g)`. `pinv` es la pseudoinversa y `tr` la suma de la diagonal:

```text
τ² = max(0, [eᵀe − tr(P √W Cov_y √W)] / tr(PW))
u_extra = √Σ(gy_i²) · √τ²
B_geometria = v_g − v_publicada

M = √(u_cinta² + u_manos² + u_sillas² + u_deteccion² + u_extra² + B_geometria²)
```

La presentación final es **`v_publicada ± M`**. El error estadístico `u_v_recta` no se suma otra vez entero. `B_geometria` representa el desplazamiento no aplicado al valor central; es distinto de la variación de altura entre tomas.

El campo exportado `margen_error_estimado_m_s` contiene M y se copia a `ajuste.error_mostrado`. El campo `sigma_speed` conserva el error estadístico. Si se llama al motor sin configuración de incertidumbre, no se calcula ese presupuesto y la presentación usa el error estadístico.

### Ejemplo de la sesión incluida

| Resultado o aporte            | m/s, aproximadamente |
| ----------------------------- | -------------------: |
| Velocidad del ajuste          |                334,9 |
| Error estadístico de la recta |                 6,47 |
| Cinta                         |                0,024 |
| Manos                         |                 1,30 |
| Sillas fijas                  |                0,009 |
| Detección                     |                15,20 |
| Dispersión adicional          |                    0 |
| Cambio geométrico no aplicado |                −1,15 |
| **Margen mostrado M**         |             **15,3** |

El resultado es **334,9 ± 15,3 m/s**. Es un margen modelado, no un intervalo con cobertura fija del 95 %. Quedan sin cuantificar sesgos del detector, diferencias de reloj, calibración de cinta y desviaciones respecto de la geometría supuesta.

## 9. Referencia por temperatura

`sound_math.reference_speed()` usa:

```text
v_referencia = 331,3 + 0,606·T
```

T está en °C y el resultado en m/s. La aplicación acepta temperaturas entre −20 y 40 °C para esta referencia aproximada. Si el campo está vacío, no calcula referencia. A 20 °C muestra 343,4 m/s.

La temperatura no interviene en las marcas, el ajuste experimental ni su margen M. Su incertidumbre tampoco se agrega a M: afectaría la comparación teórica.

## 10. Sesiones JSON

**Guardar sesión** conserva entradas, temperatura y parámetros; no incorpora el audio ni los resultados exportados. **Abrir sesión** valida que los archivos existan, recupera la configuración y deja el análisis pendiente.

Ejemplo de estructura con un par de los audios incluidos; el JSON completo contiene los seis pares:

```json
{
  "version": 2,
  "tipo": "dos_aplausos",
  "entradas": [
    {
      "archivo_a": "audios/A/3A.mp4",
      "archivo_b": "audios/B/3m2.m4a.mp4",
      "distancia_m": 3.0
    }
  ],
  "temperatura": "20.0",
  "config_incertidumbre": {
    "resolucion_distancia_m": 0.001,
    "altura_min_m": 0.38,
    "altura_max_m": 0.44,
    "margen_sillas_m": 0.03,
    "sillas_fijas": true
  }
}
```

- `marcas_a` y `marcas_b` son opcionales: cada una es una lista `[inicio1, inicio2]` en segundos. Omitirlas permite detectar automáticamente.
- A y B deben ser archivos diferentes. Una misma ruta no puede pertenecer a dos mediciones de la sesión.
- El campo antiguo `revisado` se ignora. Las sesiones del método de eco de un solo audio no son compatibles con esta interfaz.
- En JSON los decimales llevan **punto**, aunque los campos de entrada de la aplicación admitan coma.
- Para cambiar las fuentes de incertidumbre, editar `config_incertidumbre`, volver a abrir la sesión y analizar. La pestaña muestra los valores, pero no los edita.
- Si falta esa configuración, se usan los valores de `EXPERIMENT_CONFIG`. Esos valores corresponden a esta serie y deben revisarse para otro montaje.
- Las rutas relativas se resuelven desde la carpeta del JSON, independientemente de dónde se inicie el programa. También se admiten rutas absolutas de sesiones anteriores. Al guardar, se usan rutas relativas al destino del JSON; si un audio está en otra unidad de Windows, se conserva su ruta absoluta.

## 11. Archivos exportados

La interfaz crea una carpeta nueva en:

```text
<carpeta personal>/Documents/EcoLab/pares_FECHA_HORA_MICROSEGUNDOS/
```

Es exactamente `Path.home() / 'Documents' / 'EcoLab'`; se conserva ese nombre por compatibilidad. No se utiliza la carpeta `resultados` del proyecto ni se busca automáticamente una ubicación redirigida a OneDrive.

| Archivo o carpeta       | Contenido                                                                   |
| ----------------------- | --------------------------------------------------------------------------- |
| `mediciones.csv`        | Archivos A/B, distancia, TA, TB, D, velocidad, estado y avisos.             |
| `resumen.json`          | Mediciones, marcas, sensibilidad, grupos, ajuste, referencia y presupuesto. |
| `resumen.md`            | Resumen legible con las tablas y avisos.                                    |
| `incertidumbre.json`    | Configuración, aportes, supuestos y margen; si se solicita ese cálculo.     |
| `incertidumbre.md`      | Explicación del presupuesto.                                                |
| `ajuste.png`            | Puntos y recta; solo si hay un ajuste válido.                               |
| `senales/001.png`, etc. | Gráficos de cada par con los audios disponibles.                            |
| `wav/001_a.wav`, etc.   | Copias convertidas utilizadas para analizar.                                |

Las grabaciones originales permanecen intactas. Un archivo que falla puede dejar una fila sin medición y su diagnóstico, mientras los demás pares continúan.

## 12. Problemas habituales

| Problema                                  | Qué revisar                                                                                                          |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| No aparece la ventana al ejecutar código  | Ejecutar `src/paired_app.py` con el Python del entorno virtual; comprobar Tkinter y las dependencias.                 |
| No se encuentra FFmpeg                    | Comprobar `Get-Command ffmpeg` desde la misma terminal. Para compilar también tiene que estar en `PATH`.             |
| No abre el JSON                           | Comprobar sintaxis, `tipo`, rutas y que los audios estén disponibles.                                                |
| No detecta dos eventos                    | Revisar ruido, recortes y separación; ampliar el gráfico, usar marcas manuales o repetir la toma.                    |
| TA no supera a TB                         | Verificar que A corresponda al primer aplauso y B al segundo, y que las marcas correspondan al mismo ensayo.         |
| «Sin ajuste»                              | Tener al menos tres separaciones distintas con velocidad calculada y una pendiente positiva.                         |
| «± pendiente»                             | Alguna marca usada no tiene referencia suficiente para estimar su sensibilidad. Revisar los avisos de incertidumbre. |
| El ejecutable no se reemplaza al compilar | Cerrar todas las instancias de SonoLab antes de volver a ejecutar `build_exe.py`.                                    |
