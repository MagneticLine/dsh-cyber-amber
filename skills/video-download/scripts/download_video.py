#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Single-video downloader extracted from Cyber Amber's download contract.

Python 3.10+ standard library; external yt-dlp, FFmpeg and ffprobe are required.
No DSH/NoneBot imports. Output is a single JSON value; no install/update hooks.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import uuid


class DownloadError(Exception):
    def __init__(self, code, message, *, retained=False):
        super().__init__(message)
        self.code, self.retained = code, retained


def error_code(error):
    if isinstance(error, DownloadError):
        return error.code
    if isinstance(error, KeyboardInterrupt):
        return 'cancelled'
    return 'permission_denied' if isinstance(error, PermissionError) else 'processing_failed'


def normalize_url(value):
    value = value.strip()
    if re.fullmatch(r'BV[A-Za-z0-9]{10}|av\d+', value, re.I):
        value = 'https://www.bilibili.com/video/' + value
    try:
        url = urlsplit(value)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError()
        _ = url.port
    except ValueError:
        raise DownloadError('invalid_source', 'Use an HTTP(S) video URL or BV/av ID without embedded credentials.')
    if len(value) > 8192 or any(ord(c) < 32 for c in value):
        raise DownloadError('invalid_source', 'Invalid URL length or control characters.')
    return value


def display_source(value):
    url = urlsplit(value)
    host = (url.hostname or '').lower()
    key = 'v' if host == 'youtube.com' or host.endswith('.youtube.com') else 'p' if host == 'bilibili.com' or host.endswith('.bilibili.com') else None
    query = parse_qs(url.query).get(key, []) if key else []
    allowed = {key: query[0]} if query and re.fullmatch(r'[\w-]{1,64}', query[0]) else {}
    netloc = '[' + host + ']' if ':' in host else host
    if url.port:
        netloc += ':' + str(url.port)
    return urlunsplit((url.scheme, netloc, url.path, urlencode(allowed), ''))


def diagnostic(value):
    def redact_url(match):
        try:
            return display_source(match[0])
        except ValueError:
            return '[URL]'
    value = re.sub(r'https?://[^\s<>]+', redact_url, str(value))
    value = re.sub(r'(?im)\b(cookie|authorization|sessdata|bili_jct)\s*[:=][^\r\n]*', r'\1=[redacted]', value)
    value = re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]', value)
    return '\n'.join(value.strip().splitlines()[-8:])[-4000:]


def object_json(text, label):
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise DownloadError('invalid_metadata', label + ' did not return a JSON object.')


def resolve_tools(args):
    config = {}
    config_path = Path(args.config).resolve() if args.config else Path(__file__).resolve().parents[1] / 'backend.local.json'
    if args.config or config_path.exists():
        config = object_json(config_path.read_text(encoding='utf-8'), 'tool configuration')
    root_value = args.bundle_root or config.get('bundle_root')
    for key, value in config.items():
        if key not in {'bundle_root', 'yt_dlp', 'ffmpeg', 'ffprobe'} or not isinstance(value, str):
            raise DownloadError('invalid_config', 'Tool configuration accepts only string program paths and bundle_root.')
    manifest, root, verified = None, None, set()
    if root_value:
        root = Path(root_value).expanduser().resolve(strict=True)
        manifest = object_json((root / 'manifest.json').read_text(encoding='utf-8'), 'bundle manifest')
        arch = 'x64' if sys.maxsize > 2**32 else 'x86'
        if manifest.get('platform') != ('win32' if os.name == 'nt' else sys.platform) or manifest.get('arch') != arch:
            raise DownloadError('bundle_platform', 'The configured binary bundle does not match this platform.')
    tools = {}
    for key, program in [('yt_dlp', 'yt-dlp'), ('ffmpeg', 'ffmpeg'), ('ffprobe', 'ffprobe')]:
        configured = getattr(args, key) or config.get(key)
        if not configured and manifest is not None:
            files, binaries = manifest.get('files'), manifest.get('binaries')
            if not isinstance(files, dict) or not isinstance(binaries, dict):
                raise DownloadError('bundle_invalid', 'Missing bundle file or executable map.')
            name = binaries.get(program)
            entry = files.get(name) if isinstance(name, str) else None
            if not isinstance(entry, dict) or not isinstance(entry.get('component'), str):
                raise DownloadError('bundle_invalid', 'Missing component: ' + program)
            component = entry['component']
            if component not in verified:
                for relative, item in files.items():
                    if not isinstance(item, dict):
                        raise DownloadError('bundle_invalid', 'Invalid bundle file record.')
                    if item.get('component') != component:
                        continue
                    path = (root / relative).resolve(strict=True)
                    if not path.is_relative_to(root) or path == root or not path.is_file():
                        raise DownloadError('bundle_invalid', 'Bundle file escaped its root.')
                    if path.stat().st_size != item.get('bytes'):
                        raise DownloadError('bundle_checksum_failed', 'Bundle file size mismatch: ' + relative)
                    with path.open('rb') as stream:
                        hasher = hashlib.sha256()
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            hasher.update(chunk)
                    if hasher.hexdigest() != item.get('sha256'):
                        raise DownloadError('bundle_checksum_failed', 'Bundle checksum mismatch: ' + relative)
                verified.add(component)
            configured = str(root / name)
        path = shutil.which(configured or program)
        if not path:
            raise DownloadError('runtime_missing', 'Executable not found: ' + (configured or program))
        tools[key] = str(Path(path).resolve())
    return tools


