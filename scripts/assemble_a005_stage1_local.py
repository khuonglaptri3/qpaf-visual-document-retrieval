"""A005 Stage 1 assemble, run locally on the downloaded score matrices (Modal workspace hit its spend limit).

Same computation as `assemble` in a005_stage1_modal.py, processed in query chunks
to fit local memory. Every input file is checked against its Stage 1 _SUCCESS
hash first. Dev qrels enter only the coverage report, after all unions are fixed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from qpaf.a005.stage1 import assemble_channel, candidate_rows, coverage  # noqa: E402

SHARDS = 16
PAGES_SHA256 = '9dc277153f9137c8c668d70a3f66dfd208e129e5907eede7b47dbac1f2250b84'
CHUNK = 512


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 24), b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='dir with bm25.npy, dense_XX.npy, visual_XX.npy')
    parser.add_argument('--markers', type=Path, required=True, help='dir with the Stage 1 _SUCCESS copies')
    parser.add_argument('--pages', type=Path, required=True)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--dev-qrels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new directory')
    args = parser.parse_args(argv)
    marker = lambda name: json.loads((args.markers/f'{name}.json').read_text(encoding='utf-8'))  # noqa: E731
    prepare = marker('prepare')
    checks = {args.pages: PAGES_SHA256, args.queries: prepare['queries_sha256'],
              args.dev_qrels: prepare['dev_qrels_sha256'], args.data/'bm25.npy': marker('bm25')['bm25_sha256']}
    for shard in range(SHARDS):
        gpu = marker(f'gpu_{shard:02d}')
        checks[args.data/f'dense_{shard:02d}.npy'] = gpu['dense_sha256']
        checks[args.data/f'visual_{shard:02d}.npy'] = gpu['visual_sha256']
    for path, expected in checks.items():
        if sha256(path) != expected:
            raise ValueError(f'hash mismatch: {path.name}')
    args.output.mkdir(parents=False, exist_ok=False)
    pages = [json.loads(line) for line in args.pages.read_text(encoding='utf-8').splitlines()]
    page_ids = [p['page_id'] for p in pages]
    documents = {p['page_id']: p['document_id'] for p in pages}
    query_ids = [json.loads(line)['query_id'] for line in args.queries.read_text(encoding='utf-8').splitlines()]
    total = len(page_ids)
    bm25 = np.load(args.data/'bm25.npy', mmap_mode='r')
    shards = {name: [np.load(args.data/f'{name}_{s:02d}.npy', mmap_mode='r') for s in range(SHARDS)]
              for name in ('dense', 'visual')}
    if bm25.shape != (len(query_ids), total):
        raise ValueError(f'bm25 shape {bm25.shape}')
    schema = pa.schema([('query_id', pa.string()), ('page_id', pa.string()), ('document_id', pa.string())] +
                       [(c, pa.float64()) for c in ('bm25', 'dense', 'visual', 'bm25_norm', 'dense_norm', 'visual_norm')])
    unions, sizes = {}, []
    with pq.ParquetWriter(args.output/'candidate_scores.parquet', schema) as writer:
        for start in range(0, len(query_ids), CHUNK):
            rows = slice(start, start+CHUNK)
            matrices = {'bm25': np.asarray(bm25[rows], dtype=np.float64)}
            for name in ('dense', 'visual'):
                matrices[name] = assemble_channel(total, SHARDS, [np.asarray(block[rows]) for block in shards[name]])
            columns = {name: [] for name in schema.names}
            for query_id, union, raw, normalized in candidate_rows(query_ids[rows], page_ids, documents, matrices):
                unions[query_id] = union.tolist()
                sizes.append(int(union.size))
                columns['query_id'] += [query_id]*union.size
                columns['page_id'] += [page_ids[i] for i in union]
                columns['document_id'] += [documents[page_ids[i]] for i in union]
                for j, channel in enumerate(('bm25', 'dense', 'visual')):
                    columns[channel] += raw[:, j].tolist()
                    columns[channel+'_norm'] += normalized[:, j].tolist()
            writer.write_table(pa.table(columns, schema=schema))
            print(f'queries {min(start+CHUNK, len(query_ids))}/{len(query_ids)}', flush=True)
    dev = json.loads(args.dev_qrels.read_text(encoding='utf-8'))
    report = {'queries': len(query_ids), 'rows': sum(sizes), 'union_size_min': min(sizes),
              'union_size_max': max(sizes), 'union_size_mean': sum(sizes)/len(sizes),
              'coverage': {role: coverage(unions, page_ids, documents, dev[role]) for role in ('train', 'validation')},
              'candidate_scores_sha256': sha256(args.output/'candidate_scores.parquet'),
              'inputs_sha256': {path.name: expected for path, expected in checks.items()},
              'labels_used': 'dev qrels for the coverage report only, after every union was fixed',
              'run_location': 'local CPU (Modal workspace tranthanhzt123321 hit its spend limit)'}
    with (args.output/'_SUCCESS.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'inputs_sha256'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
