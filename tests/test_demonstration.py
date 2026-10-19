"""Selección de tomas y exploración térmica sin alterar resultados."""
from copy import deepcopy
from pathlib import Path
import os
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from paired_app import SonoLabApp


def example_result():
    rows = []
    for i, (distance, delta) in enumerate([(3, 13), (3, 15), (4, 20), (5, 26)], 1):
        rows.append(dict(nombre=f'Toma {i}', archivo_a=f'a{i}.wav', archivo_b=f'b{i}.wav',
                         distancia_m=distance, delta_t_ms=delta, diferencia_s=delta/1000,
                         ta_s=1+delta/1000, tb_s=1., velocidad=2000*distance/delta,
                         estado='Procesado', grafico=None, detecciones={}, avisos=[]))
    return dict(filas=rows, grupos=[
        dict(distancia_m=3, n=2, delta_t_medio=.014, delta_t_sem=.001),
        dict(distancia_m=4, n=1, delta_t_medio=.020, delta_t_sem=None),
        dict(distancia_m=5, n=1, delta_t_medio=.026, delta_t_sem=None)],
        ajuste=dict(m=.006, b=-.004, velocidad=1000/3, sigma_velocidad=1.,
                    r2=1., ponderado=False, provisional=True),
        temperatura=16., teorica=340.996, salida=str(ROOT/'build'),
        grafico_ajuste=None, presupuesto_incertidumbre=None)


@unittest.skipIf(sys.platform.startswith('linux') and not os.environ.get('DISPLAY'),
                 'La interfaz necesita DISPLAY; ejecutar con xvfb-run en Linux sin escritorio.')
class DemonstrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = SonoLabApp()
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.app.update_idletasks()
        cls.app.destroy()

    def setUp(self):
        app = self.app
        if app.expanded_fit_window and app.expanded_fit_window.winfo_exists():
            app.expanded_fit_window.destroy()
        app.table.delete(*app.table.get_children())
        app.entries.clear()
        app.invalidate_results()
        self.result = example_result()
        for row in self.result['filas']:
            app.insert_pair({key: row[key] for key in ('archivo_a', 'archivo_b', 'distancia_m')})
        app.show_result(self.result)
        app.update()

    def test_table_selection_highlights_individual_instead_of_mean(self):
        app = self.app
        app.table.selection_set(list(app.entries)[1])
        app.update()
        self.assertEqual(list(app.fit_plot.selection_artist.get_xdata()), [3])
        self.assertEqual(list(app.fit_plot.selection_artist.get_ydata()), [15])
        self.assertIn('Medición 2', app.fit_plot.selection_text.get())
        self.assertEqual(self.result['grupos'][0]['delta_t_medio'], .014)
        self.assertEqual(app.tabs.select(), str(app.fit_panel))

    def test_failed_row_and_no_selection_clear_highlight(self):
        app = self.app
        row = self.result['filas'][1]
        row['velocidad'] = row['delta_t_ms'] = None
        row['ta_s'] = None
        app.show_result(self.result)
        app.table.selection_set(list(app.entries)[1])
        app.update()
        self.assertEqual(len(app.fit_plot.selection_artist.get_xdata()), 0)
        self.assertIn('sin medición válida', app.fit_plot.selection_text.get())
        app.table.selection_remove(*app.table.selection())
        app.update()
        self.assertEqual(len(app.fit_plot.selection_artist.get_xdata()), 0)

    def test_exploring_temperature_does_not_change_measured_fit_or_session(self):
        app = self.app
        before = deepcopy(self.result)
        temperature_field = app.temp.get()
        app.temperature_panel.set_temperature(16)
        speed16 = app.temperature_panel.exploration_marker.get_ydata()[0]
        app.temperature_panel.set_temperature(20)
        speed20 = app.temperature_panel.exploration_marker.get_ydata()[0]
        app.update()
        self.assertAlmostEqual(speed20-speed16, 2.424)
        self.assertEqual(list(app.temperature_panel.session_marker.get_xdata()), [16])
        self.assertEqual(self.result, before)
        self.assertEqual(app.temp.get(), temperature_field)

    def test_expanded_plot_tracks_selection_and_invalidated_results(self):
        app = self.app
        toplevel = tk.Toplevel
        def hidden_window(parent):
            window = toplevel(parent)
            window.withdraw()
            return window
        with patch('paired_app.tk.Toplevel', side_effect=hidden_window):
            app.open_fit_plot()
        app.table.selection_set(list(app.entries)[-1])
        app.update()
        self.assertEqual(list(app.expanded_fit_plot.selection_artist.get_xdata()), [5])
        app.invalidate_results()
        app.update()
        for plot in (app.fit_plot, app.expanded_fit_plot):
            self.assertEqual(len(plot.selection_artist.get_xdata()), 0)
        self.assertEqual(len(app.temperature_panel.session_marker.get_xdata()), 0)
        self.assertTrue(app.expand_fit_button.instate(['disabled']))

    def test_points_without_a_fit_and_session_without_temperature(self):
        result = self.result
        result.update(ajuste=None, temperatura=None, teorica=None)
        result['grupos'] = result['grupos'][:1]
        result['filas'] = result['filas'][:2]
        for iid in list(self.app.entries)[2:]:
            self.app.table.delete(iid)
            del self.app.entries[iid]
        self.app.show_result(result)
        self.app.update()
        self.assertEqual(list(self.app.fit_plot.selection_artist.get_ydata()), [13])
        self.assertEqual(len(self.app.temperature_panel.session_marker.get_xdata()), 0)
        self.assertIn('sin temperatura', self.app.temperature_panel.session_text.get())

    def test_help_navigation_and_reopening_preserve_measurements(self):
        app = self.app
        before = deepcopy(app.analysis_result)
        entries = deepcopy(app.entries)
        temperature = app.temp.get()
        with patch('paired_app.HelpGuide.deiconify'):
            app.show_help()
            guide = app.help_window
            app.show_help()
            self.assertIs(app.help_window, guide)
            self.assertTrue(guide.previous_button.instate(['disabled']))
            for index in range(1, len(guide.navigation)):
                guide.next_button.invoke()
                app.update()
                self.assertEqual(guide.page_index, index)
                self.assertEqual(guide.canvas.yview()[0], 0)
            self.assertTrue(guide.next_button.instate(['disabled']))
            guide.navigation[0].invoke()
            self.assertEqual(guide.page_index, 0)
            guide.close_button.invoke()
            self.assertFalse(guide.winfo_exists())
            self.assertTrue(app.winfo_exists())
            app.show_help()
            self.assertIsNot(app.help_window, guide)
            app.help_window.destroy()
        self.assertEqual(app.analysis_result, before)
        self.assertEqual(app.entries, entries)
        self.assertEqual(app.temp.get(), temperature)


if __name__ == '__main__':
    unittest.main()