def stop_process(process):
    if process.poll() is not None:
        try:
            process.communicate(timeout=1)
            return
        except subprocess.TimeoutExpired:
            raise DownloadError('process_cleanup_failed', 'Child streams remain open after parent exit.', retained=True)
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if result.returncode and process.poll() is None:
            raise DownloadError('process_cleanup_failed', 'Could not confirm the owned process tree stopped.', retained=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        raise DownloadError('process_cleanup_failed', 'Owned process did not exit; work directory retained.', retained=True)


def run_command(argv, cwd, deadline, stage):
    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=max(0.001, deadline - time.monotonic()))
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as original:
        try:
            stop_process(process)
        except Exception as cleanup:
            raise DownloadError('process_cleanup_failed', diagnostic(cleanup), retained=True) from original
        code = 'cancelled' if isinstance(original, KeyboardInterrupt) else 'timeout'
        raise DownloadError(code, 'Download operation ' + code + '.')
    if process.returncode:
        details = diagnostic(stderr.decode('utf-8', errors='replace'))
        permission = re.search(r'permission denied|access is denied|拒绝访问|\bEACCES\b|\bEPERM\b', details, re.I)
        raise DownloadError('permission_denied' if permission else stage + '_failed', details or stage + ' exited unsuccessfully.')
    if len(stdout) > 1024 * 1024:
        raise DownloadError('output_truncated', stage + ' output exceeded 1MB.')
    return stdout.decode('utf-8', errors='replace')


def download_args(url, work, args, tools):
    video, combined = f'bv[height<=?{args.height}]', f'b[height<=?{args.height}]'
    command = [tools['yt_dlp'], '--ignore-config', '--no-playlist', '--no-progress', '--no-simulate',
               '--retries', '1', '--fragment-retries', '1', '--extractor-retries', '0',
               '--abort-on-unavailable-fragments', '--socket-timeout', '30',
               '--max-filesize', str(int(args.max_mb * 1000000)),
               '--no-write-thumbnail', '--no-write-subs', '--no-write-auto-subs',
               '-f', f'{video}/{combined}' if args.video_only else f'{video}+ba/{combined}/{video}',
               '--ffmpeg-location', tools['ffmpeg'], '-P', str(work), '-o', 'media.%(ext)s',
               '--write-info-json', '--no-clean-info-json', '--print', 'after_move:filepath']
    if not args.video_only:
        command += ['--merge-output-format', 'mkv']
    if args.cookies_file:
        cookie = Path(args.cookies_file).expanduser().resolve(strict=True)
        if not cookie.is_file():
            raise DownloadError('cookies_missing', 'Cookie path is not a file.')
        private_copy = work / 'login-cookies.txt'
        shutil.copyfile(cookie, private_copy)
        command += ['--cookies', str(private_copy)]
    if args.proxy:
        command += ['--proxy', args.proxy]
    return command + ['--', url]


def media_info(path, tools, work, deadline):
    data = object_json(run_command([tools['ffprobe'], '-v', 'error', '-show_entries',
        'stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,sample_aspect_ratio:stream_side_data=rotation:format=duration',
        '-of', 'json', str(path)], work, deadline, 'probe'), 'ffprobe')
    streams = data.get('streams')
    if not isinstance(streams, list):
        raise DownloadError('invalid_metadata', 'No stream list returned.')
    video = next((s for s in streams if isinstance(s, dict) and s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if isinstance(s, dict) and s.get('codec_type') == 'audio'), None)
    if video is None:
        raise DownloadError('no_video', 'The downloaded file has no video stream.')
    try:
        sar = video.get('sample_aspect_ratio', '1:1')
        sar = 1 if sar in ('N/A', '0:1', '') else float(Fraction(sar.replace(':', '/')))
        width, height = int(video['width']) * sar, int(video['height'])
        rotation = float(next((s['rotation'] for s in video.get('side_data_list', []) if 'rotation' in s), 0))
        if not math.isfinite(rotation) or abs(rotation / 90 - round(rotation / 90)) > 0.001:
            raise ValueError()
        if round(rotation / 90) % 2:
            width, height = height, width
        duration = float(data['format']['duration'])
        fps = 0
        for key in ('avg_frame_rate', 'r_frame_rate'):
            try:
                fps = float(Fraction(video.get(key, '0/1')))
            except (ValueError, ZeroDivisionError):
                continue
            if fps > 0:
                break
        if not all(math.isfinite(v) and v > 0 for v in (width, height, duration, fps)):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError, ZeroDivisionError):
        raise DownloadError('invalid_metadata', 'Invalid video dimensions, duration or frame rate.')
    result = {'width': width, 'height': height, 'fps': fps, 'duration_seconds': duration,
              'bytes': path.stat().st_size, 'video_codec': video.get('codec_name'), 'has_audio': audio is not None}
    if audio and isinstance(audio.get('codec_name'), str):
        result['audio_codec'] = audio['codec_name']
    return result


