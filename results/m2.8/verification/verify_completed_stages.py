"""Independent full-corpus BM25 and dense replay before relevance is accessed."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import digest, read_json, object_hash, write_json
from qpaf.m22.checks import compare
from qpaf.m28.runtime import load_array

folder = ROOT/'results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
config = read_json(folder/'resolved_config.json')
inputs = read_json(folder/'input_manifest.json')
source = read_json(folder/'source.json')
identity = {'config_sha256': object_hash(config), 'source_sha256': source['digest'],
            'input_sha256': object_hash(inputs)}
queries = read_json(folder/'queries.json')
if object_hash(queries) != inputs['query_texts_sha256']:
    raise ValueError('Query texts changed')
remote = folder/'remote'
dense = remote/'dense'
q = load_array(dense/'query_embeddings.npy', {**identity, 'kind': 'dense_queries'})
page_chunks = []
size = config['execution']['dense_shard_size']
for start in range(0, inputs['page_count'], size):
    stop = min(start+size, inputs['page_count'])
    page_chunks.append(load_array(dense/f'page_embeddings-{start:08d}.npy',
        {**identity, 'kind': 'dense_pages', 'start': start, 'stop': stop}))
p = np.concatenate(page_chunks)
actual_dense = load_array(dense/'scores.npy', {**identity, 'kind': 'dense_full'})
dense_check = compare(actual_dense, q@p.T, config['parity']['dense_atol'], config['parity']['dense_rtol'])

ocr_path = ROOT/config['ocr']['local_output']/'resolved_pages.json'
if digest(ocr_path) != inputs['m26_handover']['resolved_pages_sha256']:
    raise ValueError('OCR text payload changed')
pages = sorted(read_json(ocr_path), key=lambda r: r['page_id'])
if [p['page_id'] for p in pages] != inputs['page_ids']:
    raise ValueError('Page ID order changed')
postings = defaultdict(list)
lengths = np.zeros(len(pages), dtype=np.float64)
for index, page in enumerate(pages):
    counts = Counter(re.findall(r'\w+', page['text'].lower()))
    lengths[index] = sum(counts.values())
    for term, count in counts.items():
        postings[term].append((index, count))
average = float(lengths.mean())
k1, b = config['retrievers']['bm25']['k1'], config['retrievers']['bm25']['b']
reference_bm25 = np.zeros((len(queries), len(pages)), dtype=np.float64)
for qi, qid in enumerate(inputs['query_ids']):
    for term, repetitions in Counter(re.findall(r'\w+', queries[qid].lower())).items():
        hits = postings.get(term, [])
        if not hits or not average:
            continue
        indices = np.array([hit[0] for hit in hits])
        frequency = np.array([hit[1] for hit in hits], dtype=np.float64)
        idf = math.log((len(pages)+1)/(len(hits)+.5))
        value = idf*(k1+1)*frequency/(frequency+k1*(1-b+b*lengths[indices]/average))
        reference_bm25[qi, indices] += repetitions*value
actual_bm25 = load_array(remote/'bm25'/'scores.npy', {**identity, 'kind': 'bm25_full'})
bm25_check = compare(actual_bm25, reference_bm25, config['parity']['bm25_atol'])
report = {'status': 'PASS' if dense_check['passed'] and bm25_check['passed'] else 'FAIL',
          'full_query_page_pairs_per_channel': inputs['query_count']*inputs['page_count'],
          'dense_full_embedding_replay': dense_check, 'bm25_full_inverted_index_replay': bm25_check,
          'uses_qrels': False, 'identity': identity,
          'verifier_sha256': digest(Path(__file__))}
write_json(folder/'completed_stages_independent_replay.json', report)
print(json.dumps(report, indent=2))
if report['status'] != 'PASS':
    raise SystemExit(1)
