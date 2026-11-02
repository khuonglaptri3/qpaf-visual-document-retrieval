"""F5–F9 reranker screening (docs/feature_lab/F5, F6_F8, F9): pairs, constant-λ screens and the learned-λ gate.

  pairs   top-K pages of every dev query under its fold's static anchor, with query and OCR text, for
          scripts/modal_lab_rerank.py. Labels pick the anchor only through the other folds, as in the lab.
          With --base the top-K come from the trained gate instead (F9); --skip leaves out pairs already scored.
  screen  out-of-fold nDCG@10 for λ fitted on the train folds and for λ = 1, against static and the
          committed baseline QARF/QPAF rows. Several --scores files are averaged after per-query min-max (F7).
  gate    F6: λ learned per query (QARF-λ) and per page (QPAF-λ), anchored at the train-fold constant λ.
  base    F9: out-of-fold page scores of the baseline QARF/QPAF gate, checked against the committed rows.
  stack   F9: the screen rule on the top-K of the trained gate instead of the static fusion.
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
from qpaf.lab.rerank import LAMBDAS, TOP_K, fold_anchors, fuse, fuse_scores, minmax, top_of, top_pages, unit_score  # noqa: E402
from qpaf.lab.rerank_gate import PAGE_FEATURES, QUERY_FEATURES, columns_for, page_lambdas, query_tensors, train_gate  # noqa: E402
from qpaf.lab.rerank_stack import gate_page_scores  # noqa: E402
from qpaf.lab.train import SEEDS  # noqa: E402
from qpaf.m43.freeze import git, sha  # noqa: E402

DATA_FILES = {'vimdoc': ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json'),
              'vidoseek': ('raw_scores.parquet', 'queries.json', 'qrels_development.json')}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)+'\n', encoding='utf-8')


def save_base(path, queries, scores, meta):
    offsets = np.cumsum([0]+[len(q.page_ids) for q in queries])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, query_ids=np.array([q.query_id for q in queries]), offsets=offsets,
                        meta=np.array(json.dumps(meta)), **{m: np.concatenate(rows) for m, rows in scores.items()})


def load_base(path, queries):
    """Gate page scores per method, aligned with `queries`, and the metadata written by `base`."""
    with np.load(path) as data:
        offsets = data['offsets']
        if data['query_ids'].tolist() != [q.query_id for q in queries] or \
                np.diff(offsets).tolist() != [len(q.page_ids) for q in queries]:
            raise SystemExit(f'{path} was written for other queries or pages')
        scores = {m: [data[m][a:b] for a, b in zip(offsets[:-1], offsets[1:])] for m in ('qarf', 'qpaf')}
        return scores, json.loads(str(data['meta']))


def build_pairs(args):
    queries = load(args.dataset, ROOT, args.data)
    anchors = fold_anchors(queries)
    texts = {}
    # Split on '\n' only: OCR strings hold raw form feeds and U+2028 that splitlines() would cut.
    for line in filter(str.strip, args.page_text.read_text(encoding='utf-8').split('\n')):
        page = json.loads(line)
        texts[page['page_id']] = page['text']
    if args.base:  # F9: union of the QARF and QPAF top-K
        gate = load_base(args.base, queries)[0]
        chosen = [sorted({int(i) for m in gate for i in top_of(gate[m][row])}) for row in range(len(queries))]
    else:
        chosen = [top_pages(q, anchors[fold_of(q.query_id)]) for q in queries]
    skip = set()
    if args.skip:
        done = json.loads(args.skip.read_text(encoding='utf-8'))
        if done['fold_anchors'] != anchors:
            raise SystemExit(f'{args.skip} was built with other fold anchors')
        skip = {tuple(pair) for pair in done['pairs']}
    pairs, pages = [], {}
    for q, top in zip(queries, chosen):
        for i in top:
            page_id = q.page_ids[i]
            if (q.query_id, page_id) in skip:
                continue
            if page_id not in texts:
                raise SystemExit(f'{args.dataset}: no OCR for {page_id}')
            pages[page_id] = texts[page_id]
            pairs.append([q.query_id, page_id])
    write_json(args.out, {'dataset': args.dataset, 'top_k': TOP_K, 'fold_anchors': anchors,
                          'queries': {q.query_id: q.text for q in queries}, 'pages': pages, 'pairs': pairs,
                          'inputs_sha256': {name: sha(args.data/name) for name in DATA_FILES[args.dataset]},
                          'page_text_sha256': sha(args.page_text), 'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
                          'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                          **({'base_sha256': sha(args.base)} if args.base else {}),
                          **({'skip_sha256': sha(args.skip), 'skipped': len(skip)} if args.skip else {})})
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


def static_fused(queries, anchors, fold):
    """Each query's static page scores under its fold's anchor."""
    return [minmax(q.raw)@np.asarray(anchors[fold[row]]) for row, q in enumerate(queries)]


def lambda_table(queries, fused, rerank):
    """[queries, len(LAMBDAS)] unit nDCG@10 of the constant-λ interpolation on each query's out-of-fold fused scores."""
    table = np.zeros((len(queries), len(LAMBDAS)))
    for row, q in enumerate(queries):
        by_index = {i: rerank[q.query_id][q.page_ids[i]] for i in top_of(fused[row])}
        table[row] = [unit_score(q, fuse_scores(fused[row], by_index, lam)) for lam in LAMBDAS]
    return table


