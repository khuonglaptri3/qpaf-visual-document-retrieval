"""Build the label-free inputs of the A005 BM25 re-run: dense/visual top-200 from the verified shards.

Every shard, OCR file, page table and query table is checked against its Stage 1
marker before use. The output directory holds exactly a005_stage1_bm25_modal.INPUTS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np  # noqa: E402

from qpaf.a005.bm25_rerun import channel_tops  # noqa: E402
from qpaf.a005.stage1 import assemble_channel  # noqa: E402

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
    parser.add_argument('--data', type=Path, required=True, help='dir with dense_XX.npy, visual_XX.npy')
    parser.add_argument('--ocr', type=Path, required=True, help='dir with ocr_XX.jsonl')
    parser.add_argument('--markers', type=Path, required=True)
    parser.add_argument('--pages', type=Path, required=True)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new directory')
    args = parser.parse_args(argv)
    marker = lambda name: json.loads((args.markers/f'{name}.json').read_text(encoding='utf-8'))  # noqa: E731
    checks = {args.pages: PAGES_SHA256, args.queries: marker('prepare')['queries_sha256']}
    for shard in range(SHARDS):
        gpu = marker(f'gpu_{shard:02d}')
        checks[args.data/f'dense_{shard:02d}.npy'] = gpu['dense_sha256']
        checks[args.data/f'visual_{shard:02d}.npy'] = gpu['visual_sha256']
        checks[args.ocr/f'ocr_{shard:02d}.jsonl'] = marker(f'ocr_{shard:02d}')['ocr_jsonl_sha256']
    for path, expected in checks.items():
        if sha256(path) != expected:
            raise ValueError(f'hash mismatch: {path.name}')
    args.output.mkdir(parents=False, exist_ok=False)
    total = len(args.pages.read_text(encoding='utf-8').splitlines())
    queries = len(args.queries.read_text(encoding='utf-8').splitlines())
    shards = {name: [np.load(args.data/f'{name}_{s:02d}.npy', mmap_mode='r') for s in range(SHARDS)]
              for name in ('dense', 'visual')}
    tops = {name: [] for name in shards}
    for start in range(0, queries, CHUNK):
        rows = slice(start, start+CHUNK)
        for name in shards:
            matrix = assemble_channel(total, SHARDS, [np.asarray(block[rows]) for block in shards[name]])
            tops[name].append(channel_tops(matrix))
        print(f'queries {min(start+CHUNK, queries)}/{queries}', flush=True)
    np.savez(args.output/'tops.npz', dense_top=np.concatenate(tops['dense']),
             visual_top=np.concatenate(tops['visual']))
    shutil.copyfile(args.pages, args.output/'canonical_pages.jsonl')
    shutil.copyfile(args.queries, args.output/'queries.jsonl')
    for shard in range(SHARDS):
        shutil.copyfile(args.ocr/f'ocr_{shard:02d}.jsonl', args.output/f'ocr_{shard:02d}.jsonl')
    print(json.dumps({'tops_sha256': sha256(args.output/'tops.npz'), 'pages': total, 'queries': queries}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
