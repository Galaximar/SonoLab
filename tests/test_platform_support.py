"""Compatibilidad de FFmpeg y de los visores externos del escritorio."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import audio_io
import desktop


class PlatformSupportTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)
        self.document = self.path/'gráfico con espacios.png'
        self.document.touch()

    def test_bundled_ffmpeg_works_without_system_installation(self):
        for platform, name in [('linux', 'ffmpeg'), ('win32', 'ffmpeg.exe')]:
            executable = self.path/name
            executable.touch()
            with patch.object(sys, 'platform', platform), \
                 patch.object(sys, '_MEIPASS', str(self.path), create=True), \
                 patch('audio_io.shutil.which', return_value=None):
                self.assertEqual(audio_io.ffmpeg_path(), str(executable))

    def test_linux_viewer_uses_original_libraries_without_changing_parent(self):
        original = {'LD_LIBRARY_PATH': '/private/app:/usr/local/lib',
                    'LD_LIBRARY_PATH_ORIG': '/usr/local/lib'}
        with patch.object(sys, 'platform', 'linux'), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.dict(os.environ, original, clear=True), \
             patch('desktop.shutil.which', return_value='/usr/bin/xdg-open'), \
             patch('desktop.subprocess.Popen') as launch:
            desktop.open_path(self.document)
            self.assertEqual(launch.call_args.args[0], ['/usr/bin/xdg-open', str(self.document)])
            self.assertEqual(launch.call_args.kwargs['env']['LD_LIBRARY_PATH'], '/usr/local/lib')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], original['LD_LIBRARY_PATH'])

    def test_linux_viewer_clears_private_libraries_when_no_original_existed(self):
        with patch.object(sys, 'platform', 'linux'), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.dict(os.environ, {'LD_LIBRARY_PATH': '/private/app'}, clear=True), \
             patch('desktop.shutil.which', return_value='/usr/bin/xdg-open'), \
             patch('desktop.subprocess.Popen') as launch:
            desktop.open_path(self.document)
            self.assertNotIn('LD_LIBRARY_PATH', launch.call_args.kwargs['env'])

    def test_windows_keeps_native_file_opening(self):
        with patch.object(sys, 'platform', 'win32'), \
             patch.object(os, 'startfile', create=True) as launch:
            desktop.open_path(self.document)
            launch.assert_called_once_with(str(self.document))

    def test_missing_linux_viewer_has_actionable_error(self):
        with patch.object(sys, 'platform', 'linux'), \
             patch('desktop.shutil.which', return_value=None):
            with self.assertRaisesRegex(OSError, 'xdg-utils'):
                desktop.open_path(self.document)


if __name__ == '__main__':
    unittest.main()
