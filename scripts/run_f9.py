"""F9, the final proposed method (QPAF gate + Qwen3-Reranker-4B on its top-20), as a package (src/qpaf/f9).

  prepare  label-free: fit the QPAF gate on the dev queries, score the held-out/new pool, write the first-stage
           scores (f9_first_stage.npz) and the (query, OCR) pairs of its top-20 for scripts/modal_lab_rerank.py
  rank     label-free: final F9 scores from the Qwen3-4B scores; writes each query's top-10 units as gzip JSON lines
  verify   label-free regression against the sealed held-out run of scripts/lab_heldout.py: the same inputs must
           give the same final scores (--refit also retrains the gate on the dev queries)

--dataset vidoseek (default) uses TEST-172 of the M2.8 bundle; --dataset vimdoc uses the M4.1 confirmation split of
the A005 Stage 1 cache given with --data. The sealed labels are never read.
"""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from lab_heldout import CONFIG, test_inputs  # noqa: E402
from qpaf.f9.method import LAMBDA, RERANKER, ROW, F9Model, fit, first_stage, pairs, rank  # noqa: E402
from qpaf.lab.data import load  # noqa: E402
from qpaf.lab.heldout import RANKED, gzip_bytes, read_predictions, top_units  # noqa: E402
from qpaf.m43.freeze import git, sha  # noqa: E402

SCORES = 'f9_scores_qwen3-4b.json'
LAB_FILES = ('test_gate_pages.npz', 'test_pairs.json', 'test_scores_qwen3-4b.json')


def split_rows(flat, offsets):
    return [flat[a:b] for a, b in zip(offsets[:-1], offsets[1:])]


def read_first_stage(path, queries):
    """First-stage QPAF scores per query and the metadata; the file must have been written for these queries."""
    with np.load(path) as data:
        offsets, meta = data['offsets'], json.loads(str(data['meta']))
        if data['query_ids'].tolist() != [q.query_id for q in queries] or \
                np.diff(offsets).tolist() != [len(q.page_ids) for q in queries]:
            raise SystemExit(f'{path} was written for other queries or pages')
        return split_rows(data['qpaf'], offsets), meta


def read_rerank(pairs_path, scores_path):
    """{(query_id, page_id): reranker score} of a scored run; it must be Qwen3-Reranker-4B on exactly these pairs."""
    listed, run = (json.loads(p.read_text(encoding='utf-8')) for p in (pairs_path, scores_path))
    if run['pairs_sha256'] != sha(pairs_path) or (run['manifest']['model'], run['manifest']['revision']) != RERANKER:
        raise SystemExit('reranker scores are not Qwen3-Reranker-4B on these pairs')
    if len(run['scores']) != len(listed['pairs']):
        raise SystemExit('reranker scores and pairs differ in length')
    return {tuple(pair): score for pair, score in zip(listed['pairs'], run['scores'])}, run['manifest']


def ranking_model(lam, meta):
    """F9Model for ranking from stored first-stage scores: no gate is needed."""
    return F9Model(meta['anchor'], None, None, None, lam, meta['seed'], meta['top_k'], meta['recipe'])


def prepare_command(args):
    dev = load(args.dataset, ROOT, args.data)
    test, _ = test_inputs(args.dataset, args.data)
    model = fit(dev, LAMBDA[args.dataset])
    first = first_stage(model, test)
    texts = {}
    for line in filter(str.strip, args.page_text.read_text(encoding='utf-8').split('\n')):
        page = json.loads(line)
        texts[page['page_id']] = page['text']
    chosen = pairs(test, first, model.top_k)
    if any(page not in texts for _, page in chosen):
        raise SystemExit(f'{args.dataset}: no OCR for a top-{model.top_k} page')
    meta = {'dataset': args.dataset, 'dev_queries': len(dev), 'test_queries': len(test), 'seed': model.seed,
            'recipe': model.recipe, 'anchor': model.anchor, 'top_k': model.top_k, 'lambda': model.lam,
            'inputs_sha256': {name: sha(args.data/name) for name in CONFIG[args.dataset]['inputs']},
            'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
            'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    args.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out/'f9_first_stage.npz', query_ids=np.array([q.query_id for q in test]),
                        offsets=np.cumsum([0]+[len(q.page_ids) for q in test]), meta=np.array(json.dumps(meta)),
                        qpaf=np.concatenate(first))
    body = {**meta, 'queries': {q.query_id: q.text for q in test}, 'pages': {p: texts[p] for _, p in chosen},
            'pairs': chosen, 'page_text_sha256': sha(args.page_text)}
    (args.out/'f9_pairs.json').write_text(json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True)+'\n',
                                          encoding='utf-8')
    print(f'{len(test)} queries, anchor {model.anchor}: {len(chosen)} pairs over {len(body["pages"])} pages '
          f'in {args.out}')


