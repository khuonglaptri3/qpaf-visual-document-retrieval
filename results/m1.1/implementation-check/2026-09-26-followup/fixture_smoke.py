"""Software-only fixture: no dataset download, model inference, or Modal execution.

Run with the repository virtualenv and --output pointing at a new directory.
"""
import argparse
import io
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'src'))

import numpy as np
from qpaf.m11.artifacts import StageRun, digest, read_json, source_provenance, verify_manifest, write_json
from qpaf.m11.config import load_config
from qpaf.m11.dataset import extract_zip
from qpaf.m11.evidence import pack_evidence, verify_evidence
from qpaf.m11.pipeline import execute_stage
from qpaf.m11.retrieval import save_score_cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    workspace = args.output.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    config_path = ROOT/'configs/m1.1/vidoseek.toml'
    config = load_config(config_path, ['oracle.bootstrap_samples=20'])
    source = source_provenance(ROOT, config['modal']['requirements_file'])
    source.update(kind='synthetic_software_test', fixture_sha256=digest(__file__))
    root = workspace/'runs'/'software-fixture'
    with StageRun(root, 'prepare', config, {}, source) as prep:
        write_json(prep.path/'queries.json', [{'query_id': 'q1', 'text': 'apple'},
                                            {'query_id': 'q2', 'text': 'pear'}])
        write_json(prep.path/'pages.json', [{'page_id': 'a', 'text': 'apple fruit'},
                                          {'page_id': 'b', 'text': 'pear tree'},
                                          {'page_id': 'c', 'text': ''}])
        write_json(prep.path/'qrels.json', {'q1': {'a': 1}, 'q2': {'b': 1}})
        write_json(prep.path/'dataset.json', {'kind': 'synthetic_software_test',
                   'note': 'Synthetic text and scores; not a ViDoSeek experiment.'})
    bm25 = execute_stage('bm25', config, workspace, 'software-fixture', source)
    caches = {'bm25': bm25}
    for channel, values in [('dense', [[0., 1., .2], [1., 0., .1]]),
                            ('visual', [[.5, .5, .5], [.4, .3, .2]])]:
        with StageRun(root, channel, config, {'prepare': digest(prep.path/'receipt.json')}, source) as run:
            save_score_cache(run.path, np.asarray(values), ['q1', 'q2'], ['a', 'b', 'c'], channel)
        caches[channel] = run.path
    oracle = execute_stage('oracle', config, workspace, 'software-fixture', source)
    assert execute_stage('oracle', config, workspace, 'software-fixture', source) == oracle
    exported = workspace/'exported-evidence'
    extract_zip(io.BytesIO(pack_evidence(root, config, source)), exported)
    verify_evidence(exported)
    command = [sys.executable, str(ROOT/'scripts/evaluate_m11.py'),
               '--config', str(config_path), '--prepared', str(prep.path),
               '--output', str(workspace/'local-evaluation'), '--set', 'oracle.bootstrap_samples=20']
    for channel, folder in caches.items():
        command.extend(['--'+channel, str(folder)])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    (workspace/'local-evaluator.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    write_json(workspace/'local-evaluator-command.json', {'command': command, 'exit_code': result.returncode})
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    local_root = workspace/'local-evaluation'/'oracle'
    pointer = read_json(local_root/'complete.json')
    local = local_root/pointer['attempt']
    assert digest(local/'receipt.json') == pointer['receipt_sha256']
    verify_manifest(local, read_json(local/'receipt.json')['outputs'])
    for filename in ['query_ids.csv', 'per_query_metrics.csv', 'summary.json', 'oracle_decisions.jsonl']:
        assert (local/filename).read_bytes() == (oracle/filename).read_bytes(), filename
    assert read_json(local/'summary.json')['independent_review'] == 'pending'
    print('PASS: real BM25, synthetic dense/visual caches, Oracle resume, evidence ZIP and local evaluator CLI.')
    print('Software fixture only; no ViDoSeek/model/Modal run performed.')
    print(f'Artifacts: {workspace}')


if __name__ == '__main__':
    main()
