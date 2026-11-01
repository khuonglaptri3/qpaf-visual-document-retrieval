"""F5–F7 reranker screening (docs/feature_lab/F5, F6, F7): pairs, the constant-λ screen and the learned-λ gate.

  pairs   top-K pages of every dev query under its fold's static anchor, with query and OCR text, for
          scripts/modal_lab_rerank.py. Labels pick the anchor only through the other folds, as in the lab.
  screen  out-of-fold nDCG@10 for λ fitted on the train folds and for λ = 1, against static and the
          committed baseline QARF/QPAF rows. Several --scores files are averaged after per-query min-max (F7).
  gate    F6: λ learned per query (QARF-λ) and per page (QPAF-λ), anchored at the train-fold constant λ.
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
from qpaf.lab.rerank_gate import PAGE_FEATURES, QUERY_FEATURES, columns_for, page_lambdas, query_tensors, train_gate  # noqa: E402
from qpaf.lab.train import SEEDS  # noqa: E402
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


def load_inputs(args):
    """Queries, fold anchors and the reranker score per (query, page); several runs average per-query min-max."""
    queries = load(args.dataset, ROOT, args.data)
    anchors = fold_anchors(queries)
    pairs = json.loads(args.pairs.read_text(encoding='utf-8'))
    runs = [json.loads(path.read_text(encoding='utf-8')) for path in args.scores]
    if pairs['fold_anchors'] != anchors or any(run['pairs_sha256'] != sha(args.pairs) for run in runs):
        raise SystemExit('anchors or pairs file differ from the scored run')
    per_run = []
    for run in runs:
        scores = {}
        for (query_id, page_id), score in zip(pairs['pairs'], run['scores']):
            scores.setdefault(query_id, {})[page_id] = score
        per_run.append(scores)
    rerank = per_run[0]
    if len(per_run) > 1:  # models on different logit scales weigh equally after min-max over the query's top-K
        rerank = {}
        for query_id, pages in per_run[0].items():
            ids = list(pages)
            mean = np.mean([minmax(np.array([run[query_id][p] for p in ids])) for run in per_run], axis=0)
            rerank[query_id] = dict(zip(ids, mean.tolist()))
    manifests = [run['manifest'] for run in runs]
    return queries, anchors, pairs, rerank, manifests[0] if len(manifests) == 1 else manifests


def lambda_table(queries, anchors, rerank, fold):
    """[queries, len(LAMBDAS)] out-of-fold unit nDCG@10 of the constant-λ interpolation."""
    table = np.zeros((len(queries), len(LAMBDAS)))
    for row, q in enumerate(queries):
        anchor = anchors[fold[row]]
        by_index = {i: rerank[q.query_id][q.page_ids[i]] for i in top_pages(q, anchor)}
        table[row] = [unit_score(q, fuse(q, anchor, by_index, lam)) for lam in LAMBDAS]
    return table


def best_lambda(table, rows):
    total = table[rows].sum(axis=0)
    return max(range(len(LAMBDAS)), key=lambda i: (total[i], -i))  # ties keep the smaller λ


def baseline_rows(dataset, ids, static):
    baseline = json.loads((ROOT/'results/lab'/dataset/f'{dataset}-baseline.json').read_text(encoding='utf-8'))
    if any(abs(baseline['per_query']['static'][i]-static[i]) > 1e-12 for i in ids):
        raise SystemExit('static row differs from the committed lab baseline')
    return {f'baseline_{m}': baseline['per_query'][m] for m in ('qarf', 'qpaf')}


def provenance():
    return {'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
            'tracked_changes': bool(git(ROOT, 'status', '--porcelain', '--untracked-files=no'))}


def print_comparisons(comparisons):
    for name, c in comparisons.items():
        print(f"  {name}: {c['delta']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] {c['wins']}/{c['ties']}/{c['losses']}")


def screen(args):
    queries, anchors, _, rerank, manifest = load_inputs(args)
    fold = np.array([fold_of(q.query_id) for q in queries])
    table = lambda_table(queries, anchors, rerank, fold)
    fitted, chosen = np.zeros(len(queries)), []
    for k in range(len(anchors)):
        best = best_lambda(table, fold != k)
        chosen.append(LAMBDAS[best])
        fitted[fold == k] = table[fold == k, best]
    ids = [q.query_id for q in queries]
    static = {i: float(v) for i, v in zip(ids, table[:, 0])}
    name = args.name
    rows = {'static': static, name: dict(zip(ids, fitted.tolist())), f'{name}_only': dict(zip(ids, table[:, -1].tolist())),
            **baseline_rows(args.dataset, ids, static)}
    comparisons = {f'{a} - {b}': paired(rows[a], rows[b]) for a in (name, f'{name}_only')
                   for b in ('static', 'baseline_qarf', 'baseline_qpaf')}
    for path in args.against:
        other = json.loads(path.read_text(encoding='utf-8'))
        label = other['variant'] if 'variant' in other else path.stem.split('-', 1)[1]
        comparisons[f'{name} - {label}'] = paired(rows[name], other['per_query'][label])
    # Own schema: compare_lab.py reads only qpaf-lab-v1 gate rows, so this file never enters its tables.
    result = {'schema': 'qpaf-lab-f5-screen-v1', 'variant': name, 'dataset': args.dataset, 'top_k': TOP_K,
              'lambdas': list(LAMBDAS), 'fold_lambda': chosen, 'fold_anchors': anchors,
              'mean_by_lambda': table.mean(axis=0).tolist(),
              'mean': {n: float(np.mean(list(row.values()))) for n, row in rows.items()},
              'comparisons': comparisons, 'reranker': manifest, 'pairs_sha256': sha(args.pairs), **provenance(),
              'per_query': {n: rows[n] for n in ('static', name, f'{name}_only')}}
    write_json(args.output, result)
    print(json.dumps({k: result[k] for k in ('dataset', 'fold_lambda', 'mean')}, indent=1))
    print_comparisons(comparisons)


def gate(args):
    queries, anchors, pairs, rerank, manifest = load_inputs(args)
    fold = np.array([fold_of(q.query_id) for q in queries])
    table = lambda_table(queries, anchors, rerank, fold)
    items = [query_tensors(q, anchors[fold[i]], rerank, pairs['pages']) for i, q in enumerate(queries)]
    seed = SEEDS[0]
    const, learned = np.zeros(len(queries)), {g: np.zeros(len(queries)) for g in ('query', 'page')}
    folds, lam_stats = [], {g: [] for g in learned}
    names = list(QUERY_FEATURES)+list(PAGE_FEATURES)
    for k in range(len(anchors)):
        train, held = np.nonzero(fold != k)[0], np.nonzero(fold == k)[0]
        best = best_lambda(table, fold != k)
        const[held] = table[held, best]
        record = {'lambda0': LAMBDAS[best]}
        for granularity in learned:
            model, columns, mean, std = train_gate([items[i] for i in train], LAMBDAS[best], granularity, seed)
            lams = []
            for i in held:
                q, anchor = queries[i], anchors[k]
                lam = page_lambdas(model, columns, mean, std, items[i])
                lams.append(lam)
                by_index = {j: rerank[q.query_id][q.page_ids[j]] for j in top_pages(q, anchor)}
                learned[granularity][i] = unit_score(q, fuse(q, anchor, by_index, lam))
            lams = np.concatenate(lams)
            lam_stats[granularity].append([float(lams.mean()), float(lams.std())])
            weights = model.delta.weight.detach().numpy()[0]/std  # per raw feature unit
            record[granularity] = {'weights_per_std': dict(zip([names[c] for c in columns],
                                                               model.delta.weight.detach().numpy()[0].tolist())),
                                   'bias': float(model.delta.bias.item()), 'tau': float(np.exp(model.log_tau.item())),
                                   'weights_per_raw_unit': dict(zip([names[c] for c in columns], weights.tolist()))}
        folds.append(record)
        print(f'fold {k}: lambda0 {LAMBDAS[best]}, QARF mean/std {lam_stats["query"][-1]}, QPAF {lam_stats["page"][-1]}')
    ids = [q.query_id for q in queries]
    static = {i: float(v) for i, v in zip(ids, table[:, 0])}
    rows = {'static': static, 'constant': dict(zip(ids, const.tolist())),
            'f6_qarf': dict(zip(ids, learned['query'].tolist())), 'f6_qpaf': dict(zip(ids, learned['page'].tolist())),
            **baseline_rows(args.dataset, ids, static)}
    comparisons = {f'{a} - {b}': paired(rows[a], rows[b]) for a in ('f6_qarf', 'f6_qpaf')
                   for b in ('constant', 'static', 'baseline_qarf', 'baseline_qpaf')}
    comparisons['f6_qpaf - f6_qarf'] = paired(rows['f6_qpaf'], rows['f6_qarf'])
    result = {'schema': 'qpaf-lab-f6-gate-v1', 'variant': args.name, 'dataset': args.dataset, 'top_k': TOP_K,
              'seeds': [seed], 'query_features': list(QUERY_FEATURES), 'page_features': list(PAGE_FEATURES),
              'qarf_columns': columns_for('query'), 'folds': folds, 'lambda_mean_std': lam_stats,
              'mean': {n: float(np.mean(list(row.values()))) for n, row in rows.items()},
              'comparisons': comparisons, 'reranker': manifest, 'pairs_sha256': sha(args.pairs), **provenance(),
              'per_query': {n: rows[n] for n in ('static', 'constant', 'f6_qarf', 'f6_qpaf')}}
    write_json(args.output, result)
    print(json.dumps({k: result[k] for k in ('dataset', 'mean')}, indent=1))
    print_comparisons(comparisons)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pairs')
    p.add_argument('--dataset', required=True, choices=DATASETS)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--page-text', required=True, type=Path, help='qpaf-lab-share assets/<dataset>_page_text.jsonl')
    p.add_argument('--out', required=True, type=Path)
    for command, default in (('screen', 'f5_rerank'), ('gate', 'f6_gate')):
        s = sub.add_parser(command)
        s.add_argument('--dataset', required=True, choices=DATASETS)
        s.add_argument('--data', required=True, type=Path)
        s.add_argument('--pairs', required=True, type=Path)
        s.add_argument('--scores', required=True, type=Path, action='append',
                       help='output of scripts/modal_lab_rerank.py; repeat to average several rerankers')
        s.add_argument('--name', default=default, help='variant name; the output is results/lab/<dataset>/<dataset>-<name>.json')
        s.add_argument('--output', type=Path)
        if command == 'screen':
            s.add_argument('--against', type=Path, action='append', default=[],
                           help='another screen result; adds a paired comparison with its variant row')
    args = parser.parse_args(argv)
    if args.command == 'pairs':
        build_pairs(args)
        return
    args.output = args.output or ROOT/'results/lab'/args.dataset/f'{args.dataset}-{args.name}.json'
    (screen if args.command == 'screen' else gate)(args)


if __name__ == '__main__':
    main()
