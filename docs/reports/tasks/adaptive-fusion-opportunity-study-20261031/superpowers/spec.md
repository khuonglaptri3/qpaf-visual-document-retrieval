# Adaptive fusion opportunity study — research scope

Date: 2026-10-31. User asks for deep research into conditions and datasets where the group's
query/page-adaptive fusion could outperform one fixed weight vector.

## Research question

Identify defensible, falsifiable opportunities for QARF/QPAF rather than seek a guaranteed favorable test set.
Distinguish global-static vs query-adaptive gains from query-adaptive vs page-adaptive gains.

## Existing context

Use [F3 report](../../lab-f3-objective-20261030/README.md), the original QPAF proposal and method code.
ViDoSeek CV: static nDCG@10 0.865492; best observed QARF + ApproxNDCG 0.866475 without a clear CI gain.
Baseline/Top-k QPAF underperform static; no ViMDoc F3 experiment was run.
Existing feature-lab F1/F4 propose content/query inputs beyond score-derived features.

## Authorized deliverables

A Vietnamese research report, primary-source evidence ledger, dataset comparison, proposed diagnostics,
and a staged experiment recommendation. No training, paid/cloud compute, model/corpus downloads,
test/confirmation label inspection, production changes, or new claims of experimental gains.
Dataset counts, modalities, labeling units, access and splits must be checked against primary sources.
Broader datasets outside the current proposal must be labeled as a proposed protocol extension.

## Acceptance

- Explain measurable channel complementarity, observable routing cues, within-query candidate conflicts,
  ceiling effects, and why multimodal data alone does not establish an adaptive advantage.
- Separate published evidence, local evidence, mathematical examples, and new hypotheses.
- Recommend a short ranked dataset shortlist, with limitations and uncertainty; guarantee no success.
- Specify fair strong-static and other necessary controls, held-out validation and contamination safeguards.
- Give concrete first steps using current assets, plus stop/go diagnostics that do not select on test outcomes.
- Preserve exact owner layout and actual workflow provenance; link report to spec/plan/evidence.
