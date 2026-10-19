"""Frentes conocidos: recuperarlos sin editar muestras ni ocultar ambigüedad."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from two_claps import detect_claps, measure_audio


def signal(fs=48000, rumble=True, onsets=(.6, 1.6)):
    rng = np.random.default_rng(81)
    time = np.arange(round(2.4*fs))/fs
    x = rng.normal(0, .0001, len(time))
    for onset in onsets:
        ix = time >= onset
        x[ix] += .8*rng.normal(size=ix.sum())*np.exp(-(time[ix]-onset)/.012)
    if rumble:
        x += .07*np.cos(2*np.pi*60*(time-1.56))*np.exp(-((time-1.56)/.009)**2)
    return x


class AutomaticRumbleTests(unittest.TestCase):
    def test_clean_claps_are_unchanged(self):
        for fs in (16000, 48000):
            x = signal(fs, rumble=False)
            self.assertEqual(detect_claps(x, fs), detect_claps(x, fs, reduce_rumble=False))

    def test_known_onset_recovered_at_two_sample_rates(self):
        for fs in (16000, 48000):
            x = signal(fs)
            before = x.copy()
            raw = detect_claps(x, fs, reduce_rumble=False)
            corrected = detect_claps(x, fs)
            self.assertGreater(1.6-raw['tiempos'][1], .030)
            self.assertLess(abs(corrected['tiempos'][1]-1.6), .001)
            self.assertEqual(corrected['tiempos'][0], raw['tiempos'][0])
            np.testing.assert_array_equal(x, before)
            self.assertTrue(corrected['procesamiento_automatico']['muestras_del_inicio_conservadas'])

    def test_gain_and_time_shift_do_not_choose_different_events(self):
        fs = 48000
        original = signal(fs)
        expected = detect_claps(original, fs)['tiempos']
        for gain in (.05, .5, 2.):
            actual = detect_claps(original*gain, fs)['tiempos']
            np.testing.assert_allclose(actual, expected, atol=1/fs, rtol=0)
        shifted = np.r_[np.zeros(round(.3*fs)), original]
        actual = detect_claps(shifted, fs)['tiempos']
        np.testing.assert_allclose(actual, np.array(expected)+.3, atol=1/fs, rtol=0)

    def test_processing_variants_are_included_in_sensitivity(self):
        detection = detect_claps(signal(), 48000)
        variants = detection['procesamiento_automatico']['variantes']
        self.assertEqual(len(variants), 9)
        for i in range(2):
            observed = detection['marcas_sensibilidad'][i]
            for variant in variants:
                self.assertLessEqual(min(observed), min(variant['marcas'][i]))
                self.assertGreaterEqual(max(observed), max(variant['marcas'][i]))
        self.assertGreaterEqual(detection['sensibilidad_s'],
                                sum(max(m)-min(m) for m in detection['marcas_por_umbral'])-1e-12)

    def test_manual_markers_are_not_changed(self):
        x = signal()
        arbitrary = [.61, 1.61]
        measured = measure_audio(x, 48000, arbitrary)
        self.assertEqual(measured['tiempos'], arbitrary)
        self.assertIsNone(measured['sensibilidad_s'])
        auto = detect_claps(x, 48000)
        measured = measure_audio(x, 48000, auto['tiempos'])
        self.assertEqual(measured['referencia_umbral_manual'], auto['marcas_sensibilidad'])

    def test_three_impulses_remain_ambiguous(self):
        with self.assertRaisesRegex(ValueError, 'más de dos eventos'):
            detect_claps(signal(rumble=False, onsets=(.5, 1.2, 2.)), 48000)


if __name__ == '__main__':
    unittest.main()
