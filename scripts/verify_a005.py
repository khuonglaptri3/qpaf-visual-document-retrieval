"""Read-only replay of the facts amendment A005 cites, for its independent review.

Checks the approved amendment bytes, the §1 identity hashes at the recorded
commit, every number A005 quotes from earlier evidence, the epoch-0 anchor
arithmetic and the ViMDoc seal state. It reads no qrels, trains nothing and
authorizes nothing. Exit code 1 means at least one check failed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AMENDMENTS = 'evidence/M1_FINAL/02_protocol/amendments/'
A005 = AMENDMENTS + 'QPAF-M1.5-A005.md'
APPROVAL = AMENDMENTS + 'QPAF-M1.5-A005.approval-001.md'
IDENTITY_COMMIT = '1cecddb63a03b629bf89af4859f85eb23a2f59c5'
IDENTITY_ROW = re.compile(r'^\| `([^`]+)`.*\| `([0-9a-f]{64})` \|$')
# (claim in A005, file, JSON path, quoted value, decimals quoted)
CITED = (
    ('TEST-172 QPAF - static mean', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.mean_delta', -0.006748, 6),
    ('TEST-172 QPAF - static CI low', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.ci95.0', -0.019028, 6),
    ('TEST-172 QPAF - static CI high', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.ci95.1', 0.005269, 6),
    ('TEST-172 W/T/L wins', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.wtl.wins', 7, 0),
    ('TEST-172 W/T/L ties', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.wtl.ties', 152, 0),
    ('TEST-172 W/T/L losses', 'evidence/revisions/m5.7-001/summary.json',
     'contrasts.QPAF_minus_train_fitted_static.metrics.ndcg_at_10.wtl.losses', 13, 0),
    ('G3 decision', 'evidence/revisions/m5.9-001/decision.json', 'decision', 'LIMITED-CLAIM', None),
    ('M4.4/M4.5 validation QPAF - static mean', 'evidence/revisions/m4.5-001/verification.json',
     None, -0.005134, 6),
    ('Validation static nDCG@10', 'evidence/revisions/m4.4-001/post_run_verification.json',
     'MTH.validation_ndcg_at_10.train_fitted_static', 0.8714, 4),
    ('Validation per-page W66 oracle', 'evidence/revisions/m4.4-001/post_run_verification.json',
     'ORC.oracle_ndcg_at_10.oracle_qpaf_w66', 0.9401, 4),
    ('A001 train Spearman(loss, nDCG)', 'evidence/revisions/m4.6-001/loss_alignment_probe.json',
     'gate_v1.spearman', 0.537, 3),
    ('A001 minimum is BM25-only', 'evidence/revisions/m4.6-001/loss_alignment_probe.json',
     'gate_v1.min_loss_weights', [1.0, 0.0, 0.0], None),
    ('ViDoSeek static weights', 'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/train_fit.json',
     'weights', [0.0, 0.1, 0.9], None),
    ('ViMDoc train IDs', 'evidence/revisions/m4.1-001/manifest.json',
     'split.files.train_ids.txt.count', 1600, 0),
    ('ViMDoc validation IDs', 'evidence/revisions/m4.1-001/manifest.json',
     'split.files.validation_ids.txt.count', 400, 0),
    ('ViMDoc confirmation IDs', 'evidence/revisions/m4.1-001/manifest.json',
     'split.files.confirmation_ids.txt.count', 8904, 0),
    ('ViMDoc confirmation labels still sealed', 'evidence/revisions/m4.1-001/manifest.json',
     'access.confirmation_queries_and_labels_opened', False, None),
    ('ViMDoc document unit', 'evidence/revisions/m4.1-001/manifest.json', 'evaluation.unit', 'document', None),
    ('ViMDoc document score', 'evidence/revisions/m4.1-001/manifest.json',
     'evaluation.document_score', 'max_fused_page_score', None),
)
M56_SUMMARY = 'results/m5.6/RUN-QPAF-M5_6-ABL-001-20261027T164635Z-A01/summary.json'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_at(rel, commit):
    """File bytes at the commit when its object is present, else the working tree."""
    if commit is not None:
        found = subprocess.run(['git', 'cat-file', '-e', f'{commit}:{rel}'], cwd=ROOT, capture_output=True)
        if found.returncode == 0:
            return subprocess.run(['git', 'show', f'{commit}:{rel}'], cwd=ROOT, capture_output=True,
                                  check=True).stdout, commit
    return (ROOT / rel).read_bytes(), 'working-tree'


def json_path(record, path):
    """Dotted path; keys such as train_ids.txt contain a dot, so the longest existing key wins."""
    parts, node, i = path.split('.'), record, 0
    while i < len(parts):
        for j in range(len(parts), i, -1):
            key = '.'.join(parts[i:j])
            if isinstance(node, dict) and key in node:
                node, i = node[key], j
                break
        else:
            node, i = node[int(parts[i])], i + 1
    return node


def m45_static_delta(record):
    """The M4.5 verification nests the static contrast; take its ndcg mean_delta."""
    hits = []

    def walk(node):
        if isinstance(node, dict):
            if 'train_fitted_static' in node and isinstance(node['train_fitted_static'], dict) \
                    and 'mean_delta' in node['train_fitted_static']:
                hits.append(node['train_fitted_static']['mean_delta'])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(record)
    return hits[0] if hits else None


def checks(identity_commit):
    results = []

    def add(name, ok, detail):
        results.append({'check': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})

    a005 = (ROOT / A005).read_bytes()
    approval = (ROOT / APPROVAL).read_text(encoding='utf-8')
    approved_sha = re.search(r'SHA-256\s*`([0-9a-f]{64})`', approval)
    add('approved A005 bytes unchanged', approved_sha is not None and approved_sha.group(1) == sha_bytes(a005),
        sha_bytes(a005))
    rows = [IDENTITY_ROW.match(line) for line in a005.decode('utf-8').splitlines()]
    rows = [m.groups() for m in rows if m]
    add('identity table has rows', len(rows) >= 10, f'{len(rows)} rows')
    for rel, expected in rows:
        data, source = read_at(rel, identity_commit)
        add(f'identity {rel}', sha_bytes(data) == expected, source)
    for name, rel, path, quoted, decimals in CITED:
        record = json.loads((ROOT / rel).read_text(encoding='utf-8'))
        value = m45_static_delta(record) if path is None else json_path(record, path)
        if decimals is None:
            ok = value == quoted
        else:
            ok = isinstance(value, (int, float)) and round(value, decimals) == quoted
        add(f'cited: {name}', ok, f'{rel}: {value!r}')
    summary = json.loads((ROOT / M56_SUMMARY).read_text(encoding='utf-8'))
    deltas = [v['mean_delta'] for v in summary['ablation_vs_control_ndcg_at_10'].values()]
    add('cited: M5.6 feature-group ablations within +/-0.002', len(deltas) == 4 and max(map(abs, deltas)) <= 0.002,
        f'{[round(d, 6) for d in deltas]}')
    anchor = [(w + 1e-3) / (1 + 3e-3) for w in (0.0, 0.1, 0.9)]
    add('epoch-0 anchor weights', [round(w, 6) for w in anchor] == [0.000997, 0.100698, 0.898305],
        f'{anchor}')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-commit', default=IDENTITY_COMMIT,
                        help='commit whose file bytes the §1 table pins (falls back to the working tree)')
    args = parser.parse_args()
    results = checks(args.identity_commit)
    failed = [r for r in results if r['status'] == 'FAIL']
    print(json.dumps({'amendment': 'QPAF-M1.5-A005', 'checks': results, 'PASS': len(results) - len(failed),
                      'FAIL': len(failed), 'reads_labels': False, 'read_only': True}, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
