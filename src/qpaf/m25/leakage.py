"""Read-only split and candidate checks before baseline/statistical evaluation."""
import hashlib
import json
import math
from pathlib import Path

from qpaf.m24.dataset import SCORE_COLUMNS

ROLE_FILES = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_frozen_splits(root, config):
    """Verify exact M2.1 bytes, role coverage, disjointness and M1.3 source manifest."""
    root = Path(root)
    manifest_path = root/config['split_manifest']
    manifest_bytes = manifest_path.read_bytes()
    if _sha256(manifest_bytes) != config['split_manifest_sha256']:
        raise ValueError('M2.1 split manifest hash mismatch')
    manifest = json.loads(manifest_bytes)
    if (manifest.get('status') != 'VERIFIED_ACTIVE_PRIMARY_SPLITS' or
            manifest.get('dataset', {}).get('name') != config['dataset']):
        raise ValueError('M2.1 split manifest is not the frozen active dataset')
    source_path = root/manifest['split_bundle']['manifest_path']
    if _sha256(source_path.read_bytes()) != manifest['split_bundle']['manifest_sha256']:
        raise ValueError('M1.3 split manifest hash mismatch')
    roles = {}
    hashes = {}
    for role in ROLE_FILES:
        record = manifest['roles'][role]
        if Path(record['id_manifest']).name != ROLE_FILES[role]:
            raise ValueError(f'{role}: unexpected split file')
        data = (root/record['id_manifest']).read_bytes()
        if (b'\r' in data or not data.endswith(b'\n') or _sha256(data) != record['sha256']
                or len(data) != record['size_bytes']):
            raise ValueError(f'{role}: split bytes/hash mismatch')
        ids = data.decode('utf-8').splitlines()
        if (len(ids) != record['count'] or len(set(ids)) != len(ids) or
                any(not q or q != q.strip() for q in ids)):
            raise ValueError(f'{role}: invalid ID count/content')
        roles[role] = ids
        hashes[role] = _sha256(data)
    union = set().union(*(set(ids) for ids in roles.values()))
    if len(union) != sum(map(len, roles.values())) or len(union) != 1142:
        raise ValueError('Frozen split roles overlap or lack queries')
    query_hash = _sha256(''.join(q+'\n' for q in sorted(union)).encode('utf-8'))
    if query_hash != manifest['query_ids_sha256']:
        raise ValueError('Split union differs from frozen query set')
    if [len(roles[r]) for r in ROLE_FILES] != [799, 171, 172]:
        raise ValueError('Unexpected M2.1 role sizes')
    return {'status': 'PASS', 'role_counts': {r: len(roles[r]) for r in roles},
            'role_sha256': hashes, 'query_ids_sha256': query_hash, 'roles': roles}


def audit_score_rows(rows, splits, *, roles=('train', 'validation'), max_candidates=600):
    """Require label-free cache schema and complete requested-role candidate keys."""
    if not rows or not roles or any(role not in ROLE_FILES for role in roles):
        raise ValueError('Nonempty rows and valid requested roles required')
    owner = {q: role for role, ids in splits.items() for q in ids}
    if len(owner) != sum(len(ids) for ids in splits.values()):
        raise ValueError('Split overlap')
    counts = {}
    keys = set()
    for row in rows:
        if set(row) != set(SCORE_COLUMNS):
            raise ValueError('Score row must contain only five label-free contract fields')
        query_id, page_id = row['query_id'], row['page_id']
        if not isinstance(query_id, str) or query_id not in owner or not isinstance(page_id, str) or not page_id:
            raise ValueError('Orphan query or invalid page ID')
        if owner[query_id] not in roles:
            continue  # Test role remains unopened, as in M2.4.
        key = (query_id, page_id)
        if key in keys:
            raise ValueError('Duplicate candidate key')
        keys.add(key)
        if any(type(row[name]) not in (int, float) or not math.isfinite(row[name])
               for name in SCORE_COLUMNS[2:]):
            raise ValueError('Nonfinite or invalid channel score')
        counts[query_id] = counts.get(query_id, 0)+1
        if counts[query_id] > max_candidates:
            raise ValueError('Candidate cap exceeded')
    requested = {q for role in roles for q in splits[role]}
    if set(counts) != requested:
        raise ValueError('Requested split has uncovered queries')
    return {'status': 'PASS', 'query_count': len(requested), 'candidate_count': len(keys),
            'candidate_keys_sha256': _sha256(''.join(f'{q}\t{p}\n' for q, p in sorted(keys)).encode('utf-8'))}


def assert_matched_candidates(*candidate_sets):
    """Fail if any compared method used different query/page pairs."""
    if len(candidate_sets) < 2 or not candidate_sets[0]:
        raise ValueError('At least two nonempty candidate sets required')
    reference = set(candidate_sets[0])
    if any(set(items) != reference or len(items) != len(reference) for items in candidate_sets):
        raise ValueError('Compared methods have mismatched candidate rows')
    return True
