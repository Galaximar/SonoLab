"""Gráficos interactivos de demostración; no modifican el análisis experimental."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sound_math import reference_speed


TEAL = '#087f75'
ORANGE = '#c65b10'


def chart(parent):
    figure = Figure(figsize=(6, 2.8), dpi=100, layout='constrained')
    axes = figure.add_subplot()
    canvas = FigureCanvasTkAgg(figure, master=parent)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    return figure, axes, canvas


def style_axes(axes):
    axes.tick_params(labelsize=9)
    axes.grid(alpha=.18)
    axes.spines[['top', 'right']].set_visible(False)


class FitPlot(ttk.Frame):
    """La recta usa los grupos; el resaltado siempre usa la toma individual."""
    def __init__(self, parent):
        super().__init__(parent)
        self.selection_text = tk.StringVar(value='Seleccioná una fila después de analizar.')
        ttk.Label(self, textvariable=self.selection_text, wraplength=740,
                  foreground=ORANGE).pack(fill='x', padx=10, pady=4)
        self.figure, self.axes, self.canvas = chart(self)
        self.set_result(None)

    def set_result(self, result):
        self.axes.clear()
        style_axes(self.axes)
        groups = (result or {}).get('grupos', [])
        fit = (result or {}).get('ajuste')
        self.axes.set(xlabel='Separación entre micrófonos (m)', ylabel='TA − TB (ms)')
        if groups:
            repeated = any(g['n'] > 1 for g in groups)
            if repeated:
                rows = [r for r in result['filas'] if r.get('velocidad') is not None]
                self.axes.plot([r['distancia_m'] for r in rows],
                               [r['delta_t_ms'] for r in rows], '.', color='#8496a3',
                               markersize=5, label='Tomas individuales')
            self.axes.errorbar([g['distancia_m'] for g in groups],
                              [g['delta_t_medio']*1000 for g in groups],
                              yerr=[(g['delta_t_sem'] or 0)*1000 for g in groups],
                              fmt='o', capsize=4, color=TEAL, markersize=5,
                              label='Promedios por distancia' if repeated else 'Mediciones')
            if fit:
                xx = [0, max(g['distancia_m'] for g in groups)*1.05]
                self.axes.plot(xx, [(fit['m']*x+fit['b'])*1000 for x in xx],
                               color='#427caf', label='Recta ajustada')
            else:
                self.axes.set_title('Sin ajuste válido todavía', fontsize=10)
        else:
            self.axes.text(.5, .5, 'Analizá los pares para mostrar sus puntos.',
                           transform=self.axes.transAxes, ha='center', color='#567083')
        self.selection_artist, = self.axes.plot([], [], 'o', markerfacecolor='none',
                                                markeredgecolor=ORANGE, markeredgewidth=2.5,
                                                markersize=12, zorder=10,
                                                label='Medición seleccionada')
        if groups:
            self.axes.legend(loc='upper left', fontsize=8)
        if self.canvas.toolbar:
            self.canvas.toolbar.update()
        self.set_selection(None)

    def set_selection(self, row, number=None):
        self.selection_artist.set_data([], [])
        if row is None:
            self.selection_text.set('Seleccioná una fila después de analizar.')
        elif row.get('velocidad') is None or row.get('delta_t_ms') is None:
            self.selection_text.set(f'Medición {number}: sin medición válida; no tiene punto en el ajuste.')
        else:
            d, dt = row['distancia_m'], row['delta_t_ms']
            self.selection_artist.set_data([d], [dt])
            name = Path(row.get('archivo_a', '')).name
            self.selection_text.set(f'Medición {number} · {name} · {d:g} m · ΔT = {dt:.3f} ms')
        self.canvas.draw_idle()


class TemperaturePlot(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=10, pady=(8, 3))
        ttk.Label(controls, text='Explorar temperatura:').pack(side='left')
        self.temperature = tk.DoubleVar(value=20)
        self.scale = ttk.Scale(controls, from_=-20, to=40, variable=self.temperature,
                               command=self.update_temperature)
        self.scale.pack(side='left', fill='x', expand=True, padx=10)
        self.value_text = tk.StringVar()
        ttk.Label(controls, textvariable=self.value_text, width=28).pack(side='left')
        for t in (16, 20):
            ttk.Button(controls, text=f'{t} °C', command=lambda value=t: self.set_temperature(value)).pack(side='left', padx=3)
        self.session_text = tk.StringVar(value='Analizá una sesión para marcar su temperatura en la curva.')
        ttk.Label(self, textvariable=self.session_text, wraplength=1100).pack(fill='x', padx=10, pady=3)
        ttk.Label(self, text='Modelo aproximado para aire seco: v = 331,3 + 0,606·T. '
                  'De 16 a 20 °C: +2,424 m/s. El control solo explora la referencia teórica.',
                  wraplength=1100).pack(fill='x', padx=10, pady=(0, 4))
        self.figure, self.axes, self.canvas = chart(self)
        style_axes(self.axes)
        self.axes.plot([-20, 40], [reference_speed(-20), reference_speed(40)],
                       color=TEAL, label='Referencia teórica')
        self.axes.set(xlabel='Temperatura (°C)', ylabel='v (m/s)',
                      xlim=(-21, 41), ylim=(317, 358))
        self.exploration_marker, = self.axes.plot([], [], 'o', color=ORANGE,
                                                markersize=7, label='Temperatura explorada')
        self.session_marker, = self.axes.plot([], [], 'o', markerfacecolor='none',
                                            markeredgecolor='#427caf', markeredgewidth=2,
                                            markersize=13, label='Temperatura del análisis')
        self.axes.legend(loc='upper left', fontsize=8)
        self.update_temperature()

    def set_temperature(self, value):
        self.temperature.set(value)
        self.update_temperature()

    def update_temperature(self, _value=None):
        temperature = round(self.temperature.get(), 1)
        speed = reference_speed(temperature)
        self.value_text.set(f'{temperature:.1f} °C → {speed:.3f} m/s')
        self.exploration_marker.set_data([temperature], [speed])
        self.canvas.draw_idle()

    def set_result(self, result):
        temperature = (result or {}).get('temperatura')
        self.session_marker.set_data([], [])
        if temperature is None:
            self.session_text.set('Análisis sin temperatura registrada.' if result else
                                  'Analizá una sesión para marcar su temperatura en la curva.')
        else:
            temperature = float(temperature)
            speed = reference_speed(temperature)
            self.session_marker.set_data([temperature], [speed])
            self.session_text.set(f'Temperatura del análisis: {temperature:g} °C · '
                                  f'Referencia: {speed:.3f} m/s. La velocidad medida se muestra en la tarjeta superior.')
            self.set_temperature(temperature)
        self.canvas.draw_idle()
