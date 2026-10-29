"""Retain registry sources referenced by the inspected FFmpeg dependency locks."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution/materials'
download = runpy.run_path(str(ROOT / 'scripts/collect-source-evidence.py'))['download']


def main():
    lock_path = ROOT / 'vendor/locked-source-materials.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    inspection = json.loads((ROOT / 'vendor/native-source-inspection.json').read_text(encoding='utf-8'))
    known = {(r['name'], r['version']): r for r in lock['records']}
    pending = {}
    for ref in inspection['cargo_source_references']:
        key = (ref['name'], ref['version'])
        if key in known:
            assert known[key]['sha256'] == ref['sha256'], key
        elif key in pending:
            assert pending[key]['sha256'] == ref['sha256'], key
        else:
            pending[key] = ref

    def collect(ref):
        filename = f'{ref["name"]}-{ref["version"]}.crate'
        path = CACHE / filename
        assert path.parent == CACHE
        data = path.read_bytes() if path.exists() else download(ref['url'])
        assert hashlib.sha256(data).hexdigest() == ref['sha256'], filename
        if not path.exists():
            path.write_bytes(data)
        licenses = []
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive:
                if member.isfile() and member.size <= 1_000_000 and re.search(
                        r'(^|/)(LICENSE[^/]*|COPYING[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', member.name, re.I):
                    payload = archive.extractfile(member).read()
                    licenses.append({'path': member.name, 'sha256': hashlib.sha256(payload).hexdigest()})
        return {'ecosystem': 'cargo', 'name': ref['name'], 'version': ref['version'],
                'url': ref['url'], 'sha256': ref['sha256'], 'filename': filename,
                'bytes': len(data), 'license_files': licenses, 'evidence': 'native-source-inspection.json'}

    # No source code is installed or executed. Hashes come from retained locks.
    with ThreadPoolExecutor(max_workers=4) as pool:
        added = list(pool.map(collect, pending.values()))
    lock['records'].extend(added)
    lock['records'].sort(key=lambda r: (r['ecosystem'], r['name'], r['version']))
    lock['scope'] = 'Conservative source superset for Gifski, native FFmpeg dependency Cargo locks and Windows Python build requirements; not a linked-code SBOM.'
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'native_cargo_references': len(inspection['cargo_source_references']),
                      'added_sources': len(added), 'total_material_records': len(lock['records'])}))


if __name__ == '__main__':
    main()
