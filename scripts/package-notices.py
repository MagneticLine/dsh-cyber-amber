"""Verify actual tarball notices against reviewed project/installed bytes."""
import hashlib

REQUIRED = (
    'NOTICE.md', 'LICENSE', 'docs/SOURCES.md', 'docs/SOURCE-MATERIALS.md',
    'vendor/SOURCE_MATERIAL_NOTICES.txt', 'vendor/NATIVE_SOURCE_NOTICES.txt',
    'vendor/locked-source-materials.json', 'vendor/ffmpeg-retained-sources.json',
    'vendor/native-source-inspection.json', 'vendor/runtime-source-evidence.json',
    'vendor/licenses/ffmpeg-LICENSE.txt', 'vendor/licenses/gifski-LICENSE.md',
    'vendor/licenses/GPL-3.0.txt', 'vendor/licenses/yt-dlp-LICENSE.txt',
    'vendor/licenses/yt-dlp-THIRD_PARTY_LICENSES.txt',
)


def verify_notices(archive, root):
    names = archive.getnames()
    records = []
    for name in REQUIRED:
        member_name = 'package/' + name
        assert names.count(member_name) == 1, 'Missing or duplicate notice/evidence: ' + name
        member = archive.getmember(member_name)
        assert member.isfile(), 'Notice must be a regular file: ' + name
        expected = (root / name).read_bytes()
        data = archive.extractfile(member).read()
        assert data and data == expected, 'Packaged notice/evidence differs: ' + name
        records.append({'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    notice = archive.extractfile('package/NOTICE.md').read().decode('utf-8')
    assert 'vendor/SOURCE_MATERIAL_NOTICES.txt' in notice and 'vendor/NATIVE_SOURCE_NOTICES.txt' in notice
    return {'verified': True, 'files': records}
