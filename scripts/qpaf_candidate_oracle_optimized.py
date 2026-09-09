from __future__ import annotations

import bisect

import numpy as np

from oracle_study.metrics import RankingMetrics, dcg_at_k, evaluate_scores, stable_order
from oracle_study.qpaf import TOLERANCE, _discounts


def candidate_oracle_exact_fast(
    score_matrix: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
    profiles: np.ndarray,
    query_profile_index: int,
    query_scores: np.ndarray,
    query_metrics: RankingMetrics,
    max_sweeps: int = 2,
) -> tuple[np.ndarray, np.ndarray, RankingMetrics, int]:
    """Match the frozen candidate oracle while reusing candidate-invariant ranking state."""
    assignments = np.full(len(page_ids), query_profile_index, dtype=int)
    current_scores = query_scores.copy()
    current_metrics = query_metrics
    fixed_order = stable_order(query_scores, page_ids)
    changes = 0

    gains = np.power(2.0, relevance.astype(float)) - 1.0
    discounts = _discounts(len(page_ids), 10)
    ideal_dcg = dcg_at_k(np.sort(relevance)[::-1], 10)

    for _ in range(max_sweeps):
        changed_this_sweep = 0
        for candidate_index in fixed_order:
            candidate_index = int(candidate_index)
            order = stable_order(current_scores, page_ids)
            positions = np.empty(len(order), dtype=int)
            positions[order] = np.arange(len(order))
            old_position = int(positions[candidate_index])
            other_order = order[order != candidate_index]
            other_keys = [
                (-float(current_scores[index]), str(page_ids[index]))
                for index in other_order
            ]
            ranked_gains = gains[order]
            current_dcg = current_metrics.ndcg10 * ideal_dcg
            shifts_up = ranked_gains * (discounts[1:] - discounts[:-1])
            shifts_down = np.zeros(len(order), dtype=float)
            shifts_down[1:] = ranked_gains[1:] * (discounts[:-2] - discounts[1:-1])

            best_profile = int(assignments[candidate_index])
            best_ndcg = current_metrics.ndcg10
            best_score = float(current_scores[candidate_index])
            for profile_index, profile in enumerate(profiles):
                if profile_index == assignments[candidate_index]:
                    continue
                new_score = float(score_matrix[candidate_index] @ profile)
                new_position = bisect.bisect_left(
                    other_keys,
                    (-new_score, str(page_ids[candidate_index])),
                )
                if new_position == old_position:
                    ndcg = current_metrics.ndcg10
                elif ideal_dcg <= 0:
                    ndcg = 0.0
                else:
                    item_gain = gains[candidate_index]
                    delta = item_gain * (
                        discounts[new_position] - discounts[old_position]
                    )
                    if new_position < old_position:
                        delta += float(shifts_up[new_position:old_position].sum())
                    else:
                        delta += float(
                            shifts_down[old_position + 1 : new_position + 1].sum()
                        )
                    ndcg = max(0.0, min(1.0, (current_dcg + delta) / ideal_dcg))
                if ndcg > best_ndcg + TOLERANCE:
                    best_profile = profile_index
                    best_ndcg = ndcg
                    best_score = new_score
            if best_profile != assignments[candidate_index]:
                assignments[candidate_index] = best_profile
                current_scores[candidate_index] = best_score
                current_metrics = evaluate_scores(current_scores, relevance, page_ids)
                changed_this_sweep += 1
                changes += 1
        if changed_this_sweep == 0:
            break
    return assignments, current_scores, current_metrics, changes
