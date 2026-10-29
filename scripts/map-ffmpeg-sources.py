"""Map actual configure flags to pinned build recipes without executing shell code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT / 'scripts/collect-source-evidence.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar', type=Path, required=True)
    args = parser.parse_args()
    files = helpers['source_trees'](args.sidecar)['ffmpeg-builds']
    recipes = {}
    groups = {}
    for path, data in files.items():
        if not path.startswith('scripts.d/') or not path.endswith('.sh'):
            continue
        name = re.sub(r'^\d+-', '', Path(path).stem)
        text = data.decode('utf-8')
        pins = dict(re.findall(r'^SCRIPT_(REPO|COMMIT|REV)=["\']([^"\']+)["\']', text, re.M))
        revision = pins.get('COMMIT') or pins.get('REV')
        previous = recipes.get(name)
        equivalent = []
        if previous and (previous['repo'] or pins.get('REPO')):
            assert (previous['repo'], previous['revision']) == (pins.get('REPO'), revision), 'Conflicting source recipe id: ' + name
            equivalent = previous.get('equivalent_source_recipes', []) + [previous['recipe']]
        block = re.search(r'ffbuild_depends\(\)\s*\{(.*?)^\}', text, re.M | re.S)
        depends = re.findall(r'^\s*echo ([\w-]+)\s*$', block[1], re.M) if block else []
        configure = re.search(r'ffbuild_configure\(\)\s*\{(.*?)^\}', text, re.M | re.S)
        recipes[name] = {'recipe': path, 'recipe_sha256': hashlib.sha256(data).hexdigest(),
                         'repo': pins.get('REPO'), 'revision': revision, 'depends': depends,
                         'equivalent_source_recipes': equivalent,
                         'features': sorted(set(re.findall(r'--enable-([\w-]+)', configure[1] if configure else '')))}
        if Path(path).parent.as_posix() != 'scripts.d':
            group = re.sub(r'^\d+-', '', Path(path).parent.name)
            groups.setdefault(group, []).append(name)
    features = set(re.findall(r'--enable-([\w-]+)', (ROOT / 'vendor/ffmpeg-buildconf.txt').read_text(encoding='utf-8')))
    direct = {name for name, r in recipes.items() if features.intersection(r['features'])}
    pending = list(direct | {'base'})
    selected = set()
    unresolved = []
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        if name in groups:
            pending.extend(groups[name])
        elif name in recipes:
            pending.extend(recipes[name]['depends'])
        else:
            unresolved.append(name)
    covered = set().union(*(set(recipes[name]['features']) for name in direct))
    records = [dict(name=name, **recipes[name]) for name in sorted(selected) if name in recipes]
    for r in records:
        if r['repo'] and r['revision']:
            repo = r['repo'].removesuffix('.git')
            if repo.startswith('https://github.com/'):
                r['source_url'] = repo + '/tree/' + r['revision']
                r['archive_url'] = 'https://codeload.github.com/' + repo.removeprefix('https://github.com/') + '/tar.gz/' + r['revision']
            else:
                r['source_url'] = repo
    result = {'schema_version': 1, 'build_repo_commit': 'b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd',
              'upstream_build_run': 'https://github.com/BtbN/FFmpeg-Builds/actions/runs/40502414924',
              'scope': 'Static conservative dependency map from actual configure flags and recipe dependency groups; not a complete linked-code SBOM or proof of all submodule/source/notice coverage.',
              'unmatched_configure_features': sorted(features - covered), 'unresolved_dependency_groups': sorted(unresolved),
              'records': records}
    path = ROOT / 'vendor/ffmpeg-source-map.json'
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'selected_recipes': len(records), 'pinned_repositories': sum(bool(r['repo'] and r['revision']) for r in records),
                      'unmatched_features': result['unmatched_configure_features'], 'unresolved_groups': unresolved}))


if __name__ == '__main__':
    main()
