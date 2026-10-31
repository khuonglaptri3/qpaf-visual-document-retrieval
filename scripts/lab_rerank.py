"""F5 reranker screening (docs/feature_lab/F5): build the label-free pairs, then score the out-of-fold fusion.

  pairs   top-K pages of every dev query under its fold's static anchor, with query and OCR text, for
          scripts/modal_lab_rerank.py. Labels pick the anchor only through the other folds, as in the lab.
  screen  out-of-fold nDCG@10 for λ fitted on the train folds and for λ = 1, against static and the
          committed baseline QARF/QPAF rows.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.lab.compare import paired  # noqa: E402
from qpaf.lab.data import DATASETS, fold_of, load  # noqa: E402
from qpaf.lab.rerank import LAMBDAS, TOP_K, fold_anchors, fuse, minmax, top_pages, unit_score  # noqa: E402
from qpaf.m43.freeze import git, sha  # noqa: E402

DATA_FILES = {'vimdoc': ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json'),
              'vidoseek': ('raw_scores.parquet', 'queries.json', 'qrels_development.json')}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)+'\n', encoding='utf-8')


def build_pairs(args):
    queries = load(args.dataset, ROOT, args.data)
    anchors = fold_anchors(queries)
    texts = {}
    # Split on '\n' only: OCR strings hold raw form feeds and U+2028 that splitlines() would cut.
    for line in filter(str.strip, args.page_text.read_text(encoding='utf-8').split('\n')):
        page = json.loads(line)
        texts[page['page_id']] = page['text']
    pairs, pages = [], {}
    for q in queries:
        for i in top_pages(q, anchors[fold_of(q.query_id)]):
            page_id = q.page_ids[i]
            if page_id not in texts:
                raise SystemExit(f'{args.dataset}: no OCR for {page_id}')
            pages[page_id] = texts[page_id]
            pairs.append([q.query_id, page_id])
    write_json(args.out, {'dataset': args.dataset, 'top_k': TOP_K, 'fold_anchors': anchors,
                          'queries': {q.query_id: q.text for q in queries}, 'pages': pages, 'pairs': pairs,
                          'inputs_sha256': {name: sha(args.data/name) for name in DATA_FILES[args.dataset]},
                          'page_text_sha256': sha(args.page_text), 'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
                          'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    empty = sum(not pages[p].strip() for _, p in pairs)
    print(f'{args.dataset}: {len(pairs)} pairs, {len(pages)} pages ({empty} pairs with empty OCR), anchors {anchors}')


def screen(args):
    queries = load(args.dataset, ROOT, args.data)
    anchors = fold_anchors(queries)
    pairs, scored = json.loads(args.pairs.read_text(encoding='utf-8')), json.loads(args.scores.read_text(encoding='utf-8'))
    if pairs['fold_anchors'] != anchors or scored['pairs_sha256'] != sha(args.pairs):
        raise SystemExit('anchors or pairs file differ from the scored run')
    rerank = {}
    for (query_id, page_id), score in zip(pairs['pairs'], scored['scores']):
        rerank.setdefault(query_id, {})[page_id] = score
    fold = np.array([fold_of(q.query_id) for q in queries])
    table = np.zeros((len(queries), len(LAMBDAS)))
    for row, q in enumerate(queries):
        anchor = anchors[fold[row]]
        by_index = {i: rerank[q.query_id][q.page_ids[i]] for i in top_pages(q, anchor)}
        table[row] = [unit_score(q, fuse(q, anchor, by_index, lam)) for lam in LAMBDAS]
    fitted, chosen = np.zeros(len(queries)), []
    for k in range(len(anchors)):
        total = table[fold != k].sum(axis=0)
        best = max(range(len(LAMBDAS)), key=lambda i: (total[i], -i))  # ties keep the smaller λ
        chosen.append(LAMBDAS[best])
        fitted[fold == k] = table[fold == k, best]
    ids = [q.query_id for q in queries]
    static = {i: float(v) for i, v in zip(ids, table[:, 0])}
    rows = {'static': static, 'f5_rerank': dict(zip(ids, fitted.tolist())),
            'f5_rerank_only': dict(zip(ids, table[:, -1].tolist()))}
    baseline = json.loads((ROOT/'results/lab'/args.dataset/f'{args.dataset}-baseline.json').read_text(encoding='utf-8'))
    if any(abs(baseline['per_query']['static'][i]-static[i]) > 1e-12 for i in ids):
        raise SystemExit('static row differs from the committed lab baseline')
    for method in ('qarf', 'qpaf'):
        rows[f'baseline_{method}'] = baseline['per_query'][method]
    comparisons = {f'{a} - {b}': paired(rows[a], rows[b]) for a in ('f5_rerank', 'f5_rerank_only')
                   for b in ('static', 'baseline_qarf', 'baseline_qpaf')}
    # Own schema: compare_lab.py reads only qpaf-lab-v1 gate rows, so this file never enters its tables.
    result = {'schema': 'qpaf-lab-f5-screen-v1', 'dataset': args.dataset, 'top_k': TOP_K, 'lambdas': list(LAMBDAS), 'fold_lambda': chosen,
              'fold_anchors': anchors, 'mean_by_lambda': table.mean(axis=0).tolist(),
              'mean': {name: float(np.mean(list(row.values()))) for name, row in rows.items()},
              'comparisons': comparisons, 'reranker': scored['manifest'], 'pairs_sha256': scored['pairs_sha256'],
              'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
              'tracked_changes': bool(git(ROOT, 'status', '--porcelain', '--untracked-files=no')),
              'per_query': {name: rows[name] for name in ('static', 'f5_rerank', 'f5_rerank_only')}}
    write_json(args.output, result)
    print(json.dumps({k: result[k] for k in ('dataset', 'fold_lambda', 'mean')}, indent=1))
    for name, c in comparisons.items():
        print(f"  {name}: {c['delta']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] {c['wins']}/{c['ties']}/{c['losses']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pairs')
    p.add_argument('--dataset', required=True, choices=DATASETS)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--page-text', required=True, type=Path, help='qpaf-lab-share assets/<dataset>_page_text.jsonl')
    p.add_argument('--out', required=True, type=Path)
    s = sub.add_parser('screen')
    s.add_argument('--dataset', required=True, choices=DATASETS)
    s.add_argument('--data', required=True, type=Path)
    s.add_argument('--pairs', required=True, type=Path)
    s.add_argument('--scores', required=True, type=Path, help='output of scripts/modal_lab_rerank.py')
    s.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'pairs':
        build_pairs(args)
    else:
        args.output = args.output or ROOT/'results/lab'/args.dataset/f'{args.dataset}-f5_rerank.json'
        screen(args)


if __name__ == '__main__':
    main()
