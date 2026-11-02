"""F9 held-out check on ViDoSeek TEST-172, in the order of docs/feature_lab/F9_heldout_vidoseek.md.

  prepare  label-free: fit the static anchor and the QARF/QPAF gates on the 970 dev queries, score the 172 test
           pools, write their page scores and the (query, OCR) pairs of the static and QPAF top-K
  seal     label-free: the five pre-registered rows from the Qwen3-4B scores; writes the prediction file, its
           SHA-256 seal and the authorization draft for the Research Lead
  open     with the approved authorization: reads qrels_test_sealed.json once (pinned SHA-256) and scores the
           sealed prediction file; create-once, no rerun
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.lab.compare import paired  # noqa: E402
from qpaf.lab.data import load, make_query  # noqa: E402
from qpaf.lab.heldout import RERANKED, ROWS, label_free_query, predictions_bytes, read_predictions, recall_at  # noqa: E402
from qpaf.lab.model import unit_max, unit_ndcg  # noqa: E402
from qpaf.lab.rerank import TOP_K, fuse_scores, minmax, top_of  # noqa: E402
from qpaf.lab.rerank_stack import page_scores, train_gates  # noqa: E402
from qpaf.lab.train import RECIPE, SEEDS, prepare  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids  # noqa: E402
from qpaf.m43.freeze import git, sha  # noqa: E402
from qpaf.r7.sealed import label_free_records, open_sealed_qrels  # noqa: E402

BUNDLE = ROOT/'results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle'
SEALED_QRELS_SHA256 = '05eaaa810e47d35d4eb06b3d36a05f03b002ec9d3c5ee6bce5fc27d2e336d154'  # bundle hashes.json, R7
INPUTS = ('raw_scores.parquet', 'queries.json', 'qrels_development.json', 'splits/test_ids.txt')
RERANKER = ('Qwen/Qwen3-Reranker-4B', '22e683669bc0f0bd69640a1354a6d0aebcfeede5')
OUT = ROOT/'results/lab/vidoseek/heldout'
PREDICTIONS, SEAL, AUTHORIZATION, RESULT = (OUT/n for n in ('test_predictions.csv.gz', 'prediction_seal.json',
                                                            'authorization.json', 'heldout_result.json'))
CODE = ('scripts/lab_heldout.py', 'src/qpaf/lab')
DEV_ROWS = {'static': ('baseline', 'static'), 'qarf': ('baseline', 'qarf'), 'qpaf': ('baseline', 'qpaf'),
            'f7_static_qwen4b': ('f7_qwen4b', 'f7_qwen4b'), 'f9_qpaf_qwen4b': ('f9_stack_qwen4b', 'f9_qpaf')}
CONTRASTS = (('f9_qpaf_qwen4b', 'qpaf'), ('f9_qpaf_qwen4b', 'static'), ('f9_qpaf_qwen4b', 'qarf'),
             ('f9_qpaf_qwen4b', 'f7_static_qwen4b'))


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def write_new(path, data):
    """Create-once: refuse to overwrite any held-out record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data if isinstance(data, bytes) else (json.dumps(data, ensure_ascii=False, indent=1,
                                                                       sort_keys=True)+'\n').encode('utf-8'))


def test_inputs(data):
    """Label-free TEST-172 LabQuery rows plus the raw inputs the opening needs again."""
    rows = read_score_rows(data/'raw_scores.parquet')
    queries = json.loads((data/'queries.json').read_text(encoding='utf-8'))
    splits = read_split_ids(data/'splits')
    records = label_free_records(rows, queries, splits)
    return [label_free_query(r) for r in records], (rows, queries, splits)


def prepare_command(args):
    dev = load('vidoseek', ROOT, args.data)
    test, _ = test_inputs(args.data)
    variant, seed = load_variant('baseline'), SEEDS[0]
    dev_items, test_items = prepare(dev, variant), prepare(test, variant)
    anchor, mean, std, models = train_gates(dev_items, seed)
    scores = {'static': [minmax(q.raw)@np.asarray(anchor) for q in test],
              **{method: page_scores(model, test_items, mean, std) for method, model in models.items()}}
    texts = {}
    for line in filter(str.strip, args.page_text.read_text(encoding='utf-8').split('\n')):
        page = json.loads(line)
        texts[page['page_id']] = page['text']
    pairs, pages = [], {}
    for row, q in enumerate(test):
        for i in sorted({int(i) for base in ('static', 'qpaf') for i in top_of(scores[base][row])}):
            pages[q.page_ids[i]] = texts[q.page_ids[i]]
            pairs.append([q.query_id, q.page_ids[i]])
    meta = {'dataset': 'vidoseek', 'split': 'test', 'dev_queries': len(dev), 'test_queries': len(test),
            'seed': seed, 'recipe': RECIPE, 'anchor': anchor, 'top_k': TOP_K,
            'inputs_sha256': {name: sha(args.data/name) for name in INPUTS},
            'source_commit': git(ROOT, 'rev-parse', 'HEAD'), 'created_utc': now()}
    args.out.mkdir(parents=True, exist_ok=True)
    offsets = np.cumsum([0]+[len(q.page_ids) for q in test])
    np.savez_compressed(args.out/'test_gate_pages.npz', query_ids=np.array([q.query_id for q in test]),
                        offsets=offsets, meta=np.array(json.dumps(meta)),
                        **{m: np.concatenate(v) for m, v in scores.items()})
    body = {**meta, 'queries': {q.query_id: q.text for q in test}, 'pages': pages, 'pairs': pairs,
            'page_text_sha256': sha(args.page_text)}
    (args.out/'test_pairs.json').write_text(json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True)+'\n',
                                            encoding='utf-8')
    print(f'{len(test)} test queries, anchor {anchor}: {len(pairs)} pairs over {len(pages)} pages in {args.out}')