def best_lambda(table, rows):
    total = table[rows].sum(axis=0)
    return max(range(len(LAMBDAS)), key=lambda i: (total[i], -i))  # ties keep the smaller λ


def fit_folds(table, fold, folds):
    """Out-of-fold row of the λ fitted on the other folds, and the λ chosen for each fold."""
    fitted, chosen = np.zeros(len(table)), []
    for k in range(folds):
        best = best_lambda(table, fold != k)
        chosen.append(LAMBDAS[best])
        fitted[fold == k] = table[fold == k, best]
    return fitted, chosen


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
    table = lambda_table(queries, static_fused(queries, anchors, fold), rerank)
    fitted, chosen = fit_folds(table, fold, len(anchors))
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
    table = lambda_table(queries, static_fused(queries, anchors, fold), rerank)
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


def base(args):
    queries = load(args.dataset, ROOT, args.data)
    reference = json.loads((ROOT/'results/lab'/args.dataset/f'{args.dataset}-baseline.json').read_text(encoding='utf-8'))
    inputs = {name: sha(args.data/name) for name in DATA_FILES[args.dataset]}
    seed = SEEDS[0]
    if reference['seeds'] != [seed] or reference['inputs_sha256'] != inputs:
        raise SystemExit('the committed baseline used another seed or other inputs')
    scores, anchors = gate_page_scores(queries, seed)
    if anchors != fold_anchors(queries):
        raise SystemExit('gate anchors differ from the screen anchors')
    for method, rows in scores.items():
        gap = max(abs(unit_score(q, s)-reference['per_query'][method][q.query_id]) for q, s in zip(queries, rows))
        if gap > 1e-12:
            raise SystemExit(f'{method} page scores miss the committed baseline row by up to {gap:.2e}')
        print(f'{method}: reproduces the committed baseline row (max gap {gap:.1e})')
    save_base(args.out, queries, scores, {'dataset': args.dataset, 'seed': seed, 'fold_anchors': anchors,
                                          'inputs_sha256': inputs, **provenance(),
                                          'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')})