def rank_command(args):
    with np.load(args.cache/'f9_first_stage.npz') as data:
        meta = json.loads(str(data['meta']))
    data_dir = args.data or CONFIG[meta['dataset']]['data']
    if data_dir is None:
        raise SystemExit('--data is required for ViMDoc')
    test, _ = test_inputs(meta['dataset'], data_dir)
    first, _ = read_first_stage(args.cache/'f9_first_stage.npz', test)
    rerank, manifest = read_rerank(args.cache/'f9_pairs.json', args.scores or args.cache/SCORES)
    lam = meta['lambda'] if args.lam is None else args.lam
    scores = rank(ranking_model(lam, meta), test, first, rerank)
    lines = [json.dumps({'method': 'f9', 'dataset': meta['dataset'], 'top': RANKED, 'lambda': lam,
                         'top_k': meta['top_k'], 'reranker': [manifest['model'], manifest['revision']]}),
             *(json.dumps({'query_id': q.query_id, 'top': top_units(q, s)}) for q, s in zip(test, scores))]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(gzip_bytes(('\n'.join(lines)+'\n').encode('utf-8')))
    print(f'{len(test)} queries, lambda {lam}: top-{RANKED} units in {args.out}')


def compare_vidoseek(final, test):
    path = ROOT/'results/lab/vidoseek/heldout'/CONFIG['vidoseek']['predictions']
    sealed = read_predictions(path.read_bytes(), test)[ROW]
    pages = sum(len(s) for s in sealed)
    wrong = sum(int((a != b).sum()) for a, b in zip(final, sealed))
    gap = max(float(np.abs(a-b).max()) for a, b in zip(final, sealed))
    return wrong == 0, f'{pages} page scores, {wrong} differ, max abs diff {gap:.3g}'


def compare_vimdoc(final, test):
    path = ROOT/'results/lab/vimdoc/heldout'/CONFIG['vimdoc']['predictions']
    header, *lines = gzip.decompress(path.read_bytes()).decode('utf-8').rstrip('\n').split('\n')
    sealed = [json.loads(line) for line in lines]
    if json.loads(header)['top'] != RANKED or [e['query_id'] for e in sealed] != [q.query_id for q in test]:
        raise SystemExit('sealed ranking file differs in header or queries')
    wrong = sum(top_units(q, s) != e[ROW] for q, s, e in zip(test, final, sealed))
    return wrong == 0, f'{len(test)} queries, {wrong} with other top-{RANKED} units or scores'


def verify_command(args):
    test, _ = test_inputs(args.dataset, args.data)
    cache = args.lab_cache
    first, meta = read_first_stage(cache/LAB_FILES[0], test)
    rerank, _ = read_rerank(cache/LAB_FILES[1], cache/LAB_FILES[2])
    final = rank(ranking_model(LAMBDA[args.dataset], meta), test, first, rerank)
    ok, detail = (compare_vidoseek if args.dataset == 'vidoseek' else compare_vimdoc)(final, test)
    results = [('final scores vs sealed run', ok, detail)]
    if args.refit:
        model = fit(load(args.dataset, ROOT, args.data), LAMBDA[args.dataset], log=lambda *_: None)
        refit = first_stage(model, test)
        gap = max(float(np.abs(a-b).max()) for a, b in zip(refit, first))
        results.append(('refit first stage', gap == 0, f'max abs diff {gap:.3g}'))
        results.append(('refit anchor', model.anchor == meta['anchor'], f"{model.anchor} vs {meta['anchor']}"))
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    if not all(passed for _, passed, _ in results):
        raise SystemExit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--dataset', default='vidoseek', choices=sorted(LAMBDA))
    p.add_argument('--page-text', required=True, type=Path, help='qpaf-lab-share assets/<dataset>_page_text.jsonl')
    p.add_argument('--out', required=True, type=Path, help='cache folder outside the repo (pairs hold OCR)')
    r = sub.add_parser('rank')
    r.add_argument('--cache', required=True, type=Path, help='the prepare folder, with the scored pairs')
    r.add_argument('--scores', type=Path, help=f'output of scripts/modal_lab_rerank.py (default <cache>/{SCORES})')
    r.add_argument('--lam', type=float, help='override lambda (default: the pre-registered value of the dataset)')
    r.add_argument('--out', required=True, type=Path, help='.jsonl.gz with the top-10 units of every query')
    v = sub.add_parser('verify')
    v.add_argument('--dataset', default='vidoseek', choices=sorted(LAMBDA))
    v.add_argument('--lab-cache', required=True, type=Path, help='the lab_heldout prepare folder')
    v.add_argument('--refit', action='store_true', help='also retrain the gate on the dev queries (CPU, minutes)')
    for command in (p, r, v):
        command.add_argument('--data', type=Path,
                             help='ViDoSeek: the M2.8 bundle (default); ViMDoc: the A005 Stage 1 cache')
    args = parser.parse_args(argv)
    if args.command != 'rank':
        args.data = args.data or CONFIG[args.dataset]['data']
        if args.data is None:
            parser.error('--data is required for ViMDoc')
    {'prepare': prepare_command, 'rank': rank_command, 'verify': verify_command}[args.command](args)


if __name__ == '__main__':
    main()
