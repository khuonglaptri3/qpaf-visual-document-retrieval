"""Deterministic label-free split generation and verification."""
import hashlib
from typing import Dict, List, Optional, Tuple


def hash_query_for_split(query_id: str, seed: int, namespace: str = "vidoseek_v1") -> bytes:
    """Compute deterministic SHA256 digest for a query ID."""
    token = f"{namespace}:{seed}:{query_id}".encode("utf-8")
    return hashlib.sha256(token).digest()


def create_deterministic_splits(
    query_ids: List[str],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 2026,
    namespace: str = "vidoseek_v1",
) -> Dict[str, List[str]]:
    """Derive deterministic splits based on label-free hash sorting.

    Ensures total count matches exactly and partitions are disjoint.
    """
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError("Train, val, and test ratios must sum to 1.0")

    total = len(query_ids)
    if total == 0:
        return {"train": [], "val": [], "test": []}

    # Deterministic sort based on (hash bytes, query_id)
    ranked = sorted(
        query_ids,
        key=lambda q: (hash_query_for_split(q, seed, namespace), q),
    )

    n_train = int(round(total * train_ratio))
    n_val = int(round(total * val_ratio))
    # Ensure exact sum
    if n_train + n_val > total:
        n_val = total - n_train
    n_test = total - (n_train + n_val)

    train_ids = ranked[:n_train]
    val_ids = ranked[n_train : n_train + n_val]
    test_ids = ranked[n_train + n_val :]

    return {
        "train": sorted(train_ids),
        "val": sorted(val_ids),
        "test": sorted(test_ids),
    }


def verify_split_disjointness(
    splits: Dict[str, List[str]],
    total_expected: Optional[int] = None,
) -> Tuple[bool, str]:
    """Verify pairwise disjointness and completeness of splits."""
    keys = list(splits.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            set_i = set(splits[keys[i]])
            set_j = set(splits[keys[j]])
            overlap = set_i.intersection(set_j)
            if overlap:
                return False, f"Overlap detected between '{keys[i]}' and '{keys[j]}': {sorted(list(overlap))[:5]}"

    all_ids = set()
    for k, ids in splits.items():
        all_ids.update(ids)

    if total_expected is not None and len(all_ids) != total_expected:
        return False, f"Total unique queries {len(all_ids)} does not match expected {total_expected}"

    return True, "Splits are strictly disjoint and complete"


def serialize_split_manifest(ids: List[str]) -> Tuple[str, str]:
    """Serialize list of IDs to newline-delimited string and compute its SHA256."""
    text = "".join(f"{item}\n" for item in ids)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, digest