def stack(args):
    queries = load(args.dataset, ROOT, args.data)
    anchors = fold_anchors(queries)
    gate_scores, meta = load_base(args.base, queries)
    rerank, manifests = {}, []
    for pairs_path, scores_path in zip(args.pairs, args.scores, strict=True):
        pairs, run = (json.loads(path.read_text(encoding='utf-8')) for path in (pairs_path, scores_path))
        if pairs['fold_anchors'] != anchors or run['pairs_sha256'] != sha(pairs_path):
            raise SystemExit(f'{pairs_path}: anchors or scored pairs differ')
        for (query_id, page_id), score in zip(pairs['pairs'], run['scores']):
            rerank.setdefault(query_id, {})[page_id] = score
        manifests.append(run['manifest'])
    if len({(m['model'], m['revision']) for m in manifests}) != 1:
        raise SystemExit('every --scores file must come from the same reranker')
    fold = np.array([fold_of(q.query_id) for q in queries])
    ids = [q.query_id for q in queries]
    static = {i: unit_score(q, s) for i, q, s in zip(ids, queries, static_fused(queries, anchors, fold))}
    rows = {'static': static, **baseline_rows(args.dataset, ids, static)}
    chosen, by_lambda = {}, {}
    for method in ('qarf', 'qpaf'):
        table = lambda_table(queries, gate_scores[method], rerank)
        if any(abs(table[r, 0]-rows[f'baseline_{method}'][i]) > 1e-12 for r, i in enumerate(ids)):
            raise SystemExit(f'λ = 0 does not reproduce the baseline {method} row')
        fitted, chosen[method] = fit_folds(table, fold, len(anchors))
        rows[f'f9_{method}'] = dict(zip(ids, fitted.tolist()))
        rows[f'f9_{method}_only'] = dict(zip(ids, table[:, -1].tolist()))
        by_lambda[method] = table.mean(axis=0).tolist()
    mains = ('f9_qarf', 'f9_qpaf')
    comparisons = {f'{a} - {b}': paired(rows[a], rows[b]) for a in mains
                   for b in ('static', 'baseline_qarf', 'baseline_qpaf')}
    comparisons['f9_qpaf - f9_qarf'] = paired(rows['f9_qpaf'], rows['f9_qarf'])
    for path in args.against:
        other = json.loads(path.read_text(encoding='utf-8'))
        for a in mains:
            comparisons[f"{a} - {other['variant']}"] = paired(rows[a], other['per_query'][other['variant']])
    result = {'schema': 'qpaf-lab-f9-stack-v1', 'variant': args.name, 'dataset': args.dataset, 'top_k': TOP_K,
              'lambdas': list(LAMBDAS), 'fold_lambda': chosen, 'fold_anchors': anchors, 'mean_by_lambda': by_lambda,
              'mean': {n: float(np.mean(list(row.values()))) for n, row in rows.items()},
              'comparisons': comparisons, 'reranker': manifests, 'pairs_sha256': [sha(p) for p in args.pairs],
              'base': meta, 'base_sha256': sha(args.base), **provenance(),
              'per_query': {n: rows[n] for n in ('static', *mains, *(f'{m}_only' for m in mains))}}
    write_json(args.output, result)
    print(json.dumps({k: result[k] for k in ('dataset', 'fold_lambda', 'mean')}, indent=1))
    print_comparisons(comparisons)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pairs')
    p.add_argument('--dataset', required=True, choices=DATASETS)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--page-text', required=True, type=Path, help='qpaf-lab-share assets/<dataset>_page_text.jsonl')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--base', type=Path, help='F9: output of `base`; take the QARF and QPAF top-K instead of the static top-K')
    p.add_argument('--skip', type=Path, help='leave out the pairs already in this pairs file')
    b = sub.add_parser('base')
    b.add_argument('--dataset', required=True, choices=DATASETS)
    b.add_argument('--data', required=True, type=Path)
    b.add_argument('--out', required=True, type=Path, help='.npz of gate page scores; keep it outside the repo')
    t = sub.add_parser('stack')
    t.add_argument('--dataset', required=True, choices=DATASETS)
    t.add_argument('--data', required=True, type=Path)
    t.add_argument('--base', required=True, type=Path)
    t.add_argument('--pairs', required=True, type=Path, action='append', help='repeat; one --scores per --pairs, in order')
    t.add_argument('--scores', required=True, type=Path, action='append')
    t.add_argument('--against', type=Path, action='append', default=[], help='a screen result to compare with')
    t.add_argument('--name', default='f9_stack')
    t.add_argument('--output', type=Path)
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
    if args.command in ('pairs', 'base'):
        (build_pairs if args.command == 'pairs' else base)(args)
        return
    args.output = args.output or ROOT/'results/lab'/args.dataset/f'{args.dataset}-{args.name}.json'
    {'screen': screen, 'gate': gate, 'stack': stack}[args.command](args)


if __name__ == '__main__':
    main()
