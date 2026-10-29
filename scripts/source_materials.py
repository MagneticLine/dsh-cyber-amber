"""Build and independently verify opaque source archives and retained notices."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution'


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(path):
    """Check every member against the embedded inventory, not just gzip validity."""
    with tarfile.open(path, 'r:gz') as archive:
        inventory = json.load(archive.extractfile('source-materials/inventory.json'))
        expected = {r['archive_path']: r for r in inventory['files']}
        assert len(expected) == len(inventory['files']), 'Duplicate inventory paths'
        assert all(name.startswith('source-materials/') and '..' not in Path(name).parts
                   for name in expected), 'Invalid inventory path'
        seen = set()
        inventory_count = 0
        for member in archive:
            if member.name == 'source-materials/inventory.json':
                inventory_count += 1
                assert inventory_count == 1 and member.isfile(), 'Duplicate/invalid inventory'
                continue
            assert member.name in expected and member.name not in seen and member.isfile(), member.name
            record = expected[member.name]
            assert member.size == record['bytes'], member.name
            with archive.extractfile(member) as source:
                assert hashlib.file_digest(source, 'sha256').hexdigest() == record['sha256'], member.name
            seen.add(member.name)
        assert seen == set(expected), 'Missing source/notice payload'
    return {'files': len(seen), 'bytes': path.stat().st_size, 'sha256': file_hash(path)}


def restore(path):
    """Restore only opaque cached inputs, never source trees or tracked files."""
    result = verify(path)
    restored = 0
    with tarfile.open(path, 'r:gz') as archive:
        inventory = json.load(archive.extractfile('source-materials/inventory.json'))
        for record in inventory['files']:
            relative = record['archive_path'].removeprefix('source-materials/')
            category, separator, name = relative.partition('/')
            if category not in ('sources', 'ffmpeg', 'build-evidence'):
                continue
            assert separator and Path(name).name == name and name not in ('.', '..')
            directory = CACHE / {'sources': 'materials', 'ffmpeg': 'ffmpeg-sources', 'build-evidence': ''}[category]
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / name
            assert target.resolve().parent == directory.resolve() and not target.is_symlink()
            if target.exists():
                assert file_hash(target) == record['sha256'], 'Existing cached input differs: ' + name
                continue
            with archive.extractfile(record['archive_path']) as source, target.open('xb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            assert file_hash(target) == record['sha256']
            restored += 1
    return {**result, 'restored_cached_files': restored}


def build(destination, include_ffmpeg=False, ffmpeg_only=False):
    materials = json.loads((ROOT / 'vendor/locked-source-materials.json').read_text(encoding='utf-8'))
    inputs = [(CACHE / 'materials' / r['filename'], 'sources/' + r['filename'], r['sha256']) for r in materials['records']]
    if ffmpeg_only:
        inputs = []
    if include_ffmpeg:
        ffmpeg = json.loads((ROOT / 'vendor/ffmpeg-retained-sources.json').read_text(encoding='utf-8'))
        inputs.extend((CACHE / 'ffmpeg-sources' / r['filename'], 'ffmpeg/' + r['filename'], r['sha256'])
                      for r in ffmpeg['retained'].values())
    notices = ['Third-party source-material notices\n',
               'This is a conservative superset of build/runtime/platform dependencies.\n'
               'Inclusion does not assert every component is linked into the Windows binaries.\n'
               'Original licensing statements are retained; no aggregate relicensing is made.\n']
    notice_count = 0
    for r in materials['records']:
        path = CACHE / 'materials' / r['filename']
        assert file_hash(path) == r['sha256'], str(path)
        if r['ecosystem'] == 'toolchain-notice':
            notices.extend(['\n===== ' + r['filename'] + ' =====\n', path.read_text(encoding='utf-8')])
            continue
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for license in r.get('license_files', []):
                    data = archive.read(license['path'])
                    assert hashlib.sha256(data).hexdigest() == license['sha256']
                    notices.append(f'\n===== {r["name"]} {r["version"]}: {license["path"]} =====\n')
                    try:
                        notices.append(data.decode('utf-8'))
                    except UnicodeDecodeError:
                        notices.append('Original non-UTF-8 notice retained verbatim in the named source archive.\n')
                    notice_count += 1
            continue
        if not tarfile.is_tarfile(path):
            continue
        with tarfile.open(path, 'r:*') as archive:
            for license in r.get('license_files', []):
                data = archive.extractfile(license['path']).read()
                assert hashlib.sha256(data).hexdigest() == license['sha256']
                notices.append(f'\n===== {r["name"]} {r["version"]}: {license["path"]} =====\n')
                try:
                    notices.append(data.decode('utf-8'))
                except UnicodeDecodeError:
                    notices.append('Original non-UTF-8 notice retained verbatim in the named source archive.\n')
                notice_count += 1
            if r['ecosystem'] in ('source-evidence', 'build-evidence'):
                for member in archive:
                    if member.isfile() and member.name.count('/') == 1 and re.search(r'/(COPYING[^/]*|LICENSE[^/]*|NOTICE[^/]*)$', member.name, re.I):
                        notices.extend([f'\n===== {r["name"]}: {member.name} =====\n', archive.extractfile(member).read().decode('utf-8')])
    notices.append('\nDual-license coverage: gif-dispose 5.0.1 declares MIT OR Apache-2.0 in its retained Cargo.toml. '
                   'Its crate omits license text; the Apache-2.0 option and full Rust LICENSE-APACHE text retained above are used. '
                   'The two winapi GNU import-library crates explicitly permit Apache-2.0 or MIT in src/lib.rs; '
                   'their parent winapi 0.3.9 license texts and copyright notices are retained above.\n')
    notice_path = ROOT / 'vendor/SOURCE_MATERIAL_NOTICES.txt'
    # The readable aggregate is a new UTF-8/LF document. Source archives retain
    # the original notice bytes and line endings verbatim.
    text = ''.join(notices).replace('\r\n', '\n')
    assert '\ufffd' not in text
    notice_path.write_text(text, encoding='utf-8', newline='\n')
    for relative in ('vendor/locked-source-materials.json', 'vendor/ffmpeg-source-map.json',
                     'vendor/runtime-source-evidence.json',
                     'vendor/SOURCE_MATERIAL_NOTICES.txt', 'docs/SOURCE-MATERIALS.md'):
        path = ROOT / relative
        if not ffmpeg_only:
            inputs.append((path, relative, file_hash(path)))
    if include_ffmpeg:
        for relative in ('vendor/ffmpeg-retained-sources.json', 'vendor/native-source-inspection.json',
                         'vendor/NATIVE_SOURCE_NOTICES.txt', 'vendor/amf-export-verification.json',
                         'vendor/ffmpeg-source-map.json'):
            path = ROOT / relative
            inputs.append((path, relative, file_hash(path)))
        for path in sorted(CACHE.glob('job-*.log')):
            inputs.append((path, 'build-evidence/' + path.name, file_hash(path)))
        for filename in ('evidence.json', 'ffmpeg-run.json', 'ffmpeg-jobs.json',
                         'ffmpeg-artifacts-1.json', 'ffmpeg-artifacts-2.json'):
            path = CACHE / filename
            inputs.append((path, 'build-evidence/' + filename, file_hash(path)))
        for path in CACHE.glob('AMF-*-tree.json'):
            inputs.append((path, 'build-evidence/' + path.name, file_hash(path)))
    unique = {}
    for item in inputs:
        if item[1] in unique:
            assert unique[item[1]][2] == item[2], 'Conflicting source inventory paths'
        unique[item[1]] = item
    inputs = list(unique.values())
    inventory = {'schema_version': 1, 'scope': 'Additional source materials; main program snapshots remain in the separate upstream-sources sidecar.',
                 'files': []}
    for path, relative, checksum in inputs:
        assert file_hash(path) == checksum, str(path)
        inventory['files'].append({'archive_path': 'source-materials/' + relative,
                                   'bytes': path.stat().st_size, 'sha256': checksum})
    payload = json.dumps(inventory, indent=2).encode('utf-8') + b'\n'
    with destination.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as compressed, tarfile.open(fileobj=compressed, mode='w') as output:
        entry = tarfile.TarInfo('source-materials/inventory.json')
        entry.size, entry.mode = len(payload), 0o644
        output.addfile(entry, io.BytesIO(payload))
        for path, relative, _ in inputs:
            entry = tarfile.TarInfo('source-materials/' + relative)
            entry.size, entry.mode = path.stat().st_size, 0o644
            with path.open('rb') as source:
                output.addfile(entry, source)
    result = verify(destination)
    result.update(notice_files=notice_count, include_ffmpeg=include_ffmpeg, artifact=destination.name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--verify', type=Path)
    operation.add_argument('--restore', type=Path, help='Verify a sidecar and restore opaque inputs under the project cache')
    parser.add_argument('--include-ffmpeg', action='store_true')
    parser.add_argument('--ffmpeg-only', action='store_true', help='Keep the large native sources separate from Cargo/Python sources')
    parser.add_argument('--output', type=Path, help='New local artifact path; existing artifacts are never overwritten')
    args = parser.parse_args()
    destination = args.output or ROOT / 'dist/dsh-cyber-amber-0.2.1-rc.1-third-party-sources-20261029.tar.gz'
    if not args.verify and not args.restore and destination.exists():
        raise FileExistsError('Choose a new artifact filename instead of replacing retained evidence')
    result = verify(args.verify) if args.verify else restore(args.restore) if args.restore else build(destination, args.include_ffmpeg or args.ffmpeg_only, args.ffmpeg_only)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
