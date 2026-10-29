"""Offline source/notice evidence inventory. Never certifies legal compliance."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def material_progress(source_files, sidecar, native_sidecar=None):
    progress = {'verified': False, 'gifski_complete': False, 'python_complete': False, 'ffmpeg_complete': False}
    if not sidecar:
        return progress
    verify = runpy.run_path(str(ROOT / 'scripts/source_materials.py'))['verify']
    progress['sidecar'] = verify(sidecar)
    materials = json.loads((ROOT / 'vendor/locked-source-materials.json').read_text(encoding='utf-8'))
    with tarfile.open(sidecar, 'r:gz') as archive:
        assert json.load(archive.extractfile('source-materials/vendor/locked-source-materials.json')) == materials
        for r in materials['records']:
            with archive.extractfile('source-materials/sources/' + r['filename']) as source:
                assert hashlib.file_digest(source, 'sha256').hexdigest() == r['sha256'], r['filename']
        notices = archive.extractfile('source-materials/vendor/SOURCE_MATERIAL_NOTICES.txt').read().decode('utf-8')
    records = {(r['name'], r['version']): r for r in materials['records']}
    cargo = tomllib.loads(source_files['gifski']['Cargo.lock'].decode('utf-8'))['package']
    expected = [p for p in cargo if p.get('source')]
    for p in expected:
        record = records[(p['name'], p['version'])]
        if p['source'].startswith('registry+'):
            assert record['sha256'] == p['checksum'], p['name']
        else:
            assert record['revision'] == p['source'].rsplit('#', 1)[1], p['name']
    runtime = json.loads((ROOT / 'vendor/runtime-source-evidence.json').read_text(encoding='utf-8'))
    assert runtime['gifski_rustc_revisions'] == ['6b00bc3880198600130e1cf62b8f8a93494488cc']
    assert 'gif-dispose 5.0.1' in notices and 'Apache-2.0' in notices
    progress.update(verified=True, gifski_complete=True, gifski_lock_sources=len(expected),
                    rustc_revision=runtime['gifski_rustc_revisions'][0])
    requirements = {}
    for path in ('bundle/requirements/default.txt', 'bundle/requirements/curl-cffi.txt', 'bundle/requirements/win-x64-pyinstaller.txt'):
        text = source_files['yt-dlp'][path].decode('utf-8')
        for block in re.split(r'\n(?=[\w.-]+(?:==| @ ))', text):
            m = re.match(r'([\w.-]+)==([^\s;\\]+)', block)
            if m:
                requirements.setdefault((m[1], m[2]), set()).update(re.findall(r'--hash=sha256:([a-f0-9]{64})', block))
    for key, allowed in requirements.items():
        assert records[key]['sha256'] in allowed, key
    assert materials['custom_pyinstaller_mapping']['wheel_sha256'] in source_files['yt-dlp']['bundle/requirements/win-x64-pyinstaller.txt'].decode('utf-8')
    assert records[('pyinstaller', '6.22.0')]['revision'] == materials['custom_pyinstaller_mapping']['source_revision']
    assert records[('curl-impersonate', '2.3.0')]['revision'] == 'aa68bd3ddb4d03120c2f0ba0c5c631613ed9ab52'
    assert ('cpython-PCbuild-python.props', '3.14.10') in records
    assert records[('cpython', '3.14.10')]['revision'] == 'b703b2c5e704341d61e367b9b940b77ed11dded0'
    native_names = {r['name'] for r in materials['records'] if r['ecosystem'] == 'python-native'}
    expected_python_native = {'cpython'} | {'cpython-native-' + name for name in (
        'bzip2-1.0.8', 'libffi-3.4.4', 'openssl-3.5.9', 'mpdecimal-4.0.0',
        'sqlite-3.50.4.0', 'xz-5.2.5', 'zlib-ng-2.2.4', 'zstd-1.5.7')}
    expected_python_native |= {'curl-native-' + name for name in (
        'brotli', 'boringssl', 'nghttp2', 'ngtcp2', 'nghttp3', 'zlib', 'zstd', 'cares', 'curl')}
    assert expected_python_native <= native_names, 'Python/native source payload is incomplete'
    progress.update(python_complete=True, python_requirement_sources=len(requirements),
        python_native_sources=len(expected_python_native),
        python_scope='Pinned Python sdists, custom bootloader source/recipes, full CPython snapshot, native dependency source archives mapped from CPython/curl recipes, and retained notices. Some CPython native revisions are recipe-derived, not runtime measurements; not a bit-identical rebuild or full linked-code SBOM certification.')
    if native_sidecar:
        progress['native_sidecar'] = verify(native_sidecar)
        with tarfile.open(native_sidecar, 'r:gz') as archive:
            def record(name):
                return json.load(archive.extractfile('source-materials/vendor/' + name))
            retained = record('ffmpeg-retained-sources.json')
            inspected = record('native-source-inspection.json')
            mapped = record('ffmpeg-source-map.json')
            assert not retained['missing_recipes'] and not inspected['revision_mismatches']
            assert 'sha256:' + retained['artifact_sha256'] == retained['upstream_digest']
            expected_stages = {Path(r['recipe']).stem for r in mapped['records'] if r['repo'] and r['revision']}
            assert expected_stages == set(retained['retained'])
            assert expected_stages == {r['stage'] for r in inspected['records']}
            for r in retained['retained'].values():
                with archive.extractfile('source-materials/ffmpeg/' + r['filename']) as source:
                    assert hashlib.file_digest(source, 'sha256').hexdigest() == r['sha256']
            for r in inspected['records']:
                assert r['source_sha256'] == retained['retained'][r['stage']]['sha256']
            for ref in inspected['cargo_source_references']:
                assert records[(ref['name'], ref['version'])]['sha256'] == ref['sha256']
            amf = record('amf-export-verification.json')
            assert amf['all_files_identical'] and amf['cached_source_sha256'] == retained['retained']['50-amf']['sha256']
            tree_file = f'source-materials/build-evidence/AMF-{amf["revision"]}-tree.json'
            assert digest(archive.extractfile(tree_file).read()) == amf['tree_sha256']
            assert archive.getmember('source-materials/vendor/NATIVE_SOURCE_NOTICES.txt').size > 0
        progress.update(ffmpeg_complete=True, native_archives=len(expected_stages),
                        native_cargo_references=len(inspected['cargo_source_references']),
                        ffmpeg_scope='Exact build-cache source archives, root/nested Git and SVN pins, AMF file-tree comparison, native notices and Cargo source checks. Conservative superset; not a linked-code SBOM or legal certification.')
    return progress


def inventory(sidecar, materials_sidecar=None, native_sidecar=None):
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
    progress = material_progress(source_files, materials_sidecar, native_sidecar)
    blockers = []
    if not progress['ffmpeg_complete']:
        blockers.append({'id': 'DIST-01', 'component': 'ffmpeg', 'reason': 'Native build-source retention and notice/revision inspection have not been verified.'})
    if not progress['gifski_complete']:
        blockers.append({'id': 'DIST-02', 'component': 'gifski', 'reason': 'Additional pinned Cargo sources and retained notices have not been verified.'})
    if not progress['python_complete']:
        blockers.append({'id': 'DIST-03', 'component': 'yt-dlp', 'reason': 'Additional Python/native-build and custom PyInstaller source records have not been verified.'})
    blockers.append({'id': 'DIST-04', 'component': 'candidate-package', 'reason': 'Frozen rc.1 does not contain the newly retained aggregate notices. Prepare and verify a new candidate without replacing rc.1; user review is required before any public action.'})
    return {
        'schema_version': 1,
        'publication_ready': False,
        'additional_source_progress': progress,
        'scope': 'Evidence inventory, not a complete SBOM, source closure, or legal certification.',
        'main_components': {name: {'version': binary_lock['components'][name]['version'],
                                  'source': lock['sources'][name],
                                  'license': {'gifski': 'AGPL-3.0-or-later', 'ffmpeg': 'LGPL-3.0-or-later',
                                              'yt-dlp': 'Unlicense source; GPLv3+ official bundled aggregate'}[name]}
                            for name in ('gifski', 'ffmpeg', 'yt-dlp')},
        'preserved_license_files': licenses,
        'gifski_lock_entries': crates,
        'gifski_lock_scope': 'Includes optional/build dependencies; matching source archives and retained notices are checked when the additional sidecar is supplied. Not proof every entry is linked.',
        'ffmpeg_enabled_features': re.findall(r'--enable-([\w-]+)', (ROOT / 'vendor/ffmpeg-buildconf.txt').read_text(encoding='utf-8')),
        'ffmpeg_build_recipes': recipes,
        'ffmpeg_recipe_scope': 'Preserved recipe evidence; moving branch tips and transitive patches must be resolved to the actual binary build, not current upstream heads.',
        'ytdlp_notice_entries': python_notices,
        'ytdlp_notice_scope': 'Upstream notices cover multiple platforms; presence here does not prove inclusion in this Windows build or identify an exact bundled version.',
        'publication_blockers': blockers,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar', type=Path, required=True)
    parser.add_argument('--materials-sidecar', type=Path, help='Verify the additional source payload before clearing component checks')
    parser.add_argument('--native-sidecar', type=Path, help='Verify the separate large FFmpeg native-source payload')
    parser.add_argument('--write', action='store_true', help='Explicitly update the tracked evidence inventory')
    parser.add_argument('--require-public-ready', action='store_true')
    args = parser.parse_args()
    result = inventory(args.sidecar, args.materials_sidecar, args.native_sidecar)
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
