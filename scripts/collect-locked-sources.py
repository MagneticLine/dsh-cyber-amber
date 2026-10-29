"""Retain checksum-pinned Cargo and Python source packages, never install them."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'scripts/collect-source-evidence.py'))
CACHE = ROOT / '.validation/distribution/materials'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar', type=Path, required=True)
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    trees = helpers['source_trees'](args.sidecar)
    packages = tomllib.loads(trees['gifski']['Cargo.lock'].decode('utf-8'))['package']
    requests = []
    for package in packages:
        if package.get('source', '').startswith('registry+'):
            name, version = package['name'], package['version']
            requests.append({'ecosystem': 'cargo', 'name': name, 'version': version,
                             'url': f'https://static.crates.io/crates/{name}/{name}-{version}.crate',
                             'sha256': package['checksum'], 'filename': f'{name}-{version}.crate'})
        elif package.get('source', '').startswith('git+'):
            source = package['source']
            match = re.fullmatch(r'git\+https://github.com/([^?#]+)(?:\?[^#]+)?#([a-f0-9]{40})', source)
            assert match, source
            requests.append({'ecosystem': 'cargo-git', 'name': package['name'], 'version': package['version'],
                             'url': f'https://codeload.github.com/{match[1]}/tar.gz/{match[2]}',
                             'revision': match[2], 'filename': package['name'] + '-' + match[2] + '.tar.gz'})
    evidence = json.loads((ROOT / '.validation/distribution/evidence.json').read_text(encoding='utf-8'))
    seen = set()
    for requirement in evidence['python_requirements']:
        if 'version' not in requirement:
            continue  # Custom PyInstaller wheel needs its own build/source mapping.
        key = (requirement['name'], requirement['version'])
        if key in seen:
            continue
        seen.add(key)
        url = f'https://pypi.org/pypi/{key[0]}/{key[1]}/json'
        metadata = json.loads(helpers['download'](url, limit=2_000_000))
        sources = [p for p in metadata['urls'] if p['packagetype'] == 'sdist'
                   and p['digests']['sha256'] in requirement['allowed_sha256']]
        assert len(sources) == 1, ('No uniquely locked source archive', key)
        source = sources[0]
        requests.append({'ecosystem': 'python', 'name': key[0], 'version': key[1],
                         'url': source['url'], 'sha256': source['digests']['sha256'],
                         'filename': source['filename'], 'requirement': requirement['evidence'],
                         'license_expression': metadata['info'].get('license_expression'),
                         'license_metadata': metadata['info'].get('license')})

    def collect(item):
        path = CACHE / item['filename']
        assert path.parent == CACHE and path.name == item['filename']
        if not path.exists():
            data = helpers['download'](item['url'])
            if item.get('sha256'):
                assert hashlib.sha256(data).hexdigest() == item['sha256'], item['name']
            path.write_bytes(data)
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        assert not item.get('sha256') or checksum == item['sha256'], item['name']
        item = {**item, 'sha256': checksum, 'bytes': len(data)}
        licenses = []
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
            members = {m.name: m for m in archive if m.isfile()}
            if item['ecosystem'] == 'cargo':
                manifest = next(m for name, m in members.items() if name.count('/') == 1 and name.endswith('/Cargo.toml'))
                info = tomllib.loads(archive.extractfile(manifest).read().decode('utf-8'))
                item['license_expression'] = info['package'].get('license')
                item['license_file'] = info['package'].get('license-file')
            for name, member in members.items():
                if re.search(r'(^|/)(LICENSE[^/]*|COPYING[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', name, re.I):
                    content = archive.extractfile(member).read()
                    if len(content) <= 1_000_000:
                        licenses.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest()})
        item['license_files'] = licenses
        return item

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(collect, requests))
    lock = {'schema_version': 1, 'scope': 'Superset source coverage for pinned Cargo.lock and Windows Python requirement sets; includes optional/build/other-platform packages.',
            'records': sorted(records, key=lambda p: (p['ecosystem'], p['name'], p['version'])),
            'missing_custom_pyinstaller_mapping': True}
    destination = ROOT / 'vendor/locked-source-materials.json'
    destination.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'archives': len(records), 'bytes': sum(r['bytes'] for r in records),
                      'license_files': sum(len(r['license_files']) for r in records)}))


if __name__ == '__main__':
    main()
