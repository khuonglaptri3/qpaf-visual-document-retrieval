"""Read-only post-run check of the M5.6 run; the pinned runner `verify` with one documented deviation.

`runner.verify` refuses this run at its first step because the in-run copy `authorization.json` is not
byte-identical to the pinned authorization: the committed authorization has CRLF line endings (written on
Windows, stored `-text`), and the runner copied it through `read_text`/`write_text(newline='\\n')`, which
dropped every `\\r`. This check accepts the copy only if it equals the pinned committed bytes with CRLF
replaced by LF, and reports that as deviation D1. Every other step of `verify` runs unchanged by calling the
pinned runner functions, whose source hashes are re-checked first. Writes only with --write (create-once).

    .venv/Scripts/python.exe evidence/revisions/m5.6-001/post_run_check.py [--write]
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m44.common import read, sha  # noqa: E402
from qpaf.m56 import conditioning, runner  # noqa: E402

RUN = 'results/m5.6/RUN-QPAF-M5_6-ABL-001-20261027T164635Z-A01'
AUTHORIZATION_SHA256 = 'a89efaf416dc306dfc0bd09dd5bb1201d81c382dd0429dad6efd42fa99e1be98'
MANIFEST_SHA256 = 'be69197b8fb1d724d86f0bcdde729c365d69638b63e8088adff38defa2630706'
APPROVAL_COMMIT = 'c1da4f37f83ef9dcf1157c75c33af75ae0fb9170'
checks = []


def check(name, passed, detail=''):
    checks.append({'check': name, 'status': 'PASS' if passed else 'FAIL', 'detail': detail})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    output = ROOT/RUN
    manifest = read(output/'manifest.json')
    check('external manifest pin', sha(output/'manifest.json') == MANIFEST_SHA256, MANIFEST_SHA256)
    marker = read(output/'_SUCCESS.json')
    check('success marker binds manifest, no failure marker',
          marker['manifest_sha256'] == MANIFEST_SHA256 and not (output/'_FAILED.json').exists())
    bad = [e['path'] for e in manifest['files'] if not ((output/e['path']).is_file() and
           (output/e['path']).stat().st_size == e['size_bytes'] and sha(output/e['path']) == e['sha256'])]
    check('every manifest artifact matches size and SHA-256', not bad, f'{len(manifest["files"])} files; bad={bad}')
    present = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    expected = {e['path'] for e in manifest['files']} | {'manifest.json', '_ATTEMPTED.json', '_SUCCESS.json'}
    check('run file set equals manifest plus markers', present == expected)
    attempt = read(output/'_ATTEMPTED.json')
    check('attempt and manifest carry the external authorization pin',
          attempt['authorization_sha256'] == manifest['authorization_sha256'] == AUTHORIZATION_SHA256)
    check('attempt ran at the approval commit', attempt['git_head'] == APPROVAL_COMMIT, attempt['git_head'])
    committed = subprocess.check_output(['git', 'show', f'{APPROVAL_COMMIT}:{runner.AUTHORIZATION_PATH}'], cwd=ROOT)
    check('committed authorization equals the pin', __import__('hashlib').sha256(committed).hexdigest()
          == AUTHORIZATION_SHA256)
    copy = (output/'authorization.json').read_bytes()
    check('D1: in-run copy equals the pinned authorization with CRLF -> LF', copy == committed.replace(b'\r\n', b'\n')
          and copy != committed, f'copy sha256 {sha(output/"authorization.json")}; pinned bytes contain CRLF')
    try:
        runner.validate_bindings(ROOT, read(output/'authorization.json'))
        check('pinned source and authority hashes unchanged', True)
    except ValueError as exc:
        check('pinned source and authority hashes unchanged', False, str(exc))
    _, records = runner.load_records(ROOT, ('validation',))
    per_query = {rid: [{k: v if k == 'query_id' else float(v) for k, v in row.items()}
                       for row in runner._read_csv(output/rid/'validation_per_query.csv')] for rid in runner.SCOPE[:5]}
    check('R6-01..04 paired statistics replay exactly',
          read(output/'ablation_comparisons.json') == json.loads(json.dumps(runner.compare_ablations(per_query))))
    replay, _ = conditioning.compare(ROOT, records['validation'], sha)
    check('R6-05 conditioning statistics replay exactly',
          read(output/'conditioning.json') == json.loads(json.dumps(replay)))
    parity = read(output/'pilot_parity.json')
    check('R6-00 reproduces the M3.4 pilot', parity['status'] == 'PASS' and
          parity['prediction_max_abs_difference'] == 0.0, json.dumps(parity['selected_epoch']))
    summaries = {rid: read(output/rid/'summary.json') for rid in runner.SCOPE[:5]}
    check('omitted-feature weights unchanged in every diagnostic',
          all(s['omitted_weights_unchanged'] for s in summaries.values()))
    reload = runner.fresh_reload(ROOT, output)
    check('fresh-process reload of all best/last checkpoints', reload['status'] == 'PASS',
          json.dumps({k: v['prediction_max_abs_difference'] for k, v in reload['checks'].items()}))
    summary = read(output/'summary.json')
    check('no test labels, GPU, Modal or primary change', not any(
        summary[k] for k in ('test_labels_opened', 'gpu_executed', 'modal_called', 'primary_method_changed',
                             'confirmatory_claim')))
    counts = {s: sum(c['status'] == s for c in checks) for s in ('PASS', 'FAIL')}
    result = {'task_id': 'M5.6', 'run': RUN, 'manifest_sha256': MANIFEST_SHA256, 'checks': checks, **counts,
              'deviations': [{'id': 'D1', 'what': 'in-run authorization copy is LF-normalised (runner copies with '
                              'read_text/write_text); runner.verify refuses on this byte check',
                              'impact': 'none on training, checkpoints, predictions or statistics; '
                              'all other verify steps pass here'}],
              'read_only': not args.write}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.write:
        with (HERE/'post_run_verification.json').open('x', encoding='utf8', newline='\n') as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return 0 if counts['FAIL'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
