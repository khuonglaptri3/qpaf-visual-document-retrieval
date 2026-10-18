"""Deterministic synthetic score rows for software verification only.

Visual-style queries get an informative visual channel, text-style queries an
informative BM25 channel. The other two channels agree on a non-relevant
distractor page, so uniform fusion is fooled and a learned gate can beat it,
which is all this fixture is meant to show.
"""
import random


def make_fixture(seed=20260820, queries_per_role=(24, 8, 8), candidates=12):
    rng = random.Random(f'm24-synthetic:{seed}')
    rows, queries, qrels, splits = [], {}, {}, {}
    for role, count in zip(('train', 'validation', 'test'), queries_per_role):
        splits[role] = []
        for index in range(count):
            query_id = f'{role}-{index:03d}'
            visual = index % 2 == 0
            queries[query_id] = 'revenue chart figure' if visual else 'contract clause text definition term'
            relevant, distractor = rng.sample(range(candidates), 2)
            # One relevant page is deliberately outside the candidate union.
            qrels[query_id] = {f'{query_id}-p{relevant:02d}': 1, f'{query_id}-p{distractor:02d}': 0,
                               f'{query_id}-outside': 1}
            for page in range(candidates):
                informative = 2.*(page == relevant)+rng.gauss(0, .5)
                noise = [3.*(page == distractor)+rng.gauss(0, .5) for _ in range(3)]
                rows.append({'query_id': query_id, 'page_id': f'{query_id}-p{page:02d}',
                             'bm25_score': noise[0] if visual else informative,
                             'dense_score': noise[1],
                             'visual_score': informative if visual else noise[2]})
            splits[role].append(query_id)
    return rows, queries, qrels, splits
