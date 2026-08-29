from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from oracle_study.metrics import evaluate_scores, stable_order


REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "artifacts" / "metric_reference.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("fixture_name", list(REFERENCE["fixtures"]))
def test_metrics_match_frozen_hand_computed_reference(fixture_name: str) -> None:
    fixture = REFERENCE["fixtures"][fixture_name]
    actual = evaluate_scores(
        np.asarray(fixture["scores"], dtype=float),
        np.asarray(fixture["relevance"], dtype=float),
        np.asarray(fixture["page_ids"], dtype=str),
    )
    tolerance = REFERENCE["absolute_tolerance"]
    for name, expected in fixture["expected"].items():
        assert getattr(actual, name) == pytest.approx(expected, rel=0, abs=tolerance)


def test_graded_tie_uses_the_frozen_ascending_page_id_order() -> None:
    fixture = REFERENCE["fixtures"]["graded_relevance_with_score_tie"]
    actual = stable_order(
        np.asarray(fixture["scores"], dtype=float),
        np.asarray(fixture["page_ids"], dtype=str),
    )
    np.testing.assert_array_equal(actual, fixture["stable_order"])