def seal_command(args):
    test, _ = test_inputs(args.data)
    with np.load(args.cache/'test_gate_pages.npz') as data:
        if data['query_ids'].tolist() != [q.query_id for q in test]:
            raise SystemExit('gate page scores were written for other test queries')
        offsets, meta = data['offsets'], json.loads(str(data['meta']))
        flat = {m: data[m] for m in ('static', 'qarf', 'qpaf')}
    scores = {m: [v[a:b] for a, b in zip(offsets[:-1], offsets[1:])] for m, v in flat.items()}
    pairs_path, scores_path = args.cache/'test_pairs.json', args.cache/'test_scores_qwen3-4b.json'
    pairs, run = (json.loads(p.read_text(encoding='utf-8')) for p in (pairs_path, scores_path))
    if run['pairs_sha256'] != sha(pairs_path) or (run['manifest']['model'], run['manifest']['revision']) != RERANKER:
        raise SystemExit('reranker scores are not Qwen3-Reranker-4B on these pairs')
    rerank = {tuple(pair): score for pair, score in zip(pairs['pairs'], run['scores'])}
    rows = dict(scores)
    for name, (base, lam) in RERANKED.items():
        rows[name] = [fuse_scores(scores[base][r], {i: rerank[(q.query_id, q.page_ids[i])] for i in top_of(scores[base][r])},
                                  lam) for r, q in enumerate(test)]
    data = predictions_bytes(test, rows)
    write_new(PREDICTIONS, data)
    seal = {'file': PREDICTIONS.name, 'sha256': sha(PREDICTIONS), 'size_bytes': len(data), 'rows': list(ROWS),
            'reranked': {n: {'base': b, 'lambda': lam} for n, (b, lam) in RERANKED.items()}, 'gate': meta,
            'gate_pages_sha256': sha(args.cache/'test_gate_pages.npz'), 'pairs_sha256': sha(pairs_path),
            'reranker': run['manifest'], 'sealed_utc': now(), 'test_labels_read': False}
    write_new(SEAL, seal)
    write_new(AUTHORIZATION, {
        'task': 'F9 held-out check on ViDoSeek TEST-172 (post-hoc: TEST-172 was opened once in R7)',
        'protocol': 'docs/feature_lab/F9_heldout_vidoseek.md', 'status': 'PENDING_RESEARCH_LEAD',
        'scope': 'read bundle/qrels_test_sealed.json once with `scripts/lab_heldout.py open`; no rerun, no retry',
        'predictions_sha256': seal['sha256'], 'sealed_qrels_sha256': SEALED_QRELS_SHA256,
        'source_commit': 'PENDING', 'approval': {'approver': 'PENDING', 'approval_text': 'PENDING',
                                                 'approved_utc': 'PENDING', 'recorded_by': 'PENDING'}})
    print(f"sealed {PREDICTIONS.relative_to(ROOT)} sha256 {seal['sha256']}; authorization draft {AUTHORIZATION.relative_to(ROOT)}")


def check_authorization():
    auth = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    approval = auth.get('approval') or {}
    if auth.get('status') != 'APPROVED' or not all(
            isinstance(approval.get(k), str) and approval[k].strip() and 'PENDING' not in approval[k]
            for k in ('approver', 'approval_text', 'approved_utc', 'recorded_by')):
        raise SystemExit('the authorization is not APPROVED with the Research Lead\'s recorded words')
    seal = json.loads(SEAL.read_text(encoding='utf-8'))
    if seal['test_labels_read'] or sha(PREDICTIONS) != seal['sha256'] or auth['predictions_sha256'] != seal['sha256']:
        raise SystemExit('sealed predictions changed or were sealed after labels were read')
    if auth['sealed_qrels_sha256'] != SEALED_QRELS_SHA256:
        raise SystemExit('authorization names another sealed qrels file')
    if subprocess.run(['git', 'diff', '--quiet', auth['source_commit'], 'HEAD', '--', *CODE], cwd=ROOT).returncode:
        raise SystemExit('held-out code changed since the authorized commit')
    if git(ROOT, 'status', '--porcelain', '--untracked-files=no'):
        raise SystemExit('tracked working tree must be clean')
    if RESULT.exists():
        raise SystemExit(f'{RESULT.relative_to(ROOT)} exists: the held-out labels were already opened')
    return auth, seal


