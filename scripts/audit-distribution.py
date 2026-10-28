"""Offline source/notice evidence inventory. Never certifies legal compliance."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(sidecar):
    lock = json.loads((ROOT / 'vendor/source-code.lock.json').read_text(encoding='utf-8'))
    binary_lock = json.loads((ROOT / 'vendor/sources.lock.json').read_text(encoding='utf-8'))
    source_files = {}
    with tarfile.open(sidecar, 'r:gz') as outer:
        for component, entry in lock['sources'].items():
            data = outer.extractfile('upstream-sources/' + entry['file']).read()
            assert len(data) == entry['bytes'] and digest(data) == entry['sha256'], component
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as inner:
                source_files[component] = {m.name.partition('/')[2]: inner.extractfile(m).read()
                                           for m in inner if m.isfile()}
    notices = (ROOT / 'vendor/licenses/yt-dlp-THIRD_PARTY_LICENSES.txt').read_text(encoding='utf-8')
    headers = list(re.finditer(r'^([^\n|]+) \| ([^\n]+)$', notices, re.M))
    python_notices = []
    for header in headers:
        following = '\n'.join(notices[header.end():].splitlines()[:5])
        urls = re.findall(r'https?://[^\s<>]+', following)
        python_notices.append({'component': header[1], 'license': header[2], 'project_urls': urls})
    cargo = tomllib.loads(source_files['gifski']['Cargo.lock'].decode('utf-8'))
    crates = [{'name': p['name'], 'version': p['version'], 'source': p.get('source'),
               'checksum': p.get('checksum')} for p in cargo['package']]
    recipes = []
    for name, data in sorted(source_files['ffmpeg-builds'].items()):
        if not name.startswith('scripts.d/') or not name.endswith('.sh'):
            continue
        text = data.decode('utf-8')
        recipes.append({'file': name, 'sha256': digest(data),
                        'source_declarations': [line.strip() for line in text.splitlines()
                                                if re.match(r'\s*SCRIPT_(REPO|COMMIT|REV|TAG|VERSION|BRANCH)=', line)]})
    licenses = []
    for path in sorted((ROOT / 'vendor/licenses').glob('*')):
        if path.is_file():
            licenses.append({'file': path.relative_to(ROOT).as_posix(), 'sha256': digest(path.read_bytes())})
    return {
        'schema_version': 1,
        'publication_ready': False,
        'scope': 'Evidence inventory, not a complete SBOM, source closure, or legal certification.',
        'main_components': {name: {'version': binary_lock['components'][name]['version'],
                                  'source': lock['sources'][name],
                                  'license': {'gifski': 'AGPL-3.0-or-later', 'ffmpeg': 'LGPL-3.0-or-later',
                                              'yt-dlp': 'Unlicense source; GPLv3+ official bundled aggregate'}[name]}
                            for name in ('gifski', 'ffmpeg', 'yt-dlp')},
        'preserved_license_files': licenses,
        'gifski_lock_entries': crates,
        'gifski_lock_scope': 'Includes optional/build dependencies; not proof each entry is linked into the shipped executable. Per-dependency source/license closure remains unverified.',
        'ffmpeg_enabled_features': re.findall(r'--enable-([\w-]+)', (ROOT / 'vendor/ffmpeg-buildconf.txt').read_text(encoding='utf-8')),
        'ffmpeg_build_recipes': recipes,
        'ffmpeg_recipe_scope': 'Preserved recipe evidence; moving branch tips and transitive patches must be resolved to the actual binary build, not current upstream heads.',
        'ytdlp_notice_entries': python_notices,
        'ytdlp_notice_scope': 'Upstream notices cover multiple platforms; presence here does not prove inclusion in this Windows build or identify an exact bundled version.',
        'publication_blockers': [
            {'id': 'DIST-01', 'component': 'ffmpeg', 'reason': 'Exact binary-to-transitive-library version, source, patch and notice mapping is not established for all enabled libraries.'},
            {'id': 'DIST-02', 'component': 'gifski', 'reason': 'Main source and Cargo.lock are preserved; the shipped binary feature/dependency source and license closure has not been independently established.'},
            {'id': 'DIST-03', 'component': 'yt-dlp', 'reason': 'Main source and upstream notices are preserved; exact private Python/native dependency versions and corresponding source coverage remain incomplete.'},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar', type=Path, required=True)
    parser.add_argument('--write', action='store_true', help='Explicitly update the tracked evidence inventory')
    parser.add_argument('--require-public-ready', action='store_true')
    args = parser.parse_args()
    result = inventory(args.sidecar)
    path = ROOT / 'vendor/distribution-audit.json'
    if args.write:
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    else:
        assert json.loads(path.read_text(encoding='utf-8')) == result, 'Distribution evidence differs; inspect and explicitly regenerate'
    print(json.dumps({'main_components': len(result['main_components']), 'license_files': len(result['preserved_license_files']),
                      'cargo_lock_entries': len(result['gifski_lock_entries']), 'build_recipes': len(result['ffmpeg_build_recipes']),
                      'notice_entries': len(result['ytdlp_notice_entries']), 'publication_ready': result['publication_ready'],
                      'publication_blockers': result['publication_blockers']}))
    if args.require_public_ready and not result['publication_ready']:
        raise SystemExit('Public distribution gate is BLOCKED; see vendor/distribution-audit.json')


if __name__ == '__main__':
    main()
