import unittest

import pandas as pd

from oracle_study.sampling import stratified_query_sample


class SamplingTest(unittest.TestCase):
    def test_sampling_is_deterministic(self):
        frame = pd.DataFrame(
            {
                "query_id": [f"q{i}" for i in range(20)],
                "source": ["a"] * 10 + ["b"] * 10,
                "doc_ids": [["p"] if i % 2 else ["p", "q"] for i in range(20)],
            }
        )
        first = stratified_query_sample(frame, n=8)
        second = stratified_query_sample(frame, n=8)
        self.assertEqual(first["query_id"].tolist(), second["query_id"].tolist())
        self.assertEqual(len(first), 8)

    def test_relevant_count_schema_is_supported(self):
        frame = pd.DataFrame(
            {
                "query_id": [f"q{i}" for i in range(12)],
                "source": ["a"] * 6 + ["b"] * 6,
                "relevant_count": [1, 2] * 6,
            }
        )
        sampled = stratified_query_sample(frame, n=8)
        self.assertEqual(len(sampled), 8)
        self.assertIn("relevant_count", sampled)


if __name__ == "__main__":
    unittest.main()
