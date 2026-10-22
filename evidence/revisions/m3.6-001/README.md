# M3.6 — Independent integrity review and GPU protocol preparation

**Owner:** Khương. **CPU integrity:** `PASS`. **Resources / overall M3.6:**
`BLOCKED`, pending the reviewed GPU workload and measurements. **Owner acceptance:**
pending review of this record. No G2 decision is made.

[`integrity_review.json`](integrity_review.json) is the measured technical record,
completed at `2026-10-22T14:49:34Z`, after PR #28 was merged into `develop` at
`cd6b838566fbb8adb0d7ad9bf096ac1d8bce4da3`. The review was executed by Codex at
Khương's request, separately from the M3.2/M3.4 run operators. It replays the
M3.1 seal, verifies the accepted M3.5 comparison and audits both unchanged runs.

## Verified results

| Check | QARF M3.2 | QPAF M3.4 |
| --- | ---: | ---: |
| Receipt outputs rehashed | 16 | 16 |
| First-pass checks replayed | 30 PASS | 39 PASS |
| Persisted training steps checked | 1,000 / 20 epochs | 1,000 / 20 epochs |
| Fresh-process validation queries | 171 | 171 |
| Candidate scores reproduced | 82,255 | 82,255 |
| Maximum absolute score difference | 0 | 0 |
| Maximum absolute weight difference | 0 | 0 |
| Ranking disagreements | 0 | 0 |
| Maximum metric difference | 0 | 0 |
| Recomputed validation nDCG@10 | 0.7521473770883798 | 0.8662796720664044 |

Both best and last checkpoints have finite persisted model/optimizer tensors;
all checked epoch/step losses, gradient norms and counters are finite. Individual
gradient tensors from every historical step are not persisted, so the audit
does not claim to have rechecked those tensors. The trainer's finite guards and
the persisted step gradient norms remain separate evidence.

Each replay uses a new interpreter. The record includes worker PID, live process
ancestry and source hashes. This supports Windows virtualenv launchers, which
can sit between the audit and the actual Python worker. The evaluator/model are
loaded from this checkout, independently of other editable installations.

Numerical runtime matches both authorizations: Python 3.13.7, Torch 2.11.0+cpu,
NumPy 2.5.4, pandas 3.0.6 and PyArrow 26.0.0; CPU float64, one Torch thread.
The audit trains nothing, never deserializes test qrels and preserves the old
run/config/prediction/checkpoint bytes.

## Resource finding

Recorded CPU telemetry satisfies the existing authorized 3,600-second run
limit. QARF records wall 75.413 s / peak RSS 756.789 MB; QPAF 75.978 s /
753.770 MB. These are historical whole-run/phase values, not new per-query
inference measurements.

The frozen operational contract requires 20 warm-ups, at least 1,000 label-free
measured queries, median added fusion latency <=10 ms and learned-fusion CUDA
allocation <1.50 GiB. CPU phase telemetry cannot certify these latency/CUDA gates.
The two pilots contain only 970 development queries. M3.6 therefore remains
`BLOCKED` overall, rather than treating zero CUDA allocation on CPU as PASS.

## GPU protocol review package

At the user's explicit choice, prepare first and review before running GPU:

- [Human-readable protocol review](gpu_protocol_review/REVIEW.md).
- [Proposed fixed workload](gpu_protocol_review/gpu_workload.json): 20 warm-ups
  and 1,122 measured distinct IDs, selected by label-free SHA-256 order.
- [Machine-readable draft plan](gpu_protocol_review/gpu_review_plan.json).
- [Package hashes](gpu_protocol_review/package_hashes.json).

The workload includes 172 held-out ID records; text/score use for benchmarking
still needs review, with no labels, fitting or model selection. Other decisions
are the full-online-fusion interpretation of 10 ms, page-level scope, repeated
passes, and proposed A10/runtime/budget. The package is protocol preparation,
not execution-ready: GPU executor, immutable image, exact command/commit,
complete cost bound and authorization are still required. No GPU job was run.

## Literature basis and claim boundary

[Literature and methodology in Vietnamese](literature_and_methodology_vi.md)
maps verified primary sources to each decision, distinguishes project thresholds
from benchmarking guidance, and identifies analogies rather than claiming an
exact published QPAF implementation or novelty. The deep-search output was
checked against original papers and official documentation before adoption.

The two checkpoints were selected on the same validation split used for M3.5.
This one-seed development comparison is not a confirmation/robustness result.
The baseline matrix belongs to M4. GPU measurements and G2 remain pending.

## Reproduce the read-only review

Restore the M3.1 inputs according to the existing
[handoff](../../../docs/GUILDLINE_OVERVIEWS_PROPOSAL/M3_1_HANDOFF.md), preserving
manifest SHA-256 `0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893`,
and use the exact numerical runtime above:

```powershell
python -X utf8 scripts/audit_m36_integrity.py
```

The default prints JSON. `--output <new-path>` writes a create-once review;
existing outputs are refused. The sealed payload stays local and excluded from
Git. [`validation_receipt.json`](validation_receipt.json) records software tests,
review scope, diagnostic corrections and preservation checks.
