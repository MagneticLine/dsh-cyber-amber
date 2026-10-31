import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('video_download', ROOT / 'skills/video-download/scripts/download_video.py')
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)


class VideoDownloadSkill(unittest.TestCase):
    def setUp(self):
        validation = ROOT / '.validation'
        validation.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='skill-unit-', dir=validation)
        self.root = Path(self.temp.name).resolve()
        assert self.root.parent == validation.resolve()
        self.args = SimpleNamespace(height=1080, max_mb=512, video_only=False,
                                    cookies_file=None, proxy=None, output_dir=str(self.root), source='BV1RwnQ6sEd5')
        self.tools = {'yt_dlp': 'yt-dlp', 'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}

    def tearDown(self):
        self.temp.cleanup()

    def test_ids_and_signed_url_are_preserved_for_actual_request(self):
        self.assertEqual(vd.normalize_url('BV1RwnQ6sEd5'), 'https://www.bilibili.com/video/BV1RwnQ6sEd5')
        url = 'https://example.com/video?signature=secret'
        self.assertEqual(vd.normalize_url(url), url)

    def test_unsafe_source_and_embedded_credentials_rejected(self):
        for url in ['file:///a.mp4', 'https://name:secret@example.com/video', 'https://a/b\nheader']:
            with self.assertRaises(vd.DownloadError) as error:
                vd.normalize_url(url)
            self.assertEqual(error.exception.code, 'invalid_source')

    def test_provenance_and_diagnostics_omit_secrets(self):
        url = 'https://www.bilibili.com/video/BV1RwnQ6sEd5?p=2&signature=hidden'
        self.assertEqual(vd.display_source(url), 'https://www.bilibili.com/video/BV1RwnQ6sEd5?p=2')
        output = vd.diagnostic('http://name:password@example.com/a?token=hidden\nAuthorization: Bearer hidden\nSESSDATA=hidden')
        for secret in ['password', 'hidden', 'name:']:
            self.assertNotIn(secret, output)
        self.assertEqual(vd.diagnostic('https://[invalid'), '[URL]')

    def test_audio_and_video_only_format_contract(self):
        command = vd.download_args('https://example.com/a', self.root, self.args, self.tools)
        self.assertIn('bv[height<=?1080]+ba/b[height<=?1080]/bv[height<=?1080]', command)
        self.assertIn('--no-playlist', command)
        self.assertEqual(command[-2:], ['--', 'https://example.com/a'])
        self.args.video_only = True
        command = vd.download_args('https://example.com/a', self.root, self.args, self.tools)
        self.assertNotIn('--merge-output-format', command)
        self.assertIn('bv[height<=?1080]/b[height<=?1080]', command)

    def test_cookie_input_is_not_given_to_mutating_downloader(self):
        original = self.root / 'provided.txt'
        original.write_text('private fixture', encoding='utf-8')
        work = self.root / 'work'
        work.mkdir()
        self.args.cookies_file = str(original)
        command = vd.download_args('https://example.com/a', work, self.args, self.tools)
        actual = Path(command[command.index('--cookies') + 1])
        self.assertNotEqual(actual, original)
        actual.write_text('changed by downloader', encoding='utf-8')
        self.assertEqual(original.read_text(encoding='utf-8'), 'private fixture')

    def test_existing_output_is_preserved_on_filename_collision(self):
        source, target = self.root / 'source', self.root / 'target'
        source.write_bytes(b'new')
        target.write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            vd.publish(source, target)
        self.assertEqual(target.read_bytes(), b'original')

    def test_partial_output_is_removed_when_copy_fails(self):
        source, target = self.root / 'source', self.root / 'target'
        source.write_bytes(b'new')
        with patch.object(vd.shutil, 'copyfileobj', side_effect=OSError('injected copy failure')):
            with self.assertRaisesRegex(OSError, 'injected copy failure'):
                vd.publish(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(source.read_bytes(), b'new')

    def test_timeout_stops_real_owned_process(self):
        children = []
        popen = subprocess.Popen
        def launch(argv, **kwargs):
            process = popen(argv, **kwargs)
            if argv[0] == sys.executable:
                children.append(process)
            return process
        with patch.object(vd.subprocess, 'Popen', side_effect=launch):
            with self.assertRaises(vd.DownloadError) as error:
                vd.run_command([sys.executable, '-c', 'import time; time.sleep(30)'],
                               self.root, time.monotonic() + 0.2, 'test')
        self.assertEqual(error.exception.code, 'timeout')
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_metadata_audio_and_display_aspect(self):
        source = self.root / 'source'
        source.write_bytes(b'fixture')
        data = {'streams': [{'codec_type': 'video', 'codec_name': 'mpeg4', 'width': 100, 'height': 80,
                             'sample_aspect_ratio': '2:1', 'avg_frame_rate': '20/1',
                             'side_data_list': [{'rotation': 90}]}, {'codec_type': 'audio', 'codec_name': 'aac'}],
                'format': {'duration': '1.5'}}
        with patch.object(vd, 'run_command', return_value=json.dumps(data)):
            result = vd.media_info(source, self.tools, self.root, time.monotonic() + 10)
        self.assertEqual((result['width'], result['height']), (80, 200))
        self.assertTrue(result['has_audio'])
        self.assertEqual(result['audio_codec'], 'aac')

    def test_invalid_metadata_is_not_reported_as_download_success(self):
        for data in [None, [], {'streams': []}, {'streams': [None]}]:
            with patch.object(vd, 'run_command', return_value=json.dumps(data)):
                with self.assertRaises(vd.DownloadError):
                    vd.media_info(self.root / 'source', self.tools, self.root, time.monotonic() + 10)

    def test_download_failure_cleans_only_owned_directory(self):
        marker = self.root / 'existing.mp4'
        marker.write_bytes(b'keep')
        with patch.object(vd, 'run_command', side_effect=vd.DownloadError('download_failed', 'fixture failure')):
            with self.assertRaisesRegex(vd.DownloadError, 'fixture failure'):
                vd.download(self.args, self.tools, time.monotonic() + 10)
        self.assertEqual(list(self.root.iterdir()), [marker])

    def test_unconfirmed_process_keeps_work_directory(self):
        with patch.object(vd, 'run_command', side_effect=vd.DownloadError('process_cleanup_failed', 'unconfirmed', retained=True)):
            with self.assertRaises(vd.DownloadError) as error:
                vd.download(self.args, self.tools, time.monotonic() + 10)
        self.assertTrue(error.exception.retained)
        self.assertEqual(len(list(self.root.glob('.video-download-*'))), 1)

    def test_cleanup_failure_does_not_hide_original_error(self):
        with patch.object(vd, 'run_command', side_effect=vd.DownloadError('download_failed', 'original failure')):
            with patch.object(vd, 'remove_work', side_effect=PermissionError('injected cleanup failure')):
                with self.assertRaises(vd.DownloadError) as error:
                    vd.download(self.args, self.tools, time.monotonic() + 10)
        self.assertEqual(error.exception.code, 'download_failed')
        self.assertIn('original failure', str(error.exception))
        self.assertIn('Temporary directory retained', str(error.exception))

    def test_bundle_dependency_is_checked_before_use(self):
        files, binaries = {}, {}
        for program in ['yt-dlp', 'ffmpeg', 'ffprobe']:
            name = program + '.exe'
            data = program.encode()
            (self.root / name).write_bytes(data)
            files[name] = {'component': 'fixture', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            binaries[program] = name
        manifest = {'platform': 'win32' if os.name == 'nt' else sys.platform,
                    'arch': 'x64' if sys.maxsize > 2**32 else 'x86', 'files': files, 'binaries': binaries}
        (self.root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        args = SimpleNamespace(config=None, bundle_root=str(self.root), yt_dlp=None, ffmpeg=None, ffprobe=None)
        with patch.object(vd.shutil, 'which', side_effect=lambda value: value):
            self.assertTrue(vd.resolve_tools(args)['yt_dlp'].endswith('yt-dlp.exe'))
            (self.root / 'ffmpeg.exe').write_bytes(b'changed')
            with self.assertRaises(vd.DownloadError) as error:
                vd.resolve_tools(args)
        self.assertEqual(error.exception.code, 'bundle_checksum_failed')


if __name__ == '__main__':
    unittest.main()
