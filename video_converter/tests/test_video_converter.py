#!/usr/bin/env python3
"""Tests fonctionnels du convertisseur vidéo.

Nécessite ffmpeg et ffprobe installés. Exécution :
    python3 -m unittest discover -s video_converter/tests -v
ou depuis le répertoire du script :
    python3 -m unittest discover -s tests -v
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import video_converter as vc


def _check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


HAVE_FFMPEG = _check_ffmpeg()


def make_test_video(path, duration=2, width=320, height=240, with_audio=False, codec='libx264'):
    """Génère une petite vidéo de test avec ffmpeg."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'testsrc2=duration={duration}:size={width}x{height}:rate=25',
    ]
    if with_audio:
        cmd.extend(['-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}'])
        cmd.extend(['-c:a', 'aac'])
    cmd.extend(['-c:v', codec, '-pix_fmt', 'yuv420p', path])
    subprocess.run(cmd, capture_output=True, check=True)


class TestFormatting(unittest.TestCase):
    def test_format_timedelta(self):
        fmt = vc.VideoConverter._format_timedelta
        self.assertEqual(fmt(0), '00:00:00')
        self.assertEqual(fmt(65), '00:01:05')
        self.assertEqual(fmt(3661), '01:01:01')
        self.assertEqual(fmt(89999), '24:59:59')


class TestResolutionReduction(unittest.TestCase):
    def setUp(self):
        self.converter = vc.VideoConverter.__new__(vc.VideoConverter)
        self.converter.logger = logging.getLogger('test')
        self.converter.reduce_resolution = True

    def _video(self, width, height):
        return vc.VideoFile(
            path='/tmp/fake.mkv', size=0, codec='h264',
            width=width, height=height, duration=100.0,
        )

    def test_4k_reduces_to_1080p(self):
        self.assertEqual(
            self.converter.compute_reduced_resolution(self._video(3840, 2160)),
            (1920, 1080),
        )

    def test_1080p_reduces_to_720p(self):
        self.assertEqual(
            self.converter.compute_reduced_resolution(self._video(1920, 1080)),
            (1280, 720),
        )

    def test_720p_not_reduced(self):
        self.assertIsNone(self.converter.compute_reduced_resolution(self._video(1280, 720)))

    def test_unknown_resolution_not_reduced(self):
        self.assertIsNone(self.converter.compute_reduced_resolution(self._video(None, None)))

    def test_disabled_returns_none(self):
        self.converter.reduce_resolution = False
        self.assertIsNone(self.converter.compute_reduced_resolution(self._video(1920, 1080)))


class TestAudioLogic(unittest.TestCase):
    def setUp(self):
        self.converter = vc.VideoConverter.__new__(vc.VideoConverter)
        self.converter.logger = logging.getLogger('test')

    def test_has_french_audio(self):
        streams = [{'index': 0, 'language': 'fre', 'codec': 'aac'}]
        self.assertTrue(self.converter.has_french_audio(streams))

    def test_no_french_audio(self):
        streams = [{'index': 0, 'language': 'eng', 'codec': 'aac'}]
        self.assertFalse(self.converter.has_french_audio(streams))

    def test_should_reencode_without_french_high_bitrate(self):
        streams = [{'index': 0, 'language': 'eng', 'codec': 'ac3', 'channels': 6, 'bit_rate': '448000'}]
        reencode, to_process = self.converter.should_reencode_audio(streams)
        self.assertTrue(reencode)
        self.assertEqual(to_process, [0])

    def test_should_not_reencode_without_french_low_bitrate(self):
        streams = [{'index': 0, 'language': 'eng', 'codec': 'aac', 'channels': 2, 'bit_rate': '96000'}]
        reencode, to_process = self.converter.should_reencode_audio(streams)
        self.assertFalse(reencode)
        self.assertEqual(to_process, [])

    def test_should_not_reencode_with_french(self):
        streams = [
            {'index': 0, 'language': 'fre', 'codec': 'aac', 'channels': 2},
            {'index': 1, 'language': 'eng', 'codec': 'aac', 'channels': 2},
        ]
        reencode, to_process = self.converter.should_reencode_audio(streams)
        self.assertFalse(reencode)
        self.assertEqual(to_process, [1])


class TestSubtitleMap(unittest.TestCase):
    def setUp(self):
        self.converter = vc.VideoConverter.__new__(vc.VideoConverter)
        self.converter.logger = logging.getLogger('test')

    def test_includes_supported_subtitles(self):
        streams = [
            {'index': 0, 'codec': 'subrip', 'language': 'fre'},
            {'index': 1, 'codec': 'ssa', 'language': 'eng'},
        ]
        self.assertEqual(
            self.converter._build_subtitle_map_cmd(streams),
            ['-map', '0:s:0', '-map', '0:s:1'],
        )

    def test_excludes_unknown_codec(self):
        # Reproduit le bug : flux à codec inconnu -> "no decoder found for: none"
        streams = [
            {'index': 0, 'codec': 'subrip', 'language': 'fre'},
            {'index': 1, 'codec': '', 'language': 'eng'},
        ]
        self.assertEqual(
            self.converter._build_subtitle_map_cmd(streams),
            ['-map', '0:s:0'],
        )

    def test_excludes_missing_codec_key(self):
        streams = [{'index': 0, 'language': 'fre'}]
        self.assertEqual(self.converter._build_subtitle_map_cmd(streams), [])

    def test_excludes_pgs_and_hdmv_subtitles(self):
        streams = [
            {'index': 0, 'codec': 'hdmv_pgs_subtitle', 'language': 'fre'},
            {'index': 1, 'codec': 'pgssub', 'language': 'eng'},
            {'index': 2, 'codec': 'subrip', 'language': 'fre'},
        ]
        self.assertEqual(
            self.converter._build_subtitle_map_cmd(streams),
            ['-map', '0:s:2'],
        )

    def test_excludes_numeric_codec(self):
        streams = [{'index': 0, 'codec': '0', 'language': 'fre'}]
        self.assertEqual(self.converter._build_subtitle_map_cmd(streams), [])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe requis")
