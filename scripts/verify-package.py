"""Check the actual npm tarball, including every pinned executable and support DLL."""
import hashlib
import json
import runpy
from pathlib import Path
import struct
import sys
import tarfile

path = Path(sys.argv[1])
with tarfile.open(path, 'r:gz') as archive:
    package = json.load(archive.extractfile('package/package.json'))
    manifest = json.load(archive.extractfile('package/vendor/manifest.json'))
    assert package['os'] == ['win32'] and package['cpu'] == ['x64']
    assert not set(package['scripts']).intersection(['preinstall', 'install', 'postinstall', 'prepare'])
    for name, info in manifest['files'].items():
        member = archive.getmember('package/vendor/' + name)
        assert member.isfile() and member.size == info['bytes'], name
        with archive.extractfile(member) as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256'], name
    for name in manifest['binaries'].values():
        with archive.extractfile('package/vendor/' + name) as stream:
            data = stream.read(4096)
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        assert data[:2] == b'MZ' and data[offset:offset+4] == b'PE\0\0'
        assert struct.unpack_from('<H', data, offset + 4)[0] == 0x8664, name
    names = archive.getnames()
    assert not any('/.validation/' in name or '/dist/' in name for name in names)
    matched = 0
    notice_payload = None
    if len(sys.argv) > 2:
        installed = Path(sys.argv[2])
        previous = json.loads((installed / 'package.json').read_text(encoding='utf-8'))
        for key in ['name', 'version', 'exports', 'dsh', 'engines', 'os', 'cpu']:
            assert package[key] == previous[key], key
        for name in names:
            if name.startswith('package/lib/') or name == 'package/vendor/manifest.json':
                assert archive.extractfile(name).read() == (installed / name.removeprefix('package/')).read_bytes(), name
                matched += 1
        if package['version'] != '0.2.0':
            helper = runpy.run_path(str(Path(__file__).with_name('package-notices.py')))
            notice_payload = helper['verify_notices'](archive, installed)
    with path.open('rb') as stream:
        archive_sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    print(json.dumps({'package': package['name'], 'version': package['version'], 'platform': 'win32-x64',
                      'tarball_bytes': path.stat().st_size, 'verified_dependency_files': len(manifest['files']),
                      'matched_installed_runtime_files': matched, 'notice_payload': notice_payload,
                      'sha256': archive_sha256}))
