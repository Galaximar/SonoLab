"""Interfaz de SonoLab para dos micrófonos y dos aplausos."""
from pathlib import Path
from datetime import datetime
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

from app import BaseWindow
from audio_io import parse_number
from demonstration import FitPlot, TemperaturePlot
from help_guide import HelpGuide
from two_claps import analyze_pairs, validate_entries
from uncertainty import EXPERIMENT_CONFIG, validate_config, explain_uncertainty, format_speed, describe_height


class PairDialog(simpledialog.Dialog):
    def __init__(self, parent, entry=None, detections=None):
        self.entry = entry or {}
        self.detections = detections or {}
        super().__init__(parent, 'Medición · dos micrófonos y dos aplausos')

    def body(self, master):
        self.fields = {}
        ttk.Label(master, text='A: junto al PRIMER aplauso. B: junto al SEGUNDO.\n'
                  'Ambos audios deben contener los mismos dos aplausos; no hace falta sincronizarlos.',
                  wraplength=670).grid(row=0, column=0, columnspan=3, pady=10, sticky='w')
        for row, (key, heading) in enumerate([('archivo_a', 'Audio A'), ('archivo_b', 'Audio B'),
                                              ('distancia_m', 'Separación (m)')], 1):
            ttk.Label(master, text=heading).grid(row=row, column=0, sticky='w', padx=5, pady=6)
            var = tk.StringVar(value=str(self.entry.get(key, '')))
            self.fields[key] = var
            ttk.Entry(master, textvariable=var, width=65 if row < 3 else 15).grid(row=row, column=1, sticky='w')
            if row < 3:
                ttk.Button(master, text='Elegir…', command=lambda v=var: self.choose_audio(v)).grid(row=row, column=2, padx=6)
        ttk.Label(master, text='Inicios en segundos dentro de cada archivo (opcional).\n'
                  'Dejá los dos campos de un audio vacíos para detectar automáticamente.\n'
                  'Podés corregirlos después de inspeccionar los gráficos.', wraplength=650).grid(
                      row=4, column=0, columnspan=3, sticky='w', pady=(16, 8))
        for row, side in enumerate(('a', 'b'), 5):
            ttk.Label(master, text=f'Audio {side.upper()}').grid(row=row, column=0, sticky='w', padx=5)
            frame = ttk.Frame(master)
            frame.grid(row=row, column=1, sticky='w', pady=5)
            markers = self.entry.get(f'marcas_{side}') or self.detections.get(side, {}).get('tiempos', [])
            for k in range(2):
                ttk.Label(frame, text=f'Aplauso {k+1}:').pack(side='left', padx=5)
                var = tk.StringVar(value=f'{markers[k]:.6f}' if len(markers) == 2 else '')
                self.fields[f'{side}{k}'] = var
                ttk.Entry(frame, textvariable=var, width=12).pack(side='left')
        ttk.Label(master, text='Al cambiar archivos o marcas, volvé a comprobar las selecciones. Una velocidad cercana\n'
                  'a la esperada no demuestra que los inicios estén bien.', wraplength=670).grid(
                      row=7, column=0, columnspan=3, sticky='w', pady=(12, 0))

    def choose_audio(self, var):
        path = filedialog.askopenfilename(parent=self, title='Elegir audio del micrófono', filetypes=[
            ('Audio y video', '*.wav *.mp4 *.m4a *.mpeg *.mp3 *.aac *.flac *.ogg *.opus *.webm *.mov'),
            ('Todos', '*.*')])
        if path:
            var.set(path)
            side = 'a' if var is self.fields['archivo_a'] else 'b'
            for k in range(2):
                self.fields[f'{side}{k}'].set('')

    def validate(self):
        try:
            e = {k: self.fields[k].get().strip() for k in ('archivo_a', 'archivo_b')}
            for k in e:
                if not e[k] or not Path(e[k]).is_file():
                    raise ValueError('Elegí dos archivos existentes.')
            e['distancia_m'] = parse_number(self.fields['distancia_m'].get())
            for side in ('a', 'b'):
                fields = [self.fields[f'{side}{k}'].get().strip() for k in range(2)]
                if any(fields):
                    if not all(fields):
                        raise ValueError('Completá ambos inicios de ese audio o dejá ambos vacíos.')
                    markers = [parse_number(t, 'Inicio') for t in fields]
                    if not 0 <= markers[0] < markers[1]:
                        raise ValueError('Los inicios deben estar ordenados y ser positivos o cero.')
                    e[f'marcas_{side}'] = markers
            self.result = validate_entries([e])[0]
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror('Revisá la medición', str(exc), parent=self)
            return False