class TestWithRealVideos(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='vc_test_')
        self.config_file = os.path.join(self.tmpdir, 'test.conf')
        with open(self.config_file, 'w') as f:
            json.dump({'directories': [self.tmpdir], 'keep_backup': False}, f)
        self.converter = vc.VideoConverter(
            self.config_file,
            os.path.join(self.tmpdir, 'test.log'),
        )
        logging.getLogger('VideoConverter').addHandler(logging.NullHandler())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_and_metadata(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        self.converter.load_config()
        files = self.converter.scan_video_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].codec, 'h264')
        self.assertEqual(files[0].width, 320)
        self.assertEqual(files[0].height, 240)
        self.assertAlmostEqual(files[0].duration, 2.0, delta=0.5)
        self.assertGreater(files[0].size, 0)

    def test_needs_conversion_h264(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        vf = self.converter._create_video_file(path)
        self.assertTrue(self.converter.needs_conversion(vf))

    def test_needs_conversion_hevc(self):
        path = os.path.join(self.tmpdir, 'sample_hevc.mkv')
        make_test_video(path, codec='libx265')
        vf = self.converter._create_video_file(path)
        self.converter.process_audio_for_modern_codecs = False
        self.assertFalse(self.converter.needs_conversion(vf))

    def test_conversion_success(self):
        # Utiliser l'encodeur logiciel pour l'environnement de test (pas de GPU/NVENC en CI)
        original_params = vc.FFMPEG_HEVC_PARAMS
        vc.FFMPEG_HEVC_PARAMS = [
            '-c:v', 'libx265', '-preset', 'ultrafast',
            '-crf', '28', '-c:a', 'copy',
        ]
        try:
            path = os.path.join(self.tmpdir, 'sample.mp4')
            make_test_video(path)
            vf = self.converter._create_video_file(path)
            result = self.converter.convert_to_hevc(vf)
            self.assertTrue(result.success, result.error_message)
            self.assertGreater(result.converted_size, 0)
        finally:
            vc.FFMPEG_HEVC_PARAMS = original_params

    def test_ffmpeg_progress_runs(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        vf = self.converter._create_video_file(path)
        cmd = [
            'ffmpeg', '-i', path,
            '-c:v', 'libx265', '-preset', 'ultrafast',
            '-y', os.path.join(self.tmpdir, 'out.mkv'),
        ]
        elapsed = self.converter._run_ffmpeg_with_progress(cmd, vf)
        self.assertGreater(elapsed, 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, 'out.mkv')))

    def test_ffmpeg_progress_failure_raises(self):
        vf = vc.VideoFile(
            path='/tmp/inexistant.mp4', size=0, codec='h264',
            width=320, height=240, duration=2.0,
        )
        cmd = ['ffmpeg', '-i', vf.path, '-c:v', 'libx265', '-y', '/tmp/out_test.mkv']
        with self.assertRaises(subprocess.CalledProcessError):
            self.converter._run_ffmpeg_with_progress(cmd, vf)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe requis")
class TestForceScan(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='vc_force_')
        self.config_file = os.path.join(self.tmpdir, 'test.conf')
        with open(self.config_file, 'w') as f:
            json.dump({'directories': [self.tmpdir], 'keep_backup': False}, f)
        self.log_file = os.path.join(self.tmpdir, 'test.log')
        logging.getLogger('VideoConverter').addHandler(logging.NullHandler())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_marker(self, marker_name, path):
        marker_dir = os.path.dirname(self.config_file)
        with open(os.path.join(marker_dir, marker_name), 'w') as f:
            f.write(os.path.abspath(path) + '\n')

    def test_converted_marker_skipped_by_default(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        self._write_marker(vc.DEFAULT_CONVERTED_MARKER, path)
        converter = vc.VideoConverter(self.config_file, self.log_file)
        converter.load_config()
        converter.load_markers()
        files = converter.scan_video_files()
        self.assertEqual(len(files), 0)

    def test_force_scan_includes_converted_marker(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        self._write_marker(vc.DEFAULT_CONVERTED_MARKER, path)
        converter = vc.VideoConverter(self.config_file, self.log_file, force_scan=True)
        converter.load_config()
        converter.load_markers()
        files = converter.scan_video_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, path)

    def test_force_scan_includes_failed_marker(self):
        path = os.path.join(self.tmpdir, 'sample.mkv')
        make_test_video(path)
        self._write_marker(vc.DEFAULT_FAILED_MARKER, path)
        converter = vc.VideoConverter(self.config_file, self.log_file, force_scan=True)
        converter.load_config()
        converter.load_markers()
        files = converter.scan_video_files()
        self.assertEqual(len(files), 1)

    def test_force_scan_with_target_directory(self):
        subdir = os.path.join(self.tmpdir, 'subdir')
        os.makedirs(subdir)
        path = os.path.join(subdir, 'sample.mkv')
        make_test_video(path)
        self._write_marker(vc.DEFAULT_CONVERTED_MARKER, path)
        converter = vc.VideoConverter(self.config_file, self.log_file, target_path=subdir, force_scan=True)
        converter.load_config()
        converter.load_markers()
        files = converter.scan_video_files()
        self.assertEqual(len(files), 1)


if __name__ == '__main__':
    unittest.main()
