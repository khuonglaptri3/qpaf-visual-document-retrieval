from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import SEED


def stratified_query_sample(
    queries: pd.DataFrame,
    n: int = 2_000,
    seed: int = SEED,
) -> pd.DataFrame:
    required = {"query_id", "source"}
    missing = required - set(queries.columns)
    if missing:
        raise ValueError(f"Query table is missing required columns: {sorted(missing)}")
    if "relevant_count" not in queries and "doc_ids" not in queries:
        raise ValueError("Query table needs relevant_count or doc_ids for stratification")
    if queries["query_id"].astype(str).duplicated().any():
        raise ValueError("Query table contains duplicate query_id values")
    if n >= len(queries):
        return queries.sort_values("query_id", kind="stable").reset_index(drop=True)
    frame = queries.copy()
    if "relevant_count" in frame:
        counts = pd.to_numeric(frame["relevant_count"], errors="raise")
        if counts.lt(1).any():
            raise ValueError("relevant_count must be at least 1 for every sampled query")
        frame["relevance_group"] = counts.gt(1).map({True: "multi", False: "single"})
    else:
        frame["relevance_group"] = frame["doc_ids"].map(
            lambda value: "multi" if len(value) > 1 else "single"
        )
    rng = np.random.default_rng(seed)
    selected_indices: list[int] = []
    groups = list(frame.groupby(["source", "relevance_group"], sort=True))
    allocations = []
    for key, group in groups:
        exact = n * len(group) / len(frame)
        allocations.append([key, group, int(np.floor(exact)), exact - np.floor(exact)])
    remainder = n - sum(item[2] for item in allocations)
    for item in sorted(allocations, key=lambda value: (-value[3], str(value[0])))[:remainder]:
        item[2] += 1
    for _, group, count, _ in allocations:
        if count:
            selected_indices.extend(rng.choice(group.index.to_numpy(), size=count, replace=False).tolist())
    result = frame.loc[selected_indices].drop(columns="relevance_group")
    return result.sort_values("query_id", kind="stable").reset_index(drop=True)