class SonoLabApp(BaseWindow):
    def build_widgets(self):
        super().build_widgets()
        self.uncertainty_config = dict(EXPERIMENT_CONFIG)
        self.title('SonoLab · Velocidad del sonido / dos micrófonos')
        self.add.configure(text='+ Agregar par A/B')
        self.edit.configure(text='Editar / revisar marcas')
        self.go.configure(text='Analizar pares')
        cols = [('a', 'Audio A', 170), ('b', 'Audio B', 170), ('d', 'Separación (m)', 105),
                ('estado', 'Estado', 105), ('ta', 'TA (s)', 105), ('tb', 'TB (s)', 105),
                ('dt', 'TA−TB (ms)', 105), ('v', 'v (m/s)', 100)]
        self.table.configure(columns=[c[0] for c in cols])
        for key, heading, width in cols:
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, anchor='w' if key in ('a', 'b', 'estado') else 'center')
        self.table.bind('<Double-1>', lambda e: self.edit_pair())
        self.status.set('Agregá dos audios del mismo ensayo y la separación entre micrófonos.')
        self.notice.set('A está junto al primer aplauso y B junto al segundo. Cada archivo debe contener ambos aplausos.')
        self.detail.set('Después del análisis, revisá los cuatro inicios y sus ampliaciones.')
        self.tabs.tab(0, text='Audios A y B · marcas')
        self.fit_panel = ttk.Frame(self.tabs)
        self.tabs.insert(1, self.fit_panel, text='Ajuste lineal · puntos y recta')
        self.expanded_fit_window = None
        header = ttk.Frame(self.fit_panel)
        header.pack(fill='x', padx=8, pady=6)
        ttk.Label(header, text='Cómo se obtiene la velocidad de la recta',
                  font=('Segoe UI', 11, 'bold')).pack(side='left')
        self.expand_fit_button = ttk.Button(header, text='Ampliar gráfico',
                                        command=self.open_fit_plot, state='disabled')
        self.expand_fit_button.pack(side='right')
        content = ttk.Frame(self.fit_panel)
        content.pack(fill='both', expand=True)
        explanation = ttk.Frame(content)
        explanation.pack(side='right', fill='y', padx=8, pady=6)
        self.fit_explanation = tk.Text(explanation, width=39, height=6, wrap='word',
                                        font=('Segoe UI', 10), relief='flat', padx=10, pady=8)
        self.fit_explanation.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(explanation, command=self.fit_explanation.yview)
        scroll.pack(side='right', fill='y')
        self.fit_explanation.configure(yscrollcommand=scroll.set)
        self.fit_plot = FitPlot(content)
        self.fit_plot.pack(side='left', fill='both', expand=True)
        self.fit_plot.canvas.get_tk_widget().bind('<Double-1>', lambda e: self.open_fit_plot())
        self.update_fit_panel()
        self.temperature_panel = TemperaturePlot(self.tabs)
        self.tabs.insert(2, self.temperature_panel, text='Temperatura · referencia')
        self.uncertainty_panel = ttk.Frame(self.tabs)
        self.tabs.add(self.uncertainty_panel, text='Incertidumbre · fuentes de error')
        error_frame = ttk.Frame(self.uncertainty_panel)
        error_frame.pack(fill='both', expand=True)
        self.uncertainty_text = tk.Text(error_frame, wrap='word', height=6, relief='flat',
                                         font=('Segoe UI', 11), padx=14, pady=10)
        self.uncertainty_text.pack(side='left', fill='both', expand=True)
        error_scrollbar = ttk.Scrollbar(error_frame, command=self.uncertainty_text.yview)
        error_scrollbar.pack(side='right', fill='y')
        self.uncertainty_text.configure(yscrollcommand=error_scrollbar.set)
        self.update_uncertainty()
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('end', HELP_TEXT)
        self.text.configure(state='disabled')
        # Corrige el titulo de la tarjeta heredada sin cambiar el visor compartido.
        for child in self.metrics[1].master.winfo_children():
            if isinstance(child, ttk.Label) and child is not self.metrics[1]:
                child.configure(text='PARES CALCULADOS / TOTAL')
        self.full_tab_titles = [self.tabs.tab(tab, 'text') for tab in self.tabs.tabs()]
        self.compact_layout = None
        self.narrow_tabs = None
        self.bind('<Configure>', self.adapt_demo_layout, add='+')

    def adapt_demo_layout(self, event):
        if event.widget is not self:
            return
        compact = event.height < 800
        if compact != self.compact_layout:
            self.compact_layout = compact
            if compact:
                self.title_label.pack_forget()
                self.subtitle_label.pack_forget()
                self.progress_bar.pack_forget()
            else:
                self.title_label.pack(anchor='w', before=self.header_controls)
                self.subtitle_label.pack(anchor='w', pady=(0, 16), before=self.header_controls)
                self.progress_bar.pack(fill='x', pady=(0, 12), before=self.cards_frame)
            self.table.configure(height=2 if compact else 4)
        narrow = event.width < 1180
        if narrow != self.narrow_tabs:
            self.narrow_tabs = narrow
            titles = ['Audios A/B · marcas', 'Ajuste lineal', 'Temperatura',
                      'Resumen', 'Incertidumbre'] if narrow else self.full_tab_titles
            for tab, title in zip(self.tabs.tabs(), titles):
                self.tabs.tab(tab, text=title)
        self.notice_label.configure(wraplength=max(400, event.width-60))

    def show_help(self):
        window = getattr(self, 'help_window', None)
        if window is None or not window.winfo_exists():
            self.help_window = HelpGuide(self)
        self.help_window.deiconify()
        self.help_window.lift()
        self.help_window.focus_set()

    def update_uncertainty(self):
        p = (self.analysis_result or {}).get('presupuesto_incertidumbre')
        c = self.uncertainty_config
        if p:
            text = explain_uncertainty(p)
        else:
            text = (
                f"Graduación de cinta: {100*c['resolucion_distancia_m']:g} cm. "
                + describe_height(c) + '\n\n'
                + 'Analizá los pares para evaluar estas fuentes. '
                f"Sillas: ±{100*c['margen_sillas_m']:g} cm en la separación total. "
                'El ± combinará las fuentes modeladas.')
        self.uncertainty_text.configure(state='normal')
        self.uncertainty_text.delete('1.0', 'end')
        self.uncertainty_text.insert('1.0', text)
        self.uncertainty_text.configure(state='disabled')
        self.uncertainty_text.yview_moveto(0)

    def update_fit_panel(self):
        r = self.analysis_result or {}
        fit_result = r.get('ajuste')
        self.fit_plot.set_result(r)
        if self.expanded_fit_window and self.expanded_fit_window.winfo_exists():
            self.expanded_fit_plot.set_result(r)
        self.expand_fit_button.configure(state='normal' if r.get('grupos') else 'disabled')
        text = ('1. LOS PUNTOS\nHorizontal: distancia entre micrófonos. Vertical: TA−TB, '
                 'la diferencia entre los intervalos de ambos audios, en milisegundos. '
                 'Si hay varias tomas a una distancia, se usa su promedio. '
                 'El círculo naranja señala la toma individual seleccionada en la tabla.\n\n'
                 '2. LA RECTA\nEl ajuste lineal por mínimos cuadrados busca la recta que '
                 'mejor pasa entre los puntos: minimiza la suma de las separaciones '
                 'verticales al cuadrado. Si hay errores de las medias disponibles '
                 'para todas las distancias, los usa como pesos.\n\n')
        if fit_result:
            text += (f"3. RESULTADO\nLa recta sube {fit_result['m']*1000:.4f} milisegundos por cada metro. "
                      'Esa inclinación se llama pendiente.\n\n'
                      f"TA−TB (ms) = {fit_result['m']*1000:.4f} × d (m) {fit_result['b']*1000:+.4f}\n\n"
                      'El método relaciona la pendiente con 2/v. Pasándola a segundos:\n'
                      f"v = 2 / {fit_result['m']:.8f} = {fit_result['velocidad']:.1f} m/s\n\n"
                      'La velocidad sale de cómo aumenta el tiempo con la distancia; '
                      'no del promedio de las velocidades individuales. La recta puede '
                      'tener un desplazamiento b y no se obliga a pasar por cero.\n\n'
                      'AJUSTE PROVISIONAL · TODAS LAS MEDICIONES CALCULADAS\n'
                      f"{format_speed(fit_result)}\n"
                      'El margen ± combina las fuentes del experimento según los supuestos de la pestaña Incertidumbre. '
                      'No tiene cobertura fija ni incluye sesgos desconocidos de los equipos de grabación.\n'
                      f"Error estadístico de la recta, por separado: {fit_result['sigma_velocidad']:.1f} m/s.")
        else:
            text += ('3. LA VELOCIDAD\nv = 2 / pendiente, usando segundos por metro.\n\n'
                      'Analizá pares en al menos tres distancias distintas para obtener '
                      'un ajuste. También se requiere una pendiente positiva.')
        self.fit_explanation.configure(state='normal')
        self.fit_explanation.delete('1.0', 'end')
        self.fit_explanation.insert('1.0', text)
        self.fit_explanation.configure(state='disabled')
        self.fit_explanation.yview_moveto(0)
        self.highlight_fit_selection()

    def highlight_fit_selection(self):
        row, number = None, None
        selection = self.table.selection()
        if self.analysis_result and selection:
            iid = selection[0]
            row = self.results_by_id.get(iid)
            number = list(self.entries).index(iid)+1
        self.fit_plot.set_selection(row, number)
        if self.expanded_fit_window and self.expanded_fit_window.winfo_exists():
            self.expanded_fit_plot.set_selection(row, number)

    def show_fit(self):
        self.tabs.select(self.fit_panel)

    def open_fit_plot(self):
        if not self.analysis_result or not self.analysis_result.get('grupos'):
            return
        if self.expanded_fit_window and self.expanded_fit_window.winfo_exists():
            self.expanded_fit_window.lift()
            return
        self.expanded_fit_window = tk.Toplevel(self)
        self.expanded_fit_window.title('SonoLab · Ajuste y medición seleccionada')
        self.expanded_fit_window.geometry('1000x650')
        self.expanded_fit_plot = FitPlot(self.expanded_fit_window)
        toolbar = NavigationToolbar2Tk(self.expanded_fit_plot.canvas, self.expanded_fit_window,
                                       pack_toolbar=False)
        toolbar.pack(side='bottom', fill='x')
        self.expanded_fit_plot.pack(fill='both', expand=True)
        self.expanded_fit_plot.set_result(self.analysis_result)
        self.highlight_fit_selection()

    def insert_pair(self, entry):
        self.counter += 1
        iid = str(self.counter)
        self.entries[iid] = dict(entry)
        self.table.insert('', 'end', iid=iid)
        self.refresh_row(iid)

    def select_measurement(self, event=None):
        super().select_measurement(event)
        self.highlight_fit_selection()
        if not self.analysis_result or not self.table.selection():
            return
        iid = self.table.selection()[0]
        measurement_number = list(self.entries).index(iid)+1
        self.detail.set(f'Medición {measurement_number} de {len(self.entries)}. '
                         'Arriba: los dos audios completos. Medio: primer aplauso. Abajo: segundo aplauso. '
                         'Seleccioná otra fila de la tabla para ver otra medición. Doble clic para ampliar.')

    def refresh_row(self, iid, f=None):
        e = self.entries[iid]
        f = f or {}
        def fmt(k, dec):
            return f'{f[k]:.{dec}f}' if f.get(k) is not None else '—'
        self.table.item(iid, values=(Path(e['archivo_a']).name, Path(e['archivo_b']).name,
            f"{e['distancia_m']:g}", f.get('estado', 'Pendiente'), fmt('ta_s', 6), fmt('tb_s', 6),
            fmt('delta_t_ms', 3), fmt('velocidad', 1)), tags=('fallo',) if f and f.get('velocidad') is None else ())

    def invalidate_results(self):
        self.analysis_result = None
        self.update_fit_panel()
        self.temperature_panel.set_result(None)
        self.update_uncertainty()
        self.original_image = None
        self.image_path = None
        self.redraw_image()
        self.open_results_button.configure(state='disabled')
        self.view_fit_button.configure(state='disabled')
        for label in self.metrics:
            label.configure(text='—')
        for iid in self.entries:
            self.refresh_row(iid)
        self.notice.set('Lista actualizada. Volvé a analizar; se conservarán los resultados anteriores.')
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('end', 'Pendiente de análisis.\n\n'+HELP_TEXT)
        self.text.configure(state='disabled')

    def add_pair(self):
        if self.busy:
            return
        dialog = PairDialog(self)
        if dialog.result:
            try:
                validate_entries([*self.entries.values(), dialog.result])
            except ValueError as exc:
                messagebox.showerror('Par repetido', str(exc), parent=self)
                return
            self.insert_pair(dialog.result)
            self.invalidate_results()

    def edit_pair(self):
        if self.busy or not self.table.selection():
            return
        iid = self.table.selection()[0]
        f = self.results_by_id.get(iid, {}) if self.analysis_result else {}
        dialog = PairDialog(self, self.entries[iid], f.get('detecciones'))
        if dialog.result:
            try:
                validate_entries([dialog.result if k == iid else e for k, e in self.entries.items()])
            except ValueError as exc:
                messagebox.showerror('Par repetido', str(exc), parent=self)
                return
            self.entries[iid] = dialog.result
            self.invalidate_results()

    def analyze(self):
        if self.busy:
            return
        try:
            entries = validate_entries(list(self.entries.values()))
            uncertainty_config = validate_config(self.uncertainty_config)
            temp = parse_number(self.temp.get(), 'Temperatura') if self.temp.get().strip() else None
            if temp is not None and not -20 <= temp <= 40:
                raise ValueError('Temperatura entre −20 y 40 °C o campo vacío.')
        except (ValueError, KeyError) as exc:
            messagebox.showerror('Revisá los datos', str(exc), parent=self)
            return
        self.invalidate_results()
        self.set_busy(True)
        output = Path.home()/'Documents'/'EcoLab'/datetime.now().strftime('pares_%Y-%m-%d_%H-%M-%S_%f')
        def worker():
            try:
                r = analyze_pairs(entries, output, temp,
                    lambda i, n, msg: self.events.put(('progreso', (i, n, msg))),
                    uncertainty_config=uncertainty_config)
                self.events.put(('resultado', r))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def show_result(self, r):
        self.analysis_result = r
        self.results_by_id = dict(zip(self.entries, r['filas']))
        for iid, f in self.results_by_id.items():
            self.refresh_row(iid, f)
        fit_result = r['ajuste']
        for child in self.metrics[0].master.winfo_children():
            if isinstance(child, ttk.Label) and child is not self.metrics[0]:
                kind = 'MARGEN ESTIMADO' if fit_result and 'error_mostrado' in fit_result else 'ERROR ESTADÍSTICO'
                child.configure(text=('AJUSTE PROVISIONAL' if fit_result and fit_result.get('provisional') else 'VELOCIDAD DEL AJUSTE')+' · '+kind)
        self.metrics[0].configure(text=format_speed(fit_result))
        self.metrics[1].configure(text=f"{sum(f['velocidad'] is not None for f in r['filas'])} / {len(r['filas'])}")
        self.metrics[2].configure(text=f"{r['teorica']:.1f} m/s" if r['teorica'] is not None else 'Sin temperatura')
        if r.get('presupuesto_incertidumbre'):
            self.notice.set('Cálculo del error: ± = √(cinta² + manos² + sillas² + detección² + '
                           'dispersión adicional² + desplazamiento geométrico²). '
                           'Todos los aportes se expresan en m/s.')
        else:
            self.notice.set('Cálculo del error estadístico: σv = 2 × σm / m², '
                           'donde m es la pendiente y σm su error estándar.')
        self.status.set('Análisis terminado · editá una fila para revisar sus marcas')
        self.open_results_button.configure(state='normal')
        self.view_fit_button.configure(state='normal' if r['grafico_ajuste'] else 'disabled')
        lines = ['DOS APLAUSOS · RESULTADOS', '', f"Carpeta: {r['salida']}", '',
                 'TA = A2 − A1; TB = B2 − B1; v = 2d / (TA − TB).', '']
        for i, f in enumerate(r['filas'], 1):
            lines.extend([f"Par {i}: {f['nombre']}", f"Separación: {f['distancia_m']:g} m · {f['estado']}"])
            for side, det in f['detecciones'].items():
                lines.append(f"{side.upper()}: inicios {det['tiempos'][0]:.6f} y {det['tiempos'][1]:.6f} s ({det['origen']})")
            if f['velocidad'] is not None:
                lines.append(f"TA={f['ta_s']:.6f} s; TB={f['tb_s']:.6f} s; diferencia={f['delta_t_ms']:.3f} ms; v={f['velocidad']:.2f} m/s")
            elif f['ta_s'] is not None and f['tb_s'] is not None:
                lines.append(f"TA={f['ta_s']:.6f} s; TB={f['tb_s']:.6f} s; diferencia={f['delta_t_ms']:.3f} ms; sin velocidad válida")
            lines.extend([*f['avisos'], ''])
        if fit_result:
            lines.extend([f"Ajuste provisional: {format_speed(fit_result, 2)} ({fit_result.get('tipo_error', 'error estadístico')})",
                          f"Pendiente: {fit_result['m']*1000:.4f} ms/m; intercepto: {fit_result['b']*1000:.4f} ms; R²: {fit_result['r2']:.6f}"])
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('end', '\n'.join(lines))
        self.text.configure(state='disabled')
        if self.entries:
            self.table.selection_set(next(iter(self.entries)))
            self.select_measurement()
        self.update_fit_panel()
        self.temperature_panel.set_result(r)
        self.update_uncertainty()
        if fit_result:
            self.show_fit()

    def save_session(self):
        if self.busy:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.json', filetypes=[('Sesión de pares', '*.json')])
        if path:
            try:
                base = Path(path).resolve().parent
                entries = []
                for entry in self.entries.values():
                    saved_entry = dict(entry)
                    for key in ('archivo_a', 'archivo_b'):
                        try:
                            saved_entry[key] = Path(os.path.relpath(entry[key], base)).as_posix()
                        except ValueError:
                            # Windows no puede expresar una ruta relativa entre unidades.
                            saved_entry[key] = str(Path(entry[key]).resolve())
                    entries.append(saved_entry)
                Path(path).write_text(json.dumps(dict(version=2, tipo='dos_aplausos',
                    entradas=entries, temperatura=self.temp.get(),
                    config_incertidumbre=self.uncertainty_config), ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('No se pudo guardar', str(exc), parent=self)

    def load_session(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[('Sesión de pares', '*.json')])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if data.get('tipo') != 'dos_aplausos':
                raise ValueError('Esta sesión no es del método de dos aplausos. Las sesiones antiguas de eco usan un solo audio.')
            new_entries = validate_entries(data['entradas'], Path(path).resolve().parent) if data['entradas'] else []
            config = data.get('config_incertidumbre', EXPERIMENT_CONFIG)
            uncertainty_config = validate_config(config)
            for e in new_entries:
                for key in ('archivo_a', 'archivo_b'):
                    if not Path(e[key]).is_file():
                        raise ValueError(f"No se encuentra {e[key]}")
            for iid in list(self.entries):
                self.table.delete(iid)
            self.entries.clear()
            for e in new_entries:
                self.insert_pair(e)
            self.temp.delete(0, 'end')
            self.temp.insert(0, data.get('temperatura', ''))
            self.uncertainty_config = uncertainty_config
            self.invalidate_results()
        except (ValueError, OSError, TypeError, KeyError) as exc:
            messagebox.showerror('No se pudo abrir la sesión', str(exc), parent=self)


HELP_TEXT = '''Cada medición usa dos micrófonos separados y un audio por micrófono. Ambos deben registrar los mismos dos aplausos: primero cerca de A y después cerca de B.

1. Cargá los audios con «Agregar par A/B» e indicá la separación entre los micrófonos.
2. Pulsá «Analizar pares». El programa detecta los aplausos y calcula los tiempos y la velocidad.
3. Seleccioná una fila para ver sus dos audios. Los gráficos inferiores amplían cada aplauso.
4. Repetí en al menos tres distancias distintas para obtener la velocidad del ajuste y su margen ±.

«Ajuste lineal»: muestra los puntos y la recta; el círculo naranja sigue la fila seleccionada.
«Temperatura»: permite explorar la velocidad teórica y comparar 16 y 20 °C sin cambiar el ajuste medido.
«Incertidumbre»: explica cómo se calcula el ± y muestra los aportes de cada fuente de error.
«Archivo»: permite guardar o abrir una sesión JSON.'''


def main():
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    app = SonoLabApp()
    if len(sys.argv) == 4 and sys.argv[1] == '--smoke-test':
        app.withdraw()
        try:
            data = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
            entries = data['entradas'] if isinstance(data, dict) else data
            entries = validate_entries(entries, Path(sys.argv[2]).resolve().parent)
            config = data.get('config_incertidumbre', EXPERIMENT_CONFIG) if isinstance(data, dict) else EXPERIMENT_CONFIG
            app.uncertainty_config = validate_config(config)
            for e in entries:
                app.insert_pair(e)
            temperature = data.get('temperatura') if isinstance(data, dict) else None
            temperature = temperature if temperature is not None and str(temperature).strip() else None
            if temperature is not None:
                app.temp.insert(0, str(temperature))
            r = analyze_pairs(entries, sys.argv[3], temperature=temperature,
                              uncertainty_config=app.uncertainty_config)
            app.show_result(r)
            app.update()
            app.show_fit()
            app.update()
            for iid, row in app.results_by_id.items():
                app.table.selection_set(iid)
                app.select_measurement()
                if row['velocidad'] is not None:
                    assert list(app.fit_plot.selection_artist.get_xdata()) == [row['distancia_m']]
                    assert list(app.fit_plot.selection_artist.get_ydata()) == [row['delta_t_ms']]
            app.tabs.select(app.temperature_panel)
            app.temperature_panel.set_temperature(20)
            app.update()
            assert abs(app.temperature_panel.exploration_marker.get_ydata()[0]-343.42) < 1e-9
            app.help_window = HelpGuide(app)
            for index in range(len(app.help_window.navigation)):
                app.help_window.show_page(index)
                app.update()
            app.help_window.destroy()
            (Path(sys.argv[3])/'smoke-ok.txt').write_text(
                'Dos aplausos: conversión, cálculo, exportación, selección en ajuste y curva térmica OK.', encoding='utf-8')
        finally:
            app.destroy()
        return
    app.mainloop()


if __name__ == '__main__':
    main()
