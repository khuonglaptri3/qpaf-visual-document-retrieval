"""Finalize this task bundle's layout/link/history checks and byte manifest."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[5]
BUNDLE = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)+'\n',
                    encoding='utf-8', newline='\n')


def main():
    require({p.name for p in BUNDLE.iterdir()} == {'README.md', 'evidence', 'superpowers'}, 'task root layout')
    require({p.name for p in (BUNDLE/'superpowers').iterdir()} == {'spec.md', 'plan.md'}, 'planning layout')
    events = [json.loads(line) for line in (BUNDLE/'evidence/governance_events.jsonl').read_text(encoding='utf-8').splitlines()]
    auth = json.loads((BUNDLE/'evidence/gpu-attempt-003/gpu-authorization.json').read_text(encoding='utf-8'))
    require(events[0]['approval_text'] == auth['approval']['text'], 'owner approval text encoding differs')
    require(events[0]['delegation_text'] == auth['approval']['delegation'], 'owner delegation text encoding differs')
    manifest_path = BUNDLE/'evidence/bundle-manifest.json'
    if not manifest_path.exists():
        write(manifest_path, {'status': 'BUILDING'})
    validation_path = BUNDLE/'evidence/bundle-validation.json'
    if not validation_path.exists():
        write(validation_path, {'status': 'BUILDING'})
    checked = []
    documents = [*BUNDLE.rglob('*.md'), ROOT/'docs/README.md', ROOT/'docs/06_handover/README.md',
                 ROOT/'docs/06_handover/m5.5-cpu-results-and-gpu-handoff.md',
                 ROOT/'Bao_cao_tien_do/M5_5_Khuong.md']
    for doc in documents:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', doc.read_text(encoding='utf-8-sig')):
            target = target.strip().split(' "')[0].strip('<>')
            if re.match(r'^[a-zA-Z]+:', target) or target.startswith('#'):
                continue
            relative = unquote(target.split('#')[0])
            require((doc.parent/relative).resolve().exists(), f'broken link: {doc}: {target}')
            checked.append({'document': doc.relative_to(ROOT).as_posix(), 'target': target})
    old = json.loads((BUNDLE/'evidence/local-restoration.json').read_text(encoding='utf-8'))
    base = '1bdb491ec3b74f578c31dda5ba796d1d375ac586'
    history = {}
    for name, digest in old['historical_files_sha256'].items():
        require(sha(ROOT/name) == digest, 'historical file changed: '+name)
        content = subprocess.check_output(['git', 'show', base+':'+name], cwd=ROOT)
        require(hashlib.sha256(content).hexdigest() == digest, 'historical checkout bytes differ: '+name)
        history[name] = digest
    require(not (ROOT/'docs/superpowers/plans/2026-10-27-m55-cpu-diagnostics.md').exists(), 'duplicate old plan')
    require(not (ROOT/'docs/superpowers/specs/2026-10-27-m55-cpu-diagnostics-design.md').exists(), 'duplicate old spec')
    diff = subprocess.run(['git', 'diff', '--check', base], cwd=ROOT, capture_output=True, text=True)
    require(diff.returncode == 0, diff.stdout+diff.stderr)
    receipt = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(),
               'task_root_layout': ['README.md', 'evidence/', 'superpowers/'],
               'planning_files': ['spec.md', 'plan.md'], 'checked_local_links': checked,
               'historical_files_sha256': history, 'historical_base_commit': base,
               'git_diff_check': 'PASS', 'independent_human_acceptance_inferred': False}
    write(BUNDLE/'evidence/bundle-validation.json', receipt)
    files = {p.relative_to(BUNDLE).as_posix(): {'sha256': sha(p), 'size_bytes': p.stat().st_size}
             for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p != manifest_path
             and '__pycache__' not in p.parts}
    write(manifest_path, {'schema_version': 1, 'task_id': 'M5.5', 'files': files})
    print(json.dumps({'status': 'PASS', 'task_files': len(files), 'local_links': len(checked),
                      'historical_files_unchanged': len(history),
                      'manifest_sha256': sha(manifest_path)}, indent=2))


if __name__ == '__main__':
    main()
