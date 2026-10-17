from __future__ import annotations

import io

import torch

from oracle_study.learned.models import FusionScorer, LinearQARFGate, LinearQPAFGate


def test_zero_initialization_produces_equal_weights_and_mean_fusion() -> None:
    features = torch.randn(2, 5, 13, dtype=torch.float32)
    scores = torch.rand(2, 5, 3, dtype=torch.float32)
    mask = torch.tensor(
        [[True, True, True, False, False], [True, True, True, True, True]]
    )

    qpaf = LinearQPAFGate()
    qarf = LinearQARFGate()
    qpaf_weights = qpaf(features, mask)
    qarf_weights = qarf(features, mask)

    expected = torch.full_like(qpaf_weights, 1.0 / 3.0)
    torch.testing.assert_close(qpaf_weights, expected, atol=1e-7, rtol=0)
    torch.testing.assert_close(qarf_weights, expected, atol=1e-7, rtol=0)
    assert sum(parameter.numel() for parameter in qpaf.parameters()) == 42
    assert sum(parameter.numel() for parameter in qarf.parameters()) == 42

    fused = FusionScorer()(scores, qpaf_weights, mask)
    torch.testing.assert_close(fused[mask], scores.mean(dim=-1)[mask], atol=1e-7, rtol=0)
    assert torch.equal(fused[~mask], torch.zeros_like(fused[~mask]))


def test_qarf_pool_ignores_padded_features_and_broadcasts_per_query() -> None:
    gate = LinearQARFGate()
    with torch.no_grad():
        gate.linear.weight.copy_(torch.arange(39).reshape(3, 13) / 100.0)
    features = torch.rand(1, 4, 13)
    mask = torch.tensor([[True, True, False, False]])
    baseline = gate(features, mask)
    changed = features.clone()
    changed[:, 2:] = 1_000.0
    actual = gate(changed, mask)

    torch.testing.assert_close(actual, baseline)
    torch.testing.assert_close(actual[:, 0], actual[:, 1])
    torch.testing.assert_close(actual[:, 0], actual[:, 3])


def test_gate_checkpoint_round_trip_reproduces_weights() -> None:
    gate = LinearQPAFGate()
    with torch.no_grad():
        gate.linear.weight.copy_(torch.arange(39).reshape(3, 13) / 50.0)
        gate.linear.bias.copy_(torch.tensor([-0.2, 0.1, 0.3]))
    features = torch.rand(2, 3, 13)
    mask = torch.ones(2, 3, dtype=torch.bool)
    expected = gate(features, mask)

    payload = io.BytesIO()
    torch.save(gate.state_dict(), payload)
    payload.seek(0)
    restored = LinearQPAFGate()
    restored.load_state_dict(torch.load(payload, weights_only=True))
    torch.testing.assert_close(restored(features, mask), expected, atol=0, rtol=0)
