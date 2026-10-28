"""Install an actual candidate in a disposable DSH_HOME and run deterministic tools.

Use --dsh-node/--dsh-cli for the desktop's Electron-as-Node CLI. Never invokes an
LLM, the GUI, the desktop profile, or a remote publisher. Media transfer is local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsh-node', required=True)
    parser.add_argument('--dsh-cli', required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True, help='Existing MP4 with at least 10 seconds of video')
    parser.add_argument('--deadline', type=int, default=180)
    args = parser.parse_args()
    package, source = args.package.resolve(strict=True), args.source.resolve(strict=True)
    assert package.is_file() and source.is_file()
    with source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    owned = ROOT / '.validation' / ('host-rc-' + uuid.uuid4().hex)
    owned.mkdir(parents=True)
    home = owned / 'home'
    output = owned / 'output'
    output.mkdir()
    cli = [args.dsh_node, '--expose-internals', args.dsh_cli]
    env = dict(os.environ, DSH_HOME=str(home), ELECTRON_RUN_AS_NODE='1', PYTHONIOENCODING='utf-8')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    process = None
    passed = False
    try:
        def run(label, argv):
            result = subprocess.run(cli + argv, cwd=ROOT, env=env, capture_output=True,
                                    encoding='utf-8', timeout=120, **flags)
            (owned / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
            if result.returncode:
                raise RuntimeError(f'{label} failed: {result.stderr[-3000:]}')
            return result.stdout

        run('initialize', ['--profile', 'amber-rc', '--from-default-profile', 'sdk-minimal', '--dump-config'])
        profile = home / 'profiles' / 'amber-rc'
        # Inspect the generated project before the official CLI performs install.
        profile_package = json.loads((profile / 'package.json').read_text(encoding='utf-8'))
        assert isinstance(profile_package, dict)
        run('install', ['plugin', '--profile', 'amber-rc', 'add', 'file:' + package.as_posix(),
                        '--ignore-scripts', '--config.auto-install-peers=false', '--store-dir', str(owned / 'store')])
        installed = profile / 'node_modules' / 'dsh-cyber-amber'
        installed_package = json.loads((installed / 'package.json').read_text(encoding='utf-8'))
        assert installed_package['version'] == version
        # Check every packaged lib/manifest byte against what the host will load.
        verified = subprocess.run([os.sys.executable, str(ROOT / 'scripts/verify-package.py'),
                                   str(package), str(installed)], capture_output=True, encoding='utf-8', check=True)
        (owned / 'installed-package.json').write_text(verified.stdout, encoding='utf-8', newline='\n')
        patch = [
            {'id': 'cyber-amber', 'name': 'dsh-cyber-amber', 'config': {}},
            {'insert': [{'id': 'amber-rc-probe', 'name': (ROOT / 'test/host-rc-probe.mjs').as_posix(),
                         'config': {'source': source.as_posix(), 'outputDir': output.as_posix(),
                                    'reportDir': owned.as_posix(), 'packageRoot': installed.as_posix()}}]},
        ]
        patch_path = owned / 'probe.patch.yml'
        patch_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        with (owned / 'host.stdout.log').open('w', encoding='utf-8') as stdout, (owned / 'host.stderr.log').open('w', encoding='utf-8') as stderr:
            process = subprocess.Popen(cli + ['--profile', 'amber-rc', '--patch', str(patch_path)],
                                       cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, **flags)
            report_path = owned / 'host-rc-report.json'
            deadline = time.monotonic() + args.deadline
            while not report_path.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f'Host did not produce its report; inspect {owned}')
                time.sleep(0.2)
            report = json.loads(report_path.read_text(encoding='utf-8'))
            report['installed_package'] = json.loads(verified.stdout)
            with source.open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == source_hash, 'Original video changed'
            report['unchanged_source_sha256'] = source_hash
            target = ROOT / '.validation' / ('candidate-' + version)
            target.mkdir(parents=True, exist_ok=True)
            (target / 'host-rc-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
            assert report['status'] == 'passed', report.get('error')
            passed = True
            print(json.dumps({'status': report['status'], 'version': report['version'],
                              'calls': len(report['calls']), 'real_config_validation': report['real_config_validation'],
                              'external_network': False, 'report': str(target / 'host-rc-report.json')}))
    finally:
        if process and process.poll() is None:
            process.stdin.close()  # SDK EOF requests normal service disposal first.
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if process and process.poll() is None:
            if os.name == 'nt':
                stopped = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, **flags)
                if stopped.returncode and process.poll() is None:
                    raise RuntimeError(f'Could not stop owned validation host PID {process.pid}; retained {owned}')
            else:
                process.terminate()
            process.wait(timeout=15)
        if passed:
            assert owned.resolve().parent == (ROOT / '.validation').resolve() and not owned.is_symlink()
            shutil.rmtree(owned)


if __name__ == '__main__':
    main()