def remove_work(work, root):
    if work.is_symlink() or work.resolve() != work or work.parent != root or not work.name.startswith('.video-download-'):
        raise DownloadError('cleanup_path_invalid', 'Refusing to remove an unexpected work directory.')
    shutil.rmtree(work)


def publish(source, target):
    created = False
    try:
        output = target.open('xb')
        created = True
        with output, source.open('rb') as input_file:
            shutil.copyfileobj(input_file, output, 1024 * 1024)
    except BaseException as original:
        if created:
            try:
                target.unlink()
            except OSError as cleanup:
                raise DownloadError('publish_failed', diagnostic(original) + '; Partial output retained: '
                                    + str(target) + '; ' + diagnostic(cleanup)) from original
        raise


def download(args, tools, deadline):
    url = normalize_url(args.source)
    root = Path(args.output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.video-download-', dir=root)).resolve()
    result, failure = None, None
    try:
        stdout = run_command(download_args(url, work, args, tools), work, deadline, 'download')
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise DownloadError('download_not_created', 'No file was downloaded; check size limit, login and available formats.')
        source = (work / lines[-1]).resolve(strict=True)
        if source.parent != work or not source.is_file():
            raise DownloadError('download_path_invalid', 'Downloader returned a file outside its work directory.')
        if not 0 < source.stat().st_size <= args.max_mb * 1000000:
            raise DownloadError('source_size_limit', 'Downloaded file is empty or exceeds the source size limit.')
        info = media_info(source, tools, work, deadline)
        metadata_path = work / 'media.info.json'
        metadata = object_json(metadata_path.read_text(encoding='utf-8'), 'yt-dlp') if metadata_path.exists() and metadata_path.stat().st_size <= 4 * 1024 * 1024 else {}
        title = str(metadata.get('title') or metadata.get('id') or 'video')[:300]
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).rstrip('. ')[:55] or 'video'
        target = root / (name + '-' + uuid.uuid4().hex[:12] + source.suffix)
        publish(source, target)
        result = {'status': 'downloaded', 'path': str(target), 'title': title, 'source': display_source(url), **info}
    except (Exception, KeyboardInterrupt) as error:
        failure = error
    if isinstance(failure, DownloadError) and failure.retained:
        raise DownloadError(failure.code, str(failure) + ' Work directory: ' + str(work), retained=True)
    try:
        remove_work(work, root)
    except Exception as cleanup:
        note = 'Temporary directory retained: ' + str(work) + '; ' + diagnostic(cleanup)
        if failure:
            raise DownloadError(error_code(failure), diagnostic(failure) + '; ' + note) from failure
        result['warnings'] = [note]
    if failure:
        raise failure
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?')
    parser.add_argument('--output-dir', default='video-downloads')
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--max-mb', type=float, default=512)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--video-only', action='store_true')
    parser.add_argument('--cookies-file')
    parser.add_argument('--proxy')
    parser.add_argument('--config')
    parser.add_argument('--bundle-root')
    parser.add_argument('--yt-dlp', dest='yt_dlp')
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not (144 <= args.height <= 2160 and math.isfinite(args.max_mb) and 0 < args.max_mb <= 4096
                and math.isfinite(args.timeout) and 1 <= args.timeout <= 1800):
            raise DownloadError('invalid_parameter', 'height: 144..2160; max-mb: >0..4096; timeout: 1..1800 seconds.')
        if not args.check:
            if not args.source:
                raise DownloadError('invalid_source', 'Provide one video URL or BV/av ID.')
            normalize_url(args.source)
        deadline = time.monotonic() + args.timeout
        tools = resolve_tools(args)
        if args.check:
            versions = {key: run_command([path, '--version' if key == 'yt_dlp' else '-version'], Path.cwd(), deadline, 'version').splitlines()[0]
                        for key, path in tools.items()}
            result = {'status': 'ready', 'tools': tools, 'versions': versions}
        else:
            result = download(args, tools, deadline)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'status': 'error', 'code': error_code(error), 'message': diagnostic(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
