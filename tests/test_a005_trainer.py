"""A005 trainer on synthetic records: it learns when the anchor is wrong, keeps epoch 0 when it is right."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from qpaf.a005.trainer import train  # noqa: E402
from qpaf.m24.dataset import QueryRecord  # noqa: E402

ANCHOR = [0., 0.1, 0.9]


def records(count, seed, relevant_channel, pages=12, doc_ids=False):
    """The relevant page is best on `relevant_channel`; other channels are noise."""
    rng, out = random.Random(seed), []
    for q in range(count):
        target = rng.randrange(pages)
        ids, raw = [], []
        for p in range(pages):
            triple = [rng.random()*0.8 for _ in range(3)]
            if p == target:
                triple[relevant_channel] = 1.
            raw.append(tuple(triple))
            ids.append(f'd{q}x{p // 3}_{p}' if doc_ids else f'q{q}p{p}')
        labels = tuple(int(p == target) for p in range(pages))
        out.append(QueryRecord(f'q{seed}-{q}', 'synthetic query text', tuple(ids), tuple(raw), labels, 1))
    return out


def quiet(_):
    pass


class TrainerTests(unittest.TestCase):
    def test_learns_away_from_a_wrong_anchor(self):
        result = train(ANCHOR, 'page', 20260820, records(48, 1, 0), records(24, 2, 0),
                       query_length_cap=64, epochs=5, log=quiet)
        self.assertGreater(result['best_epoch'], 0)
        self.assertGreater(result['best_value'], result['history'][0]['validation_ndcg_at_10'])

    def test_keeps_epoch_zero_when_the_anchor_is_already_perfect(self):
        result = train(ANCHOR, 'page', 20260820, records(32, 3, 2), records(16, 4, 2),
                       query_length_cap=64, epochs=3, log=quiet)
        self.assertEqual(result['history'][0]['validation_ndcg_at_10'], 1.)
        self.assertEqual(result['best_epoch'], 0)

    def test_document_unit_trains_and_is_deterministic(self):
        train_rows, validation_rows = records(24, 5, 0, doc_ids=True), records(12, 6, 0, doc_ids=True)
        relevant = {}
        for record in train_rows+validation_rows:
            page = record.page_ids[record.labels.index(1)]
            relevant[record.query_id] = {page.rpartition('_')[0]}
        kwargs = dict(query_length_cap=64, epochs=2, log=quiet, train_relevant_documents=relevant,
                      validation_relevant_documents=relevant)
        first = train(ANCHOR, 'query', 20260821, train_rows, validation_rows, **kwargs)
        second = train(ANCHOR, 'query', 20260821, train_rows, validation_rows, **kwargs)
        strip = lambda h: [{k: v for k, v in row.items() if k != 'seconds'} for row in h]  # noqa: E731
        self.assertEqual(strip(first['history']), strip(second['history']))
        self.assertTrue(all(row['train_loss'] is None or row['train_loss'] > 0 for row in first['history']))


if __name__ == '__main__':
    unittest.main()
