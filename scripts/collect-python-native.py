"""Retain CPython/native sources from the already identified Windows build recipes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution/materials'
download = runpy.run_path(str(ROOT / 'scripts/collect-source-evidence.py'))['download']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gh', required=True)
    args = parser.parse_args()
    lock_path = ROOT / 'vendor/locked-source-materials.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    requests = []
    python_commit = 'b703b2c5e704341d61e367b9b940b77ed11dded0'
    requests.append({'name': 'cpython', 'version': '3.14.10', 'revision': python_commit,
        'url': f'https://codeload.github.com/python/cpython/tar.gz/{python_commit}',
        'filename': f'cpython-{python_commit}.tar.gz', 'provenance': 'CPython version measured from bundled yt-dlp'})
    text = (CACHE / 'cpython-3.14.10-PCbuild-get_externals.bat.txt').read_text(encoding='utf-8')
    # Exclude Tk/Tcl: the pinned yt-dlp Windows directory contains no Tkinter.
    names = sorted(set(re.findall(r'set libraries=%libraries%\s+(\S+)', text)))
    names = [name for name in names if not name.startswith(('tcl-', 'tk-'))]
    for name in names:
        existing = next((r for r in lock['records'] if r.get('native_source_branch') == name), None)
        if existing:
            requests.append(existing)
            continue
        route = f'repos/python/cpython-source-deps/commits/{name}'
        response = subprocess.run([args.gh, 'api', '--method', 'GET', route], capture_output=True, check=True, timeout=60)
        commit = json.loads(response.stdout)['sha']
        requests.append({'name': 'cpython-native-' + name, 'version': name, 'revision': commit,
            'native_source_branch': name, 'provenance': 'Pinned CPython PCbuild/get_externals.bat; source branch resolved to commit',
            'url': f'https://codeload.github.com/python/cpython-source-deps/tar.gz/{commit}',
            'filename': f'cpython-native-{name}-{commit}.tar.gz'})
    curl_record = next(r for r in lock['records'] if r['name'] == 'curl-impersonate')
    with tarfile.open(CACHE / curl_record['filename']) as archive:
        member = next(m for m in archive if m.name.count('/') == 1 and m.name.endswith('/CMakeLists.txt'))
        cmake = archive.extractfile(member).read().decode('utf-8')
    variables = dict(re.findall(r'set\((\w+)\s+"([^"\n]*)"\)', cmake))
    for name in ('BROTLI', 'BORINGSSL', 'NGHTTP2', 'NGTCP2', 'NGHTTP3', 'ZLIB', 'ZSTD', 'CARES', 'CURL'):
        url = re.sub(r'\$\{(\w+)\}', lambda m: variables[m[1]], variables[name + '_URL'])
        checksum = variables[name + '_URL_HASH'].removeprefix('SHA256=')
        version = variables.get(name + '_VERSION', variables.get(name + '_COMMIT'))
        requests.append({'name': 'curl-native-' + name.lower(), 'version': version,
            'url': url, 'sha256': checksum, 'filename': 'curl-native-' + name.lower() + '-' + url.rsplit('/', 1)[1],
            'provenance': 'Exact curl-impersonate CMakeLists.txt source URL and SHA256'})

    def collect(item):
        path = CACHE / item['filename']
        assert path.parent == CACHE
        data = path.read_bytes() if path.exists() else download(item['url'], limit=100_000_000)
        checksum = hashlib.sha256(data).hexdigest()
        assert not item.get('sha256') or item['sha256'] == checksum, item['name']
        if not path.exists():
            path.write_bytes(data)
        licenses = []
        def retain(name, payload):
            if re.search(r'(^|/)(LICENSE[^/]*|COPYING[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', name, re.I):
                licenses.append({'path': name, 'sha256': hashlib.sha256(payload).hexdigest()})
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for m in archive.infolist():
                    if not m.is_dir() and m.file_size <= 2_000_000:
                        if re.search(r'(^|/)(LICENSE[^/]*|COPYING[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', m.filename, re.I):
                            retain(m.filename, archive.read(m))
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
                for m in archive:
                    if m.isfile() and m.size <= 2_000_000 and re.search(r'(^|/)(LICENSE[^/]*|COPYING[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', m.name, re.I):
                        retain(m.name, archive.extractfile(m).read())
        return {**item, 'ecosystem': 'python-native', 'sha256': checksum, 'bytes': len(data), 'license_files': licenses}

    with ThreadPoolExecutor(max_workers=3) as pool:
        added = list(pool.map(collect, requests))
    names = {r['name'] for r in added}
    lock['records'] = [r for r in lock['records'] if r['name'] not in names] + added
    lock['records'].sort(key=lambda r: (r['ecosystem'], r['name'], r['version']))
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'python_native_sources': len(added), 'bytes': sum(r['bytes'] for r in added)}))


if __name__ == '__main__':
    main()
