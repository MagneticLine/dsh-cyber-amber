"""Add independently identified PyInstaller/Rust source and license evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'scripts/collect-source-evidence.py'))
CACHE = ROOT / '.validation/distribution/materials'


def main():
    lock_path = ROOT / 'vendor/locked-source-materials.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    extras = [
        {'ecosystem': 'source-evidence', 'name': 'pyinstaller', 'version': '6.22.0',
         'revision': '70fc17210920bce17f4ab09bbf8104b0dbd45338',
         'url': 'https://codeload.github.com/pyinstaller/pyinstaller/tar.gz/70fc17210920bce17f4ab09bbf8104b0dbd45338',
         'filename': 'pyinstaller-70fc17210920bce17f4ab09bbf8104b0dbd45338.tar.gz',
         'license_expression': 'GPL-2.0-or-later WITH Bootloader-exception',
         'provenance': 'https://github.com/yt-dlp/Pyinstaller-Builds/releases/tag/2026.08.19.215425'},
        {'ecosystem': 'build-evidence', 'name': 'yt-dlp-pyinstaller-builds', 'version': '2026.08.19.215425',
         'revision': '5eb86b862d61adc3df0f44e6e0b815b7d74fa3f5',
         'url': 'https://codeload.github.com/yt-dlp/Pyinstaller-Builds/tar.gz/5eb86b862d61adc3df0f44e6e0b815b7d74fa3f5',
         'filename': 'pyinstaller-builds-5eb86b862d61adc3df0f44e6e0b815b7d74fa3f5.tar.gz'},
        {'ecosystem': 'source-evidence', 'name': 'curl-impersonate', 'version': '2.3.0',
         'revision': 'aa68bd3ddb4d03120c2f0ba0c5c631613ed9ab52',
         'url': 'https://codeload.github.com/lexiforest/curl-impersonate/tar.gz/aa68bd3ddb4d03120c2f0ba0c5c631613ed9ab52',
         'filename': 'curl-impersonate-aa68bd3ddb4d03120c2f0ba0c5c631613ed9ab52.tar.gz',
         'evidence': 'curl_cffi 0.17.0 README identifies curl-impersonate 2.3.0; DLL embeds libcurl/8.23.0-IMPERSONATE'},
    ]
    for filename in ('LICENSE', 'PCbuild/python.props', 'PCbuild/get_externals.bat'):
        extras.append({'ecosystem': 'build-evidence-text', 'name': 'cpython-' + filename.replace('/', '-'), 'version': '3.14.10',
                       'revision': 'b703b2c5e704341d61e367b9b940b77ed11dded0',
                       'url': 'https://raw.githubusercontent.com/python/cpython/b703b2c5e704341d61e367b9b940b77ed11dded0/' + filename,
                       'filename': 'cpython-3.14.10-' + filename.replace('/', '-') + '.txt'})
    for filename in ('LICENSE-MIT', 'LICENSE-APACHE', 'COPYRIGHT'):
        extras.append({'ecosystem': 'toolchain-notice', 'name': 'rust-' + filename.lower(), 'version': '1.88.0',
                       'revision': '6b00bc3880198600130e1cf62b8f8a93494488cc',
                       'url': 'https://raw.githubusercontent.com/rust-lang/rust/6b00bc3880198600130e1cf62b8f8a93494488cc/' + filename,
                       'filename': 'rust-1.88.0-' + filename + '.txt',
                       'evidence': 'Exact rustc revision embedded in the pinned gifski.exe'})
    for item in extras:
        path = CACHE / item['filename']
        if not path.exists():
            path.write_bytes(helpers['download'](item['url']))
        data = path.read_bytes()
        existing = next((r for r in lock['records'] if r['filename'] == item['filename']), None)
        checksum = hashlib.sha256(data).hexdigest()
        if existing:
            assert existing['sha256'] == checksum, item['filename']
        item.update(sha256=checksum, bytes=len(data))
        lock['records'] = [r for r in lock['records'] if r['filename'] != item['filename']] + [item]
    lock['missing_custom_pyinstaller_mapping'] = False
    lock['custom_pyinstaller_mapping'] = {
        'wheel_sha256': '294099ecb5fdd2a13ae4c29006d4e335b697a63b6a16cf052b90ec2b40bef05a',
        'source_revision': extras[0]['revision'], 'recipe_revision': extras[1]['revision'],
        'evidence': extras[0]['provenance'],
        'scope': 'Upstream release explicitly identifies source revision; recipes and source are preserved, not a byte-identical rebuild claim.'}
    lock['records'].sort(key=lambda r: (r['ecosystem'], r['name'], r['version']))
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'extra_records': len(extras), 'total_records': len(lock['records'])}))


if __name__ == '__main__':
    main()
