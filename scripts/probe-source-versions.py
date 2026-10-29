"""Offline version evidence from pinned executables; never request a video URL."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'vendor/manifest.json').read_text(encoding='utf-8'))
    for name in ('yt-dlp', 'ffmpeg', 'ffprobe', 'gifski'):
        relative = manifest['binaries'][name]
        with (ROOT / 'vendor' / relative).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['files'][relative]['sha256']
    root = ROOT / '.validation/distribution'
    root.mkdir(parents=True, exist_ok=True)
    info = root / 'offline-info.json'
    info.write_text(json.dumps({'id': 'source-audit', 'title': 'source-audit',
                               'webpage_url': 'http://127.0.0.1:9/not-requested',
                               'formats': [{'format_id': 'audit', 'url': 'http://127.0.0.1:9/not-requested.mp4', 'ext': 'mp4'}]}),
                    encoding='utf-8', newline='\n')
    result = subprocess.run([str(ROOT / 'vendor' / manifest['binaries']['yt-dlp']), '--ignore-config', '--no-update',
                             '--verbose', '--simulate', '--skip-download', '--ffmpeg-location',
                             str(ROOT / 'vendor' / manifest['binaries']['ffmpeg']), '--load-info-json', str(info)],
                            capture_output=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0
    lines = [line for line in result.stderr.splitlines() if line.startswith(('[debug] yt-dlp version', '[debug] Python ',
             '[debug] Optional libraries:', '[debug] exe versions:'))]
    gif_bytes = (ROOT / 'vendor' / manifest['binaries']['gifski']).read_bytes()
    report = {'schema_version': 1, 'offline_simulation': True, 'video_requested': False, 'version_lines': lines,
              'gifski_rustc_revisions': sorted({m.decode('ascii').split('/')[1] for m in re.findall(rb'rustc/[0-9a-f]{40}', gif_bytes)}),
              'gifski_embedded_imagequant': sorted({m.decode('ascii') for m in re.findall(rb'imagequant-[0-9.]+', gif_bytes)}),
              'binary_hashes': {k: manifest['files'][v]['sha256'] for k, v in manifest['binaries'].items()}}
    destination = ROOT / 'vendor/runtime-source-evidence.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'version_evidence_lines': len(lines), 'rustc_revisions': report['gifski_rustc_revisions']}))


if __name__ == '__main__':
    main()
