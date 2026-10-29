"""Collect bounded, read-only upstream records. Does not execute downloaded code."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.validation' / 'distribution'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def download(url, limit=12_000_000):
    request = urllib.request.Request(url, headers={'User-Agent': 'Cyber-Amber-source-evidence/1', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        if int(response.headers.get('Content-Length', '0')) > limit:
            raise ValueError('Source response exceeds bounded download limit')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Source response exceeds bounded download limit')
    return data


def source_trees(sidecar):
    lock = json.loads((ROOT / 'vendor/source-code.lock.json').read_text(encoding='utf-8'))
    trees = {}
    with tarfile.open(sidecar, 'r:gz') as outer:
        for component in ('gifski', 'ffmpeg-builds', 'yt-dlp'):
            entry = lock['sources'][component]
            data = outer.extractfile('upstream-sources/' + entry['file']).read()
            assert sha(data) == entry['sha256']
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                trees[component] = {m.name.partition('/')[2]: archive.extractfile(m).read()
                                    for m in archive if m.isfile()}
    return trees


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar', type=Path, required=True)
    parser.add_argument('--gh', required=True, help='Verified GitHub CLI executable; read-only API operations')
    parser.add_argument('--logs', action='store_true', help='Also retain bounded logs for the exact upstream build jobs')
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    trees = source_trees(args.sidecar)
    report = {'schema_version': 1, 'public_mutations': False, 'records': {}, 'python_requirements': [],
              'ffmpeg_recipe_pins': [], 'availability_errors': []}

    def api(label, route, json_result=True):
        path = CACHE / (label + ('.json' if json_result else '.log'))
        if not path.exists():
            argv = [args.gh, 'api', '--method', 'GET']
            if not json_result:
                # Captured as bytes, never replayed to a terminal. Strip ANSI in
                # derived findings; this is not a permission override.
                argv.append('--allow-escape-sequences')
            result = subprocess.run(argv + [route], capture_output=True, timeout=120)
            if result.returncode:
                report['availability_errors'].append({'record': label, 'message': result.stderr.decode('utf-8')[-1000:]})
                return None
            if len(result.stdout) > 40_000_000:
                raise ValueError('Upstream log exceeds retained evidence budget')
            if json_result:
                json.loads(result.stdout)
            path.write_bytes(result.stdout)
        data = path.read_bytes()
        report['records'][label] = {'api_route': route, 'sha256': sha(data), 'bytes': len(data)}
        return json.loads(data) if json_result else re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', data.decode('utf-8', errors='strict'))

    for file in ('bundle/requirements/default.txt', 'bundle/requirements/curl-cffi.txt', 'bundle/requirements/win-x64-pyinstaller.txt'):
        text = trees['yt-dlp'][file].decode('utf-8')
        blocks = re.split(r'\n(?=[\w.-]+(?:==| @ ))', text)
        for block in blocks:
            m = re.match(r'([\w.-]+)==([^\s;\\]+)', block)
            if m:
                report['python_requirements'].append({'name': m[1], 'version': m[2], 'evidence': file,
                                                       'allowed_sha256': re.findall(r'--hash=sha256:([a-f0-9]{64})', block)})
            else:
                m = re.search(r'^([\w.-]+) @ (https://[^\s\\]+)', block, re.M)
                if m:
                    report['python_requirements'].append({'name': m[1], 'artifact_url': m[2], 'evidence': file,
                                                           'allowed_sha256': re.findall(r'--hash=sha256:([a-f0-9]{64})', block)})
    for name, raw in sorted(trees['ffmpeg-builds'].items()):
        if name.startswith('scripts.d/') and name.endswith('.sh'):
            text = raw.decode('utf-8')
            report['ffmpeg_recipe_pins'].append({'file': name, 'sha256': sha(raw),
                'pins': [line.strip() for line in text.splitlines() if re.match(r'\s*SCRIPT_(REPO|COMMIT|TAG|VERSION|BRANCH)=', line)]})
    run = api('ffmpeg-run', 'repos/BtbN/FFmpeg-Builds/actions/runs/40502414924')
    if run:
        assert run['head_sha'] == 'b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd'
    jobs = api('ffmpeg-jobs', 'repos/BtbN/FFmpeg-Builds/actions/runs/40502414924/jobs?per_page=100')
    for page in (1, 2):
        data = api('ffmpeg-artifacts-' + str(page), f'repos/BtbN/FFmpeg-Builds/actions/runs/40502414924/artifacts?per_page=100&page={page}')
        if data:
            selected = [a for a in data['artifacts'] if a['name'] == 'download-cache']
            if selected:
                report['ffmpeg_source_cache'] = [{k: a[k] for k in ('id', 'name', 'size_in_bytes', 'expired')} for a in selected]
    if args.logs and jobs:
        selected = ['Build base image (ubuntu-latest)', 'Build target-variant image (ubuntu-latest, win64, lgpl-shared 9.0)',
                    'Build ffmpeg (win64, lgpl-shared 9.0)']
        for job in jobs['jobs']:
            if job['name'] in selected:
                log = api('job-' + str(job['id']), f'repos/BtbN/FFmpeg-Builds/actions/jobs/{job["id"]}/logs', False)
                if log:
                    report.setdefault('ffmpeg_log_findings', []).append({'job_id': job['id'], 'name': job['name'],
                        'revision_lines': [line[:1200] for line in log.splitlines()
                                           if re.search(r'HEAD is now at|checkout [0-9a-f]{7,40}|Downloading|download-cache|digest: sha256:', line)][:300]})
    (CACHE / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'python_requirement_entries': len(report['python_requirements']),
                      'upstream_records': len(report['records']), 'log_jobs': len(report.get('ffmpeg_log_findings', [])),
                      'source_cache': report.get('ffmpeg_source_cache'), 'availability_errors': report['availability_errors']}))


if __name__ == '__main__':
    main()
