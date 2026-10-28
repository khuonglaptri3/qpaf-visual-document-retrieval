"""A005 anchored gate and document aggregation, on synthetic inputs only."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import torch  # noqa: E402

from qpaf.a005.losses import LOG_TAU_BOUNDS  # noqa: E402
from qpaf.a005.model import AnchoredFusionGate, document_metrics, document_of, document_scores  # noqa: E402
from qpaf.m12.features import FEATURE_NAMES, FeatureBatch  # noqa: E402

ANCHOR = [0., 0.1, 0.9]


def batch(seed=0, queries=2, pages=4):
    generator = torch.Generator().manual_seed(seed)
    values = torch.rand(queries, pages, len(FEATURE_NAMES), generator=generator, dtype=torch.float64)
    scores = torch.rand(queries, pages, 3, generator=generator, dtype=torch.float64)
    mask = torch.ones(queries, pages, dtype=torch.bool)
    mask[1, -1] = False
    return FeatureBatch(values, scores, mask)


class AnchoredGateTests(unittest.TestCase):
    def test_epoch_zero_is_the_anchor_for_both_granularities(self):
        expected = torch.tensor([(w+1e-3)/1.003 for w in ANCHOR], dtype=torch.float64)
        for granularity in ('query', 'page'):
            out = AnchoredFusionGate(ANCHOR, granularity)(batch())
            active = out.weights[batch().mask]
            self.assertTrue(torch.allclose(active, expected.expand_as(active), atol=0, rtol=1e-15))

    def test_matched_variants_share_parameters_and_differ_only_in_granularity(self):
        qarf, qpaf = AnchoredFusionGate(ANCHOR, 'query'), AnchoredFusionGate(ANCHOR, 'page')
        self.assertEqual([p.shape for p in qarf.parameters()], [p.shape for p in qpaf.parameters()])
        self.assertEqual(sum(p.numel() for p in qpaf.parameters()), 13*3+3+1)

    def test_query_gate_is_constant_within_a_query_page_gate_is_not(self):
        b = batch(seed=3)
        for granularity, constant in (('query', True), ('page', False)):
            model = AnchoredFusionGate(ANCHOR, granularity)
            with torch.no_grad():
                model.delta.weight.normal_(generator=torch.Generator().manual_seed(1))
            w = model(b).weights[0]
            self.assertEqual(torch.allclose(w, w[:1].expand_as(w)), constant)

    def test_padding_gets_zero_weight_and_scores_stay_fused(self):
        out = AnchoredFusionGate(ANCHOR, 'page')(batch())
        self.assertTrue((out.weights[1, -1] == 0).all())
        self.assertEqual(out.scores[1, -1].item(), 0.)

    def test_loss_temperature_is_clamped(self):
        model = AnchoredFusionGate(ANCHOR)
        with torch.no_grad():
            model.log_tau.fill_(-50.)
        self.assertEqual(model.loss_log_tau().item(), LOG_TAU_BOUNDS[0])

    def test_invalid_anchor_refused(self):
        for anchor in ([0.5, 0.5, 0.5], [-0.1, 0.2, 0.9], [1., 0.]):
            with self.assertRaises(ValueError):
                AnchoredFusionGate(anchor)


class DocumentTests(unittest.TestCase):
    def test_document_mapping_drops_final_segment(self):
        self.assertEqual(document_of('report_2021_page_7'), 'report_2021_page')
        with self.assertRaises(ValueError):
            document_of('nounderscore')

    def test_max_aggregation_tie_goes_to_smallest_page_and_one_page_gets_gradient(self):
        scores = torch.tensor([0.4, 0.7, 0.7, 0.2], dtype=torch.float64, requires_grad=True)
        documents, doc_scores = document_scores(scores, ['a_2', 'a_1', 'b_9', 'b_1'])
        self.assertEqual(documents, ['a', 'b'])
        self.assertEqual(doc_scores.tolist(), [0.7, 0.7])
        doc_scores[0].backward()
        self.assertEqual(scores.grad.tolist(), [0., 1., 0., 0.])

    def test_idcg_counts_relevant_documents_outside_the_candidates(self):
        metrics = document_metrics(['a_1', 'b_1', 'c_1'], [0.9, 0.5, 0.1], ['b', 'z'])
        ideal = 1+1/math.log2(3)
        self.assertAlmostEqual(metrics['ndcg_at_10'], (1/math.log2(3))/ideal, places=12)
        self.assertEqual(metrics['recall_at_1'], 0.)
        self.assertEqual(metrics['mrr_at_10'], 0.5)


if __name__ == '__main__':
    unittest.main()
