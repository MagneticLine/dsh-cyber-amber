"""Temporarily fetch the approved upstream cache; stream selected source archives out."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import time
import zipfile
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation/distribution'


def download_location(args):
    token = subprocess.check_output([args.gh, 'auth', 'token'], text=True).strip()
    assert re.fullmatch(r'[A-Za-z0-9_]+', token)
    config = ('url = "https://api.github.com/repos/BtbN/FFmpeg-Builds/actions/artifacts/12733159483/zip"\n'
              'header = "Authorization: Bearer ' + token + '"\n'
              'header = "Accept: application/vnd.github+json"\nheader = "Cache-Control: no-cache"\n')
    try:
        redirect = subprocess.run([args.curl, '--disable', '--config', '-', '--silent', '--show-error',
            '--fail', '--connect-timeout', '20', '--max-time', '60', '--dump-header', '-', '--output', 'NUL'],
            input=config.encode('ascii'), capture_output=True, timeout=65)
        assert redirect.returncode == 0, 'Artifact redirect request failed'
        locations = re.findall(r'^location:\s*(.+)$', redirect.stdout.decode('iso-8859-1'), re.I | re.M)
        assert len(locations) == 1
        location = locations[0].strip()
        parsed = urlsplit(location)
        assert parsed.scheme == 'https' and (parsed.hostname.endswith('.blob.core.windows.net')
            or parsed.hostname.endswith('.githubusercontent.com')), 'Unexpected blob host'
        value = parse_qs(parsed.query).get('se', [None])[0]
        expiry = datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None
        print(json.dumps({'link_expires_utc': expiry.isoformat() if expiry else None}), flush=True)
        return location, expiry
    finally:
        del token, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gh', required=True)
    parser.add_argument('--curl', required=True, help='Verified curl executable with native resume support')
    args = parser.parse_args()
    metadata = json.loads((CACHE / 'ffmpeg-artifacts-2.json').read_text(encoding='utf-8'))
    artifact = next(a for a in metadata['artifacts'] if a['id'] == 12733159483)
    assert not artifact['expired'] and artifact['size_in_bytes'] < 2_300_000_000
    path = CACHE / 'ffmpeg-cache-12733159483.zip'
    if not path.exists():
        partial = path.with_suffix('.zip.part')
        total = artifact['size_in_bytes']

        offset = partial.stat().st_size if partial.exists() else 0
        assert offset <= total
        ranges = [(p, min(total - 1, p + 8 * 1024 * 1024 - 1)) for p in range(offset, total, 8 * 1024 * 1024)]
        paths = {start: CACHE / f'cache-range-{start}.tmp' for start, _ in ranges}
        # Completed range files may survive a transport interruption. Final
        # provenance is established only by the whole upstream artifact digest.
        pending = [(s, e) for s, e in ranges if not paths[s].exists() or paths[s].stat().st_size != e - s + 1]
        for attempt in range(12):
            if not pending:
                break
            location, expiry = download_location(args)
            batch = pending[:64]
            entries = []
            for start, end in batch:
                target = paths[start]
                entries.append('\n'.join(['url = ' + json.dumps(location), f'range = "{start}-{end}"',
                    'output = ' + json.dumps(target.as_posix()), 'fail', 'silent', 'show-error',
                    'connect-timeout = 20', 'max-time = 90', 'speed-time = 15', 'speed-limit = 65536',
                    f'write-out = " {start}:%{{http_code}} "']))
            with (CACHE / 'curl-range.stderr.log').open('wb') as error:
                process = subprocess.Popen([args.curl, '--disable', '--parallel', '--parallel-max', '4',
                    '--parallel-immediate', '--config', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error)
                try:
                    process.stdin.write(('\nnext\n'.join(entries) + '\n').encode('ascii'))
                    process.stdin.close()
                    refreshed_early = False
                    while process.poll() is None:
                        size = offset + sum(p.stat().st_size for p in paths.values() if p.exists())
                        print(json.dumps({'downloaded_mb': round(size / 1_000_000, 1), 'pending_ranges': len(pending)}), flush=True)
                        if expiry and (expiry - datetime.now(timezone.utc)).total_seconds() < 45:
                            process.terminate()
                            process.wait(timeout=15)
                            refreshed_early = True
                            break
                        time.sleep(10)
                    statuses = dict((int(p), int(c)) for p, c in re.findall(r'(\d+):(\d{3})', process.stdout.read().decode('ascii')))
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=15)
            link_expired = expiry and datetime.now(timezone.utc) >= expiry
            if any(c in (401, 403, 404) for c in statuses.values()) and not link_expired:
                raise RuntimeError('Artifact range access refused; no retry or workaround')
            pending = [(s, e) for s, e in pending if not paths[s].exists() or paths[s].stat().st_size != e - s + 1]
            if not pending:
                break
            if process.returncode != 0 and not refreshed_early and not link_expired and process.returncode not in (18, 28, 35, 56):
                raise RuntimeError(f'Parallel download stopped (curl {process.returncode}); partial files retained')
        if pending:
            raise RuntimeError('Bounded transfer attempts exhausted; completed ranges retained')
        with partial.open('ab') as output:
            for start, end in ranges:
                target = paths[start]
                assert target.stat().st_size == end - start + 1
                with target.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                target.unlink()
        print(json.dumps({'committed_mb': round(total / 1_000_000, 1)}), flush=True)
        partial.replace(path)
    with path.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    if artifact.get('digest'):
        assert artifact['digest'] == 'sha256:' + checksum, 'Upstream artifact digest mismatch'
    mapping = json.loads((ROOT / 'vendor/ffmpeg-source-map.json').read_text(encoding='utf-8'))
    selected = {Path(r['recipe']).stem: r for r in mapping['records'] if r['repo'] and r['revision']}
    output = CACHE / 'ffmpeg-sources'
    output.mkdir(exist_ok=True)
    found = {}
    aliases = {}
    with zipfile.ZipFile(path) as outer:
        names = outer.namelist()
        assert len(names) == 1 and names[0].endswith('cache.tar.gz'), names
        with outer.open(names[0]) as compressed, tarfile.open(fileobj=compressed, mode='r|gz') as archive:
            for member in archive:
                name = Path(member.name).name
                if member.issym() and name.endswith('.tar.xz'):
                    aliases[name] = Path(member.linkname).name
                    continue
                match = re.fullmatch(r'(.+)_([a-f0-9]{64})\.tar\.xz', name)
                if not member.isfile() or not match or match[1] not in selected:
                    continue
                alias = aliases.get(match[1] + '.tar.xz')
                if alias and alias != name:
                    continue
                assert match[1] not in found, 'Ambiguous source cache revision: ' + match[1]
                assert member.size < 1_200_000_000, name
                target = output / name
                assert target.parent == output
                digest = hashlib.sha256()
                with archive.extractfile(member) as source, target.open('wb') as result:
                    while chunk := source.read(1024 * 1024):
                        result.write(chunk)
                        digest.update(chunk)
                found[match[1]] = {'filename': name, 'bytes': member.size, 'sha256': digest.hexdigest(),
                                     'recipe': selected[match[1]]}
                print(json.dumps({'retained': match[1], 'mb': round(member.size / 1_000_000, 1)}), flush=True)
    missing = sorted(set(selected) - set(found))
    report = {'artifact_id': artifact['id'], 'artifact_sha256': checksum, 'upstream_digest': artifact.get('digest'),
              'retained': found, 'missing_recipes': missing,
              'cache_aliases': {k: v for k, v in aliases.items() if k.removesuffix('.tar.xz') in selected}}
    (ROOT / 'vendor/ffmpeg-retained-sources.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    assert path.resolve().parent == CACHE.resolve() and not path.is_symlink()
    path.unlink()
    print(json.dumps({'retained': len(found), 'missing': missing, 'large_cache_removed': True}), flush=True)


if __name__ == '__main__':
    main()
