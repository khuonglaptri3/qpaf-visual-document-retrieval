from __future__ import annotations

import torch

from oracle_study.learned.losses import ListwiseRankLoss
from oracle_study.learned.models import FusionScorer, LinearQPAFGate


def test_qpaf_loss_passes_gradcheck_and_has_finite_gradients() -> None:
    torch.manual_seed(20260820)
    gate = LinearQPAFGate().double()
    with torch.no_grad():
        gate.linear.weight.copy_(torch.randn_like(gate.linear.weight) * 0.05)
        gate.linear.bias.copy_(torch.randn_like(gate.linear.bias) * 0.05)
    scorer = FusionScorer()
    loss_fn = ListwiseRankLoss(temperature=0.7)
    features = torch.randn(1, 3, 13, dtype=torch.float64, requires_grad=True)
    scores = torch.rand(1, 3, 3, dtype=torch.float64, requires_grad=True)
    relevance = torch.tensor([[2.0, 1.0, 0.0]], dtype=torch.float64)
    groups = torch.tensor([[0, 1, 2]])
    mask = torch.ones(1, 3, dtype=torch.bool)

    def objective(feature_values: torch.Tensor, score_values: torch.Tensor) -> torch.Tensor:
        weights = gate(feature_values, mask)
        fused = scorer(score_values, weights, mask)
        return loss_fn(fused, relevance, groups, mask, mask)

    assert torch.autograd.gradcheck(
        objective, (features, scores), eps=1e-6, atol=1e-4, rtol=1e-3
    )
    objective(features, scores).backward()
    for parameter in gate.parameters():
        assert parameter.grad is not None
        assert torch.isfinite(parameter.grad).all()


def test_equation_11_matches_autograd() -> None:
    temperature = 0.8
    logits = torch.tensor(
        [[[0.2, -0.1, 0.3], [0.0, 0.4, -0.2], [0.5, -0.3, 0.1]]],
        dtype=torch.float64,
        requires_grad=True,
    )
    channel_scores = torch.tensor(
        [[[0.9, 0.2, 0.4], [0.1, 0.8, 0.3], [0.5, 0.4, 0.7]]],
        dtype=torch.float64,
    )
    relevance = torch.tensor([[2.0, 1.0, 0.0]], dtype=torch.float64)
    groups = torch.tensor([[0, 1, 2]])
    mask = torch.ones(1, 3, dtype=torch.bool)
    weights = torch.softmax(logits, dim=-1)
    fused = (weights * channel_scores).sum(dim=-1)
    loss = ListwiseRankLoss(temperature)(fused, relevance, groups, mask, mask)
    actual = torch.autograd.grad(loss, logits)[0]

    gains = torch.pow(2.0, relevance) - 1.0
    targets = gains / gains.sum(dim=1, keepdim=True)
    probabilities = torch.softmax(fused.detach() / temperature, dim=1)
    d_score = (probabilities - targets) / temperature
    expected = (
        d_score.unsqueeze(-1)
        * weights.detach()
        * (channel_scores - fused.detach().unsqueeze(-1))
    )
    torch.testing.assert_close(actual, expected, atol=1e-10, rtol=1e-10)
