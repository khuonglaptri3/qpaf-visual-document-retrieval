import argparse
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from oracle_study.cli import (
    command_budget,
    command_build_cache,
    command_preflight,
    command_qpaf,
)


class CliEndToEndTest(unittest.TestCase):
    def test_cache_to_oracle_artifacts(self):
        rows = []
        for query_index in range(6):
            for page_index in range(12):
                relevant = int(page_index == query_index % 4)
                rows.append(
                    {
                        "dataset": "synthetic",
                        "query_id": f"q{query_index:02d}",
                        "page_id": f"p{page_index:02d}",
                        "source": "chart" if query_index % 2 else "table",
                        "relevance": relevant,
                        "bm25_score": 12 - abs(page_index - query_index),
                        "dense_score": 10 - abs(page_index - (query_index % 4)),
                        "stage1_score": 8 - abs(page_index - (query_index % 5)),
                        "visual_score": 9 if relevant else 1 / (page_index + 1),
                        "full_score": 10 if relevant else 1 / (page_index + 1),
                        "stage2_ms": 5.0 + query_index,
                        "stage2_flops": 100.0 + query_index,
                    }
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.parquet"
            pd.DataFrame(rows).to_parquet(raw_path, index=False)
            cache_dir = root / "cache"
            command_build_cache(
                argparse.Namespace(
                    raw=str(raw_path),
                    min_coverage=0.95,
                    query_metrics=None,
                    output_dir=str(cache_dir),
                )
            )
            command_preflight(
                argparse.Namespace(
                    scores=str(cache_dir / "retrieval_scores.parquet"),
                    metrics=str(cache_dir / "query_metrics.parquet"),
                    output=str(root / "preflight.json"),
                    reference_means=None,
                    reproduction_tolerance=0.01,
                )
            )
            command_qpaf(
                argparse.Namespace(
                    scores=str(cache_dir / "retrieval_scores.parquet"),
                    output_dir=str(root / "qpaf"),
                    grids="w7,w66",
                    bootstrap=50,
                )
            )
            command_budget(
                argparse.Namespace(
                    metrics=str(cache_dir / "query_metrics.parquet"),
                    output_dir=str(root / "budget"),
                    random_repeats=5,
                    bootstrap=50,
                )
            )

            expected = [
                root / "preflight.json",
                root / "qpaf" / "qpaf_oracle_results.jsonl",
                root / "qpaf" / "qpaf_oracle_gain.png",
                root / "budget" / "budget_oracle_results.jsonl",
                root / "budget" / "budget_oracle_curve.png",
                root / "budget" / "budget_cost_curves.png",
            ]
            for path in expected:
                self.assertTrue(path.is_file(), str(path))
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
