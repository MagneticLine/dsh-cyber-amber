"""Compare AMF's metadata-free cache export to its exact commit snapshot."""
import hashlib
import json
from pathlib import Path
import argparse
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gh', required=True)
    args = parser.parse_args()
    retained = json.loads((ROOT / 'vendor/ffmpeg-retained-sources.json').read_text(encoding='utf-8'))
    entry = retained['retained']['50-amf']
    revision = entry['recipe']['revision']
    path = CACHE / f'AMF-{revision}-tree.json'
    route = f'repos/GPUOpen-LibrariesAndSDKs/AMF/git/trees/{revision}?recursive=1'
    if not path.exists():
        response = subprocess.run([args.gh, 'api', '--method', 'GET', route], capture_output=True, check=True, timeout=60)
        assert len(response.stdout) < 32_000_000
        path.write_bytes(response.stdout)

    def files(source):
        result = {}
        with tarfile.open(source, 'r:*') as archive:
            for member in archive:
                if member.isfile():
                    name = member.name.removeprefix('./')
                    if not name.startswith('.git/'):
                        data = archive.extractfile(member).read()
                        result[name] = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        return result

    cached = files(CACHE / 'ffmpeg-sources' / entry['filename'])
    tree = json.loads(path.read_text(encoding='utf-8'))
    assert not tree['truncated']
    # The pinned build recipe explicitly removes .git and Thirdparty before caching.
    upstream = {r['path']: r['sha'] for r in tree['tree'] if r['type'] == 'blob' and not r['path'].startswith('Thirdparty/')}
    assert cached == upstream, {'missing': sorted(set(upstream) - set(cached)),
        'extra': sorted(set(cached) - set(upstream)),
        'changed': [n for n in cached.keys() & upstream.keys() if cached[n] != upstream[n]]}
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'stage': '50-amf', 'revision': revision, 'files': len(cached),
              'tree_sha256': checksum, 'tree_api_route': route, 'cached_source_sha256': entry['sha256'],
              'comparison': 'Git blob SHA1 for every cached file against the untruncated commit tree, excluding Thirdparty as specified by the build recipe',
              'all_files_identical': True}
    (ROOT / 'vendor/amf-export-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
