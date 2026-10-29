"""Read retained native sources, root Git revisions, notices and Cargo pins."""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import tarfile
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution'


def main():
    retained = json.loads((ROOT / 'vendor/ffmpeg-retained-sources.json').read_text(encoding='utf-8'))
    report = {'schema_version': 1, 'records': [], 'revision_mismatches': [], 'cargo_source_references': []}
    notices = []
    for stage, entry in sorted(retained['retained'].items()):
        path = CACHE / 'ffmpeg-sources' / entry['filename']
        with path.open('rb') as source:
            assert hashlib.file_digest(source, 'sha256').hexdigest() == entry['sha256']
        result = {'stage': stage, 'source_sha256': entry['sha256'], 'git_head': None,
                  'git_heads': {}, 'svn_revisions': [], 'notices': [], 'cargo_locks': []}
        with tarfile.open(path, 'r|xz') as archive:
            for member in archive:
                if not member.isfile():
                    continue
                name = member.name.removeprefix('./')
                if re.search(r'(^|/)\.git/HEAD$', name) and member.size < 1024:
                    head = archive.extractfile(member).read().decode('ascii').strip()
                    result['git_heads'][name] = head
                    if name == '.git/HEAD':
                        result['git_head'] = head
                if name == '.svn/wc.db':
                    data = archive.extractfile(member).read()
                    with tempfile.TemporaryDirectory(dir=CACHE) as temporary:
                        database = Path(temporary) / 'wc.db'
                        database.write_bytes(data)
                        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
                            result['svn_revisions'] = [row[0] for row in connection.execute(
                                'SELECT DISTINCT revision FROM NODES WHERE revision IS NOT NULL')]
                if re.search(r'(^|/)\.git/config$', name) and member.size < 100000:
                    config = archive.extractfile(member).read().decode('utf-8')
                    assert not re.search(r'extraheader\s*=|https?://[^\s/@]+:[^\s/@]+@', config, re.I), 'Source repo config needs credential removal before redistribution'
                if re.search(r'(^|/)\.git/', name):
                    continue
                if re.search(r'(^|/)(COPYING[^/]*|LICENSE[^/]*|NOTICE[^/]*|COPYRIGHT[^/]*|AUTHORS[^/]*)$', name, re.I) and member.size <= 2_000_000:
                    data = archive.extractfile(member).read()
                    result['notices'].append({'path': name, 'sha256': hashlib.sha256(data).hexdigest()})
                    notices.append(f'\n===== {stage}: {name} =====\n')
                    try:
                        notices.append(data.decode('utf-8'))
                    except UnicodeDecodeError:
                        notices.append('Original non-UTF-8 text is preserved verbatim in the named native source archive.\n')
                if name == 'Cargo.lock' and member.size < 5_000_000:
                    data = archive.extractfile(member).read()
                    cargo = tomllib.loads(data.decode('utf-8'))
                    result['cargo_locks'].append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'packages': len(cargo['package'])})
                    for p in cargo['package']:
                        if p.get('source', '').startswith('registry+'):
                            report['cargo_source_references'].append({'component': stage, 'name': p['name'], 'version': p['version'],
                                'sha256': p['checksum'], 'url': f'https://static.crates.io/crates/{p["name"]}/{p["name"]}-{p["version"]}.crate'})
        expected = entry['recipe']['revision']
        if re.fullmatch(r'[a-f0-9]{40}', expected) and expected not in result['git_heads'].values():
            if stage == '50-amf':
                exported = json.loads((ROOT / 'vendor/amf-export-verification.json').read_text(encoding='utf-8'))
                assert exported['all_files_identical'] and exported['revision'] == expected
                assert exported['cached_source_sha256'] == entry['sha256']
                result['export_verification'] = exported
            else:
                report['revision_mismatches'].append({'stage': stage, 'expected': expected, 'head': result['git_head']})
        if expected.isdecimal() and int(expected) not in result['svn_revisions']:
            report['revision_mismatches'].append({'stage': stage, 'expected': expected, 'svn_revisions': result['svn_revisions']})
        result['expected_revision'] = expected
        report['records'].append(result)
        print(json.dumps({'inspected': stage, 'notices': len(result['notices'])}), flush=True)
    (ROOT / 'vendor/native-source-inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    assert not report['revision_mismatches'], ('Native source revision mismatch; do not clear publication gate', report['revision_mismatches'])
    (ROOT / 'vendor/NATIVE_SOURCE_NOTICES.txt').write_text('Retained FFmpeg build-source notices (conservative superset, not linked-code inventory).\n'
        + ''.join(notices).replace('\r\n', '\n'), encoding='utf-8', newline='\n')
    print(json.dumps({'native_archives': len(report['records']), 'cargo_source_references': len(report['cargo_source_references']),
                      'notice_files': sum(len(r['notices']) for r in report['records']), 'revision_mismatches': 0}))


if __name__ == '__main__':
    main()
