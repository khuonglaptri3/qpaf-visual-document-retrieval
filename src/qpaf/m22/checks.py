"""Independent score references, precision checks and deterministic ranking."""
from collections import Counter
import math
import re


def bm25_reference(queries, texts, k1, b):
    docs = [Counter(re.findall(r'\w+', text.lower())) for text in texts]
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths)/len(docs) if docs else 0
    result = []
    for query in queries:
        values = []
        for doc, length in zip(docs, lengths):
            score = 0.
            for term in re.findall(r'\w+', query.lower()):
                tf = doc[term]
                if tf and average:
                    df = sum(term in other for other in docs)
                    score += math.log1p((len(docs)-df+.5)/(df+.5))*tf*(k1+1)/(tf+k1*(1-b+b*length/average))
            values.append(score)
        result.append(values)
    return result


def compare(actual, reference, atol, rtol=0):
    import numpy as np
    actual, reference = np.asarray(actual, dtype='float64'), np.asarray(reference, dtype='float64')
    if actual.shape != reference.shape or not actual.size:
        raise ValueError('Parity shape mismatch/empty arrays')
    if not np.isfinite(actual).all() or not np.isfinite(reference).all():
        raise ValueError('Nonfinite parity values')
    diff = np.abs(actual-reference)
    return {'passed': bool(np.allclose(actual, reference, atol=atol, rtol=rtol)),
            'max_abs_error': float(diff.max()),
            'max_relative_error': float((diff/np.maximum(np.abs(reference), 1e-12)).max()),
            'atol': atol, 'rtol': rtol, 'shape': list(actual.shape)}


def rankings(scores, page_ids):
    return [[page_ids[i] for i in sorted(range(len(page_ids)), key=lambda i: (-float(row[i]), page_ids[i]))]
            for row in scores]


def maxsim_reference(queries, pages):
    """Unpadded float32 per-pair MaxSim, independent of processor batching."""
    import torch
    return torch.tensor([[float((q.float() @ p.float().T).max(dim=1).values.sum())
                          for p in pages] for q in queries]).numpy()


def compare_multivectors(actual, reference, atol, rtol):
    """Ignore only explicit zero vectors from attention padding."""
    import torch
    rows = []
    if len(actual) != len(reference) or not actual:
        raise ValueError('Embedding ID/count mismatch')
    for a, b in zip(actual, reference):
        a, b = a[a.float().norm(dim=-1) != 0], b[b.float().norm(dim=-1) != 0]
        rows.append(compare(a.float().numpy(), b.float().numpy(), atol, rtol))
    return {'passed': all(r['passed'] for r in rows), 'count': len(rows),
            'max_abs_error': max(r['max_abs_error'] for r in rows), 'atol': atol, 'rtol': rtol}
