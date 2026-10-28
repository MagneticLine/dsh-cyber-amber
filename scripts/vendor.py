"""Maintainer-only, hash-pinned Windows x64 dependency preparation (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor'
CACHE = ROOT / '.validation' / 'downloads'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(offline=False):
    lock = json.loads((VENDOR / 'sources.lock.json').read_text(encoding='utf-8'))
    CACHE.mkdir(parents=True, exist_ok=True)
    target = VENDOR / 'win32-x64'
    files = {}

    def record(path, component):
        files[path.relative_to(VENDOR).as_posix()] = {
            'sha256': digest(path), 'bytes': path.stat().st_size, 'component': component,
        }

    def data_file(name, data, component):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        record(path, component)

    sources = {}
    for name, item in lock['components'].items():
        path = CACHE / item['cache_file']
        if not path.exists():
            if offline:
                raise SystemExit(f'Missing cached input: {path}')
            request = urllib.request.Request(item['url'], headers={'User-Agent': 'dsh-cyber-amber-build'})
            partial = path.with_suffix(path.suffix + '.part')
            try:
                with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as output:
                    shutil.copyfileobj(response, output)
                if digest(partial) != item['sha256']:
                    raise SystemExit(f'Checksum mismatch: {name}')
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
        if digest(path) != item['sha256']:
            raise SystemExit(f'Checksum mismatch: {name}')
        sources[name] = path

    # This is the reserved generated binary directory, never a user output/cache directory.
    if target.exists():
        if target.is_symlink() or target.resolve().parent != VENDOR.resolve():
            raise SystemExit('Refusing to replace an unexpected dependency directory')
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(sources['yt-dlp']) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if '..' in name.parts or name.is_absolute():
                raise SystemExit('Unsafe archive path')
            if not member.is_dir():
                data_file('yt-dlp/' + name.as_posix(), archive.read(member), 'yt-dlp')
    with zipfile.ZipFile(sources['ffmpeg']) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if '..' in name.parts or name.is_absolute():
                raise SystemExit('Unsafe archive path')
            if name.parent.name == 'bin' and (name.name in ('ffmpeg.exe', 'ffprobe.exe') or name.suffix == '.dll'):
                data_file(name.name, archive.read(member), 'ffmpeg')
            elif name.name == 'LICENSE.txt' and len(name.parts) == 2:
                path = VENDOR / 'licenses' / 'ffmpeg-LICENSE.txt'
                path.write_bytes(archive.read(member))
    matched = False
    with tarfile.open(sources['gifski'], mode='r:xz') as archive:
        for member in archive:
            if member.isfile() and PurePosixPath(member.name).name == 'gifski.exe':
                data = archive.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() == lock['components']['gifski']['exe_sha256']:
                    data_file('gifski.exe', data, 'gifski')
                    matched = True
                    break
    if not matched:
        raise SystemExit('The pinned x64 Gifski executable was not found')

    for path in sorted((VENDOR / 'licenses').glob('*')):
        if path.is_file():
            component = 'gifski' if path.name.startswith('gifski') else 'yt-dlp' if path.name.startswith('yt-dlp') else 'ffmpeg'
            record(path, component)
    manifest = {**lock, 'binaries': {
        name: f'win32-x64/{filename}' for name, filename in {
            'ffmpeg': 'ffmpeg.exe', 'ffprobe': 'ffprobe.exe', 'gifski': 'gifski.exe', 'yt-dlp': 'yt-dlp/yt-dlp.exe',
        }.items()
    }, 'files': dict(sorted(files.items()))}
    (VENDOR / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(files), 'runtime_bytes': sum(v['bytes'] for k, v in files.items() if k.startswith('win32-x64/'))}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Only use already verified cached release inputs')
    prepare(parser.parse_args().offline)
