"""Preserve immutable upstream main-project source trees as a release sidecar."""
from __future__ import annotations

import hashlib
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
    buildconf = (ROOT / 'vendor/ffmpeg-buildconf.txt').read_text(encoding='utf-8')
    assert '--enable-shared' in buildconf and '--disable-libx264' in buildconf
    CACHE.mkdir(parents=True, exist_ok=True)
    lock_path = ROOT / 'vendor' / 'source-code.lock.json'
    previous = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.exists() else {}
    inventory = {'schema_version': 1, 'scope': 'upstream main trees and build recipes; dependency source directions in docs/SOURCES.md', 'sources': {}}
    for name, (repo, commit) in SOURCES.items():
        url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
        path = CACHE / f'{name}-{commit}.tar.gz'
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
    with tarfile.open(target, 'w:gz') as output:
        for entry in inventory['sources'].values():
            output.add(CACHE / entry['file'], arcname=f'upstream-sources/{entry["file"]}', recursive=False)
        for file in ['docs/SOURCES.md', 'vendor/source-code.lock.json', 'vendor/ffmpeg-buildconf.txt', 'NOTICE.md']:
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
