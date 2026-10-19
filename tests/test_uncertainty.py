"""Regresiones del presupuesto: excluir altura conserva las otras fuentes."""
import copy
from dataclasses import asdict
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sound_math import linear_fit
from uncertainty import EXPERIMENT_CONFIG, explain_uncertainty, uncertainty_budget, validate_config


def sample_result():
    d = np.arange(3., 9.)
    dt = 2*d/340 + np.array([.001, -.001, .0005, -.0005, -.001, .001])
    fit = linear_fit(d, dt)
    rows = []
    for distance, interval in zip(d, dt):
        detections = {}
        for side, sign in (('a', 1), ('b', -1)):
            markers = [1., 2.+sign*interval/2]
            detections[side] = dict(tiempos=markers,
                marcas_por_umbral=[[t-.0001, t, t+.0001] for t in markers])
        rows.append(dict(nombre=f'{distance:g} m', distancia_m=distance,
                         velocidad=2*distance/interval, detecciones=detections))
    return dict(ajuste=dict(asdict(fit), velocidad=fit.speed,
                           sigma_velocidad=fit.sigma_speed, ponderado=False),
                grupos=[dict(distancia_m=x, delta_t_medio=y, delta_t_sem=None)
                        for x, y in zip(d, dt)], filas=rows)


class HeightContributionTests(unittest.TestCase):
    def setUp(self):
        self.result = sample_result()
        self.config = dict(EXPERIMENT_CONFIG, incluir_altura=False)

    def test_legacy_sessions_keep_height_model(self):
        legacy = dict(EXPERIMENT_CONFIG)
        legacy.pop('incluir_altura')
        old_style = uncertainty_budget(self.result, legacy)
        explicit = uncertainty_budget(self.result, EXPERIMENT_CONFIG)
        self.assertEqual(old_style, explicit)
        self.assertGreater(old_style['contribuciones_m_s']['manos'], 0)
        self.assertTrue(old_style['escenario_geometrico']['incluido'])

    def test_excluded_height_cannot_change_remaining_budget(self):
        baseline = uncertainty_budget(self.result, self.config)
        changed = uncertainty_budget(self.result, dict(self.config, altura_min_m=1., altura_max_m=2.))
        self.assertEqual(baseline['contribuciones_m_s'], changed['contribuciones_m_s'])
        self.assertEqual(baseline['margen_error_estimado_m_s'], changed['margen_error_estimado_m_s'])
        self.assertEqual(baseline['contribuciones_m_s']['manos'], 0)
        self.assertEqual(baseline['escenario_geometrico']['cambio_respecto_publicado'], 0)
        self.assertIsNone(baseline['escenario_geometrico']['altura_central_m'])

    def test_tape_detection_and_additional_scatter_still_contribute(self):
        baseline = uncertainty_budget(self.result, self.config)
        self.assertGreater(baseline['contribuciones_m_s']['cinta'], 0)
        self.assertGreater(baseline['contribuciones_m_s']['deteccion'], 0)
        self.assertGreater(baseline['u_residual_adicional_m_s'], 0)
        coarse_tape = uncertainty_budget(self.result, dict(self.config, resolucion_distancia_m=.01))
        self.assertGreater(coarse_tape['contribuciones_m_s']['cinta'], baseline['contribuciones_m_s']['cinta'])
        ambiguous = copy.deepcopy(self.result)
        for row in ambiguous['filas']:
            for detection in row['detecciones'].values():
                detection['marcas_por_umbral'] = [[t-.01, t, t+.01] for t in detection['tiempos']]
        uncertain = uncertainty_budget(ambiguous, self.config)
        self.assertGreater(uncertain['margen_error_estimado_m_s'], baseline['margen_error_estimado_m_s'])

    def test_fixed_offset_cancels_but_repositioning_still_contributes(self):
        fixed = uncertainty_budget(self.result, self.config)
        moved = uncertainty_budget(self.result, dict(self.config, sillas_fijas=False))
        self.assertAlmostEqual(fixed['contribuciones_m_s']['sillas'], 0, places=10)
        self.assertGreater(moved['contribuciones_m_s']['sillas'], 0)

    def test_missing_detection_sensitivity_is_not_treated_as_zero(self):
        self.result['filas'][0]['detecciones']['a'].pop('marcas_por_umbral')
        budget = uncertainty_budget(self.result, self.config)
        self.assertIsNone(budget['contribuciones_m_s']['deteccion'])
        self.assertIsNone(budget['margen_error_estimado_m_s'])
        self.assertTrue(budget['deteccion_faltante'])

    def test_processing_sensitivity_is_not_replaced_by_narrow_threshold_range(self):
        baseline = uncertainty_budget(self.result, self.config)
        for row in self.result['filas']:
            for detection in row['detecciones'].values():
                detection['marcas_sensibilidad'] = [[t-.008, t, t+.008] for t in detection['tiempos']]
        processed = uncertainty_budget(self.result, self.config)
        self.assertGreater(processed['contribuciones_m_s']['deteccion'],
                           baseline['contribuciones_m_s']['deteccion']*50)
        self.assertIn('100, 150 y 250 Hz', ' '.join(processed['supuestos']))

    def test_report_and_no_fit_keep_selective_configuration(self):
        for result in (self.result, dict(self.result, ajuste=None)):
            budget = uncertainty_budget(result, self.config)
            text = explain_uncertainty(budget)
            self.assertIn('aporte excluido', text)
            self.assertNotIn('38–44', text)
            self.assertIn('Cinta', text)
            self.assertIn('Sillas', text)
            self.assertFalse(budget['config']['incluir_altura'])
        with self.assertRaises(ValueError):
            validate_config(None)
        with self.assertRaises(ValueError):
            validate_config(dict(self.config, incluir_altura='false'))


if __name__ == '__main__':
    unittest.main()
