"""Local-only candidate pipeline. Does not commit, push, publish or change DSH profiles."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, help='Verified Node executable')
    parser.add_argument('--npm-cli', required=True, help='Verified npm-cli.js path; no install is run')
    parser.add_argument('--source-sidecar', type=Path, required=True, help='Existing hash-pinned source snapshot sidecar')
    parser.add_argument('--materials-sidecar', type=Path, help='Additional pinned third-party sources/notice payload')
    parser.add_argument('--native-sidecar', type=Path, help='Separate FFmpeg native-source payload')
    parser.add_argument('--require-public-ready', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
    version = package['version']
    assert re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\.\d+)?', version)
    report_dir = ROOT / '.validation' / ('candidate-' + version)
    report_dir.mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    for name in (f'dsh-cyber-amber-{version}.tgz', f'dsh-cyber-amber-{version}-upstream-sources.tar.gz',
                 f'SHA256SUMS-{version}.txt'):
        if (dist / name).exists():
            raise FileExistsError(f'Refusing to replace retained candidate artifact: {dist / name}')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    report = {'version': version, 'steps': [], 'public_operations': False}

    def run(label, argv):
        result = subprocess.run([str(x) for x in argv], cwd=ROOT, env=env,
                                capture_output=True, encoding='utf-8', errors='strict')
        (report_dir / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
        report['steps'].append({'name': label, 'exit_code': result.returncode})
        if result.returncode:
            print(result.stdout + result.stderr)
            raise RuntimeError(f'{label} failed; see {report_dir}')
        print(label + ': passed', flush=True)
        return result.stdout

    try:
        report['node'] = run('node-version', [args.node, '--version']).strip()
        report['npm'] = run('npm-version', [args.node, args.npm_cli, '--version']).strip()
        run('build', [args.node, ROOT / 'node_modules/typescript/bin/tsc', '-p', 'tsconfig.json'])
        run('bundle', [args.node, 'scripts/verify-bundle.mjs'])
        tests = run('tests', [args.node, '--test', '--test-reporter=tap',
                              *sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'test').glob('*.test.mjs'))])
        stats = {key: int(re.search(rf'^# {key} (\d+)$', tests, re.M)[1])
                 for key in ('tests', 'pass', 'fail', 'skipped', 'cancelled')}
        assert stats['tests'] >= 52 and stats['tests'] == stats['pass'] and not any(stats[k] for k in ('fail', 'skipped', 'cancelled')), stats
        report['tests'] = stats
        # The exact prepack integrity check ran above. Suppress duplicate lifecycle
        # stdout here so npm's documented JSON output remains machine-readable.
        packed = json.loads(run('pack', [args.node, args.npm_cli, 'pack', '--ignore-scripts', '--json', '--pack-destination', dist]))
        assert len(packed) == 1
        artifact = dist / packed[0]['filename']
        assert artifact.name == f'dsh-cyber-amber-{version}.tgz'
        report['package'] = json.loads(run('package', [sys.executable, 'scripts/verify-package.py', artifact, ROOT]))
        assert report['package']['matched_installed_runtime_files'] >= 7
        assert report['package']['notice_payload']['verified']
        audit_args = [sys.executable, 'scripts/audit-distribution.py', '--sidecar', args.source_sidecar.resolve(),
                      '--candidate-package', artifact, '--report', report_dir / 'distribution-report.json']
        if args.materials_sidecar:
            audit_args += ['--materials-sidecar', args.materials_sidecar.resolve()]
        if args.native_sidecar:
            audit_args += ['--native-sidecar', args.native_sidecar.resolve()]
        if args.require_public_ready:
            audit_args.append('--require-public-ready')
        audit = json.loads(run('distribution-audit', audit_args))
        report['publication_ready'] = audit['publication_ready']
        report['publication_blockers'] = audit['publication_blockers']
        report['candidate_ready_for_review'] = audit['candidate_ready_for_review']
        assert report['candidate_ready_for_review'], 'Candidate technical checks remain incomplete'
        run('sources', [sys.executable, 'scripts/source-snapshots.py', '--from-sidecar', args.source_sidecar.resolve()])
        sidecar = dist / f'dsh-cyber-amber-{version}-upstream-sources.tar.gz'
        sums = []
        for path in (artifact, sidecar, *([args.materials_sidecar] if args.materials_sidecar else []),
                     *([args.native_sidecar] if args.native_sidecar else [])):
            with path.open('rb') as stream:
                sha = hashlib.file_digest(stream, 'sha256').hexdigest()
            sums.append(f'{sha}  {path.name}')
        checksum = dist / f'SHA256SUMS-{version}.txt'
        checksum.write_text('\n'.join(sums) + '\n', encoding='utf-8', newline='\n')
        report['checksums'] = sums
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        (report_dir / 'preparation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
