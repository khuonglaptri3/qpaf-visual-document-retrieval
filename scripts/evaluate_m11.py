"""Evaluate exported complete caches locally; no Modal or model dependencies needed."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import StageRun, digest, read_json, source_provenance
from qpaf.m11.config import load_config
from qpaf.m11.pipeline import write_reports, verify_generation_config
from qpaf.m11.retrieval import load_score_cache


def main():
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--prepared', required=True, type=Path, help='Successful prepare attempt directory')
    for channel in ('bm25', 'dense', 'visual'):
        parser.add_argument('--'+channel, required=True, type=Path, help='Successful score attempt directory')
    parser.add_argument('--output', required=True, type=Path, help='New result directory')
    parser.add_argument('--set', action='append', default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output directory already exists; choose a new result directory')
    config = load_config(args.config, args.set)
    folders = {'prepare': args.prepared, 'bm25': args.bm25, 'dense': args.dense, 'visual': args.visual}
    inputs = {}
    for name, path in folders.items():
        verify_generation_config(path, name, config)
        inputs[name] = digest(path/'receipt.json')
    for channel in ('bm25', 'dense', 'visual'):
        if read_json(folders[channel]/'receipt.json')['inputs'].get('prepare') != inputs['prepare']:
            raise ValueError(f'{channel} cache belongs to a different prepared dataset')
    queries = read_json(args.prepared/'queries.json')
    pages = read_json(args.prepared/'pages.json')
    arrays = [load_score_cache(folders[name], [q['query_id'] for q in queries],
              [p['page_id'] for p in pages], name) for name in ('bm25', 'dense', 'visual')]
    with StageRun(args.output, 'oracle', config, inputs, source_provenance(ROOT, config['modal']['requirements_file'])) as run:
        write_reports(run.path, queries, pages, read_json(args.prepared/'qrels.json'),
                      np.stack(arrays, axis=-1), config, read_json(args.prepared/'dataset.json'), run.logger)
    print(run.path)


if __name__ == '__main__':
    main()