def metrics(q, page):
    unit = unit_max(page, q.units, len(q.unit_ids))
    return {'ndcg10': unit_ndcg(unit, q.positive, q.relevant_total), 'recall1': recall_at(q, page, 1),
            'recall3': recall_at(q, page, 3)}


def dev_rows(data):
    """Committed out-of-fold dev rows; one relevant page per dev query, so the rank follows from nDCG@10."""
    dev = load('vidoseek', ROOT, data)
    if any(q.relevant_total != 1 for q in dev):
        raise SystemExit('a dev query has more than one relevant page')
    out = {}
    for name, (file, key) in DEV_ROWS.items():
        ndcg = json.loads((ROOT/f'results/lab/vidoseek/vidoseek-{file}.json').read_text(encoding='utf-8'))['per_query'][key]
        out[name] = {q.query_id: {'ndcg10': ndcg[q.query_id], 'recall1': float(ndcg[q.query_id] > 1-1e-9),
                                  'recall3': float(ndcg[q.query_id] > 0.5-1e-9)} for q in dev}
    return out


def open_command(args):
    auth, seal = check_authorization()
    label_free, (rows, queries, splits) = test_inputs(args.data)
    sealed = read_predictions(PREDICTIONS.read_bytes(), label_free)
    qrels = open_sealed_qrels(args.data/'qrels_test_sealed.json', SEALED_QRELS_SHA256, splits['test'])  # the one read
    records = build_records(rows, queries, qrels, splits, ('test',))['test']
    labeled = [make_query(r.query_id, r.text, list(r.page_ids), r.raw_scores, {p: p for p in r.page_ids},
                          {p for p, v in qrels[r.query_id].items() if v >= 1}, r.relevant_total) for r in records]
    if [(q.query_id, q.page_ids) for q in labeled] != [(q.query_id, q.page_ids) for q in label_free] or \
            any(not np.array_equal(a.raw, b.raw) for a, b in zip(labeled, label_free)):
        raise SystemExit('labeled test candidates differ from the label-free ones')
    per_query = {name: {q.query_id: metrics(q, sealed[name][r]) for r, q in enumerate(labeled)} for name in ROWS}
    names = ('ndcg10', 'recall1', 'recall3')
    mean = {name: {m: float(np.mean([v[m] for v in per_query[name].values()])) for m in names} for name in ROWS}
    comparisons = {f'{a} - {b}': {m: paired({i: v[m] for i, v in per_query[a].items()},
                                            {i: v[m] for i, v in per_query[b].items()}) for m in ('ndcg10', 'recall1')}
                   for a, b in CONTRASTS}
    dev = dev_rows(args.data)
    full = {name: {m: float(np.mean([v[m] for v in (*dev[name].values(), *per_query[name].values())]))
                   for m in names} for name in ROWS}
    result = {'schema': 'qpaf-lab-f9-heldout-v1', 'dataset': 'vidoseek', 'split': 'test', 'post_hoc': True,
              'queries': len(labeled), 'queries_without_positive': sum(not q.positive.any() for q in labeled),
              'mean': mean, 'comparisons': comparisons,
              'all_1142': {'queries': len(labeled)+len(next(iter(dev.values()))), 'mean': full,
                           'note': 'dev rows are the committed out-of-fold CV rows; test rows are the sealed ones'},
              'prediction_seal': seal, 'authorization_sha256': sha(AUTHORIZATION),
              'access': {'sealed_qrels_reads': 1, 'sealed_qrels_sha256': SEALED_QRELS_SHA256, 'opened_utc': now()},
              'source_commit': git(ROOT, 'rev-parse', 'HEAD'), 'per_query': per_query}
    write_new(RESULT, result)
    for name in ROWS:
        print(f"{name:18s} nDCG@10 {mean[name]['ndcg10']:.4f}  R@1 {mean[name]['recall1']*100:.2f}  "
              f"R@3 {mean[name]['recall3']*100:.2f}  | 1,142: R@1 {full[name]['recall1']*100:.2f}  "
              f"R@3 {full[name]['recall3']*100:.2f}")
    for name, by_metric in comparisons.items():
        c = by_metric['ndcg10']
        print(f"  {name} nDCG@10: {c['delta']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] "
              f"{c['wins']}/{c['ties']}/{c['losses']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--page-text', required=True, type=Path, help='qpaf-lab-share assets/vidoseek_page_text.jsonl')
    p.add_argument('--out', required=True, type=Path, help='cache folder outside the repo (pairs hold OCR)')
    s = sub.add_parser('seal')
    s.add_argument('--cache', required=True, type=Path, help='the prepare folder, with test_scores_qwen3-4b.json')
    sub.add_parser('open')
    for command in sub.choices.values():
        command.add_argument('--data', type=Path, default=BUNDLE, help='the M2.8 ViDoSeek bundle')
    args = parser.parse_args(argv)
    {'prepare': prepare_command, 'seal': seal_command, 'open': open_command}[args.command](args)


if __name__ == '__main__':
    main()
