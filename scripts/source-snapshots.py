"""Preserve immutable upstream main-project source trees as a release sidecar."""
from __future__ import annotations

import hashlib
import argparse
import gzip
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation' / 'source-snapshots'
SOURCES = {
    'gifski': ('ImageOptim/gifski', '1060eab4500a20f27e2fa3ab7e85473d0e921cbd'),
    'ffmpeg': ('FFmpeg/FFmpeg', '6882969ce9fd2aa6aa1d0008b2bfe1c838aac11d'),
    'ffmpeg-builds': ('BtbN/FFmpeg-Builds', 'b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd'),
    'yt-dlp': ('yt-dlp/yt-dlp', 'f264a6cbd1f630894da0f368df00f8aae50140e0'),
}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-sidecar', type=Path, help='Reuse hash-verified source archives from an existing release; no network')
    args = parser.parse_args()
    buildconf = (ROOT / 'vendor/ffmpeg-buildconf.txt').read_text(encoding='utf-8')
    assert '--enable-shared' in buildconf and '--disable-libx264' in buildconf
    CACHE.mkdir(parents=True, exist_ok=True)
    lock_path = ROOT / 'vendor' / 'source-code.lock.json'
    previous = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.exists() else {}
    inventory = {'schema_version': 1, 'scope': 'upstream main trees and build recipes; dependency source directions in docs/SOURCES.md', 'sources': {}}
    for name, (repo, commit) in SOURCES.items():
        url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
        path = CACHE / f'{name}-{commit}.tar.gz'
        if not path.exists() and args.from_sidecar:
            with tarfile.open(args.from_sidecar, 'r:gz') as prior:
                data = prior.extractfile('upstream-sources/' + path.name).read()
            expected = previous['sources'][name]
            assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256'], name
            path.write_bytes(data)
        if not path.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'dsh-cyber-amber-source-snapshot'})
            partial = path.with_suffix(path.suffix + '.part')
            try:
                with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as output:
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 80 * 1024 * 1024:
                            raise SystemExit(f'Unexpected source archive size: {name}')
                        output.write(chunk)
                with tarfile.open(partial, 'r:gz') as archive:
                    assert any(member.name.endswith(('/LICENSE', '/COPYING.LGPLv3')) for member in archive), name
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
        entry = {'repository': repo, 'commit': commit, 'url': url, 'file': path.name,
                 'bytes': path.stat().st_size, 'sha256': sha256(path)}
        if previous and entry != previous['sources'][name]:
            raise SystemExit(f'Source snapshot differs from lock: {name}')
        inventory['sources'][name] = entry
        print(f'{name}: {entry["bytes"]} bytes, SHA256 {entry["sha256"]}', flush=True)
    lock_path.write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8', newline='\n')
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    target = ROOT / 'dist' / f'dsh-cyber-amber-{version}-upstream-sources.tar.gz'
    target.parent.mkdir(exist_ok=True)
    # Stable metadata: identical source/doc bytes produce identical sidecars.
    with target.open('wb') as raw, gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as output:
        for entry in inventory['sources'].values():
            member = tarfile.TarInfo(f'upstream-sources/{entry["file"]}')
            member.size = entry['bytes']
            member.mode = 0o644
            with (CACHE / entry['file']).open('rb') as source:
                output.addfile(member, source)
        for file in ['docs/SOURCES.md', 'docs/DISTRIBUTION.md', 'vendor/distribution-audit.json',
                     'vendor/source-code.lock.json', 'vendor/ffmpeg-buildconf.txt', 'NOTICE.md']:
            data = (ROOT / file).read_bytes()
            member = tarfile.TarInfo('upstream-sources/' + file)
            member.size = len(data)
            member.mode = 0o644
            output.addfile(member, io.BytesIO(data))
    with tarfile.open(target, 'r:gz') as archive:
        for entry in inventory['sources'].values():
            with archive.extractfile('upstream-sources/' + entry['file']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256']
    print(json.dumps({'artifact': target.name, 'bytes': target.stat().st_size, 'sha256': sha256(target)}))


if __name__ == '__main__':
    main()
