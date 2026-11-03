"""F9 final method on synthetic inputs only."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np  # noqa: E402

from qpaf.f9.method import (LAMBDA, RERANKER, TOP_K, F9Model, final_scores, first_stage, fit, fit_lambda,  # noqa: E402
                            lambda_table, pairs, rank)
from qpaf.lab.rerank import LAMBDAS, fuse_scores, top_of, unit_score  # noqa: E402
from qpaf.lab.rerank_stack import page_scores, train_gates  # noqa: E402
from qpaf.lab.train import SEEDS, prepare  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from tests.test_lab import synthetic  # noqa: E402

RECIPE = {'epochs': 4, 'average_from': 2}


def quiet(*_):
    pass


def reranker_table(queries, seed=1):
    rng = np.random.default_rng(seed)
    return {(q.query_id, p): float(rng.normal()) for q in queries for p in q.page_ids}


class ConstantsTests(unittest.TestCase):
    def test_lambda_is_the_preregistered_one(self):
        self.assertEqual(LAMBDA, {'vidoseek': 0.9, 'vimdoc': 0.5})

    def test_reranker_is_the_pinned_one_of_the_modal_script(self):
        text = (ROOT/'scripts/modal_lab_rerank.py').read_text(encoding='utf-8')
        entry = re.search(r"'qwen3-4b': \{'repo': '([^']+)', 'revision': '([0-9a-f]{40})'", text)
        self.assertEqual(RERANKER, entry.groups())

    def test_top_k_is_the_lab_one(self):
        from qpaf.lab.rerank import TOP_K as LAB_TOP_K
        self.assertEqual(TOP_K, LAB_TOP_K)


class FitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = synthetic(30, documents=8, pages=3)  # 24 pages, above the top-20 cut
        cls.model = fit(cls.queries, 0.5, recipe=RECIPE, log=quiet)

    def test_fit_and_first_stage_equal_the_lab_path(self):
        items = prepare(self.queries, load_variant('baseline'))
        anchor, mean, std, models = train_gates(items, SEEDS[0], recipe={**self.model.recipe}, log=quiet)
        self.assertEqual(self.model.anchor, anchor)
        self.assertEqual((self.model.lam, self.model.seed, self.model.top_k), (0.5, SEEDS[0], TOP_K))
        lab = page_scores(models['qpaf'], items, mean, std)
        for mine, theirs in zip(first_stage(self.model, self.queries), lab):
            np.testing.assert_array_equal(mine, theirs)

    def test_blocks_do_not_change_the_scores(self):
        whole = first_stage(self.model, self.queries)
        for mine, theirs in zip(first_stage(self.model, self.queries, block=7), whole):
            np.testing.assert_allclose(mine, theirs, rtol=0, atol=1e-12)
        self.assertEqual([len(s) for s in whole], [len(q.page_ids) for q in self.queries])


class RankTests(unittest.TestCase):
    def setUp(self):
        self.queries = synthetic(20, documents=8, pages=3)
        rng = np.random.default_rng(3)
        self.first = [rng.random(len(q.page_ids)) for q in self.queries]
        self.rerank = reranker_table(self.queries)
        self.model = F9Model([0.1, 0.2, 0.7], None, None, None, 0.7, SEEDS[0], TOP_K, RECIPE)

    def test_final_scores_are_the_lab_fusion(self):
        scores = rank(self.model, self.queries, self.first, self.rerank)
        for q, first, final in zip(self.queries, self.first, scores):
            by_index = {int(i): self.rerank[(q.query_id, q.page_ids[i])] for i in top_of(first)}
            np.testing.assert_array_equal(final, fuse_scores(first, by_index, 0.7))
            np.testing.assert_array_equal(final, final_scores(first, by_index, 0.7))

    def test_lambda_zero_keeps_the_first_stage_order(self):
        for q, first in zip(self.queries, self.first):
            by_index = {int(i): self.rerank[(q.query_id, q.page_ids[i])] for i in top_of(first)}
            final = final_scores(first, by_index, 0.)
            np.testing.assert_array_equal(np.argsort(-final, kind='stable'), np.argsort(-first, kind='stable'))

    def test_top_k_stay_above_the_rest(self):
        for q, first, final in zip(self.queries, self.first, rank(self.model, self.queries, self.first, self.rerank)):
            top = top_of(first)
            rest = np.setdiff1d(np.arange(len(first)), top)
            self.assertEqual(len(top), TOP_K)
            self.assertGreater(final[top].min(), final[rest].max())
            np.testing.assert_array_equal(final[rest], first[rest])

    def test_missing_reranker_score_raises_naming_query_and_page(self):
        q, first = self.queries[2], self.first[2]
        page = q.page_ids[int(top_of(first)[3])]
        del self.rerank[(q.query_id, page)]
        with self.assertRaises(KeyError) as caught:
            rank(self.model, self.queries, self.first, self.rerank)
        self.assertIn(q.query_id, str(caught.exception))
        self.assertIn(page, str(caught.exception))

    def test_pairs_cover_exactly_the_top_k(self):
        chosen = pairs(self.queries, self.first)
        self.assertEqual(len(chosen), TOP_K*len(self.queries))
        for q, first in zip(self.queries, self.first):
            expected = {q.page_ids[i] for i in top_of(first)}
            self.assertEqual({p for query_id, p in chosen if query_id == q.query_id}, expected)
        self.assertEqual({len(p) for p in chosen}, {2})
        self.assertEqual(len(pairs(self.queries, self.first, k=5)), 5*len(self.queries))


class LambdaTests(unittest.TestCase):
    def setUp(self):
        self.queries = synthetic(25, documents=8, pages=3)
        rng = np.random.default_rng(5)
        self.first = [rng.random(len(q.page_ids)) for q in self.queries]
        self.rerank = reranker_table(self.queries, seed=7)

    def brute_force(self, lambdas):
        totals = []
        for lam in lambdas:
            total = 0.
            for q, first in zip(self.queries, self.first):
                by_index = {int(i): self.rerank[(q.query_id, q.page_ids[i])] for i in top_of(first)}
                total += unit_score(q, fuse_scores(first, by_index, lam))
            totals.append(total)
        best = max(totals)
        return lambdas[min(i for i, t in enumerate(totals) if t == best)], totals

    def test_matches_a_brute_force_table(self):
        best, totals = self.brute_force(LAMBDAS)
        table = lambda_table(self.queries, self.first, self.rerank)
        self.assertEqual(table.shape, (len(self.queries), len(LAMBDAS)))
        np.testing.assert_allclose(table.sum(axis=0), totals, rtol=0, atol=1e-12)
        self.assertEqual(fit_lambda(self.queries, self.first, self.rerank), best)

    def test_matches_the_lab_rerank_script(self):
        sys.path.insert(0, str(ROOT/'scripts'))
        from lab_rerank import best_lambda, lambda_table as lab_table
        by_query = {}
        for (query_id, page), score in self.rerank.items():
            by_query.setdefault(query_id, {})[page] = score
        table = lab_table(self.queries, self.first, by_query)
        np.testing.assert_array_equal(lambda_table(self.queries, self.first, self.rerank), table)
        self.assertEqual(fit_lambda(self.queries, self.first, self.rerank),
                         LAMBDAS[best_lambda(table, np.ones(len(self.queries), dtype=bool))])

    def test_ties_keep_the_smaller_lambda(self):
        same = {(q.query_id, q.page_ids[i]): float(first[i]) for q, first in zip(self.queries, self.first)
                for i in range(len(first))}  # the reranker agrees with the first stage: every λ ranks alike
        self.assertEqual(fit_lambda(self.queries, self.first, same), 0.)
        self.assertEqual(fit_lambda(self.queries, self.first, same, lambdas=(0.3, 0.6, 0.9)), 0.3)


if __name__ == '__main__':
    unittest.main()
