# M4.4 — Full deployable baseline evaluation (validation)

**Owner:** Tấn Phát. **Status:** both authorized runs `SUCCESS`, first-pass
verify `PASS`; independent review `PENDING` (M4.5, Thanh). Validation only:
171 ViDoSeek queries, single seed `20260820`. Test qrels were never opened.

- [`authorization.json`](authorization.json), SHA-256
  `8cfd641d0eab3e62f29dbad664a94c5b586b3eec5a75475b22fd690ce710140b`, approved
  2026-10-23T17:21:02Z. The approval text is the Research Lead's verbatim reply,
  recorded by Claude Code at their request. Source commit `2b0ab86`.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261023-0005`/`0006`
  (AUTHORIZED), `0007`/`0008` (STARTED), `0009`/`0010` (VERIFICATION_RECORDED).
- [`post_run_verification.json`](post_run_verification.json): pre-run checks and
  `scripts/run_m44_evaluation.py verify` for both runs.

| Run | Class | Wall time | Manifest SHA-256 |
| --- | --- | ---: | --- |
| `RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01` | `learned_evaluation` | 14.7 s | `aa2ab518…e4a7` |
| `RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01` | `oracle_upper_bound` | 267.5 s | `6d796a27…b5a2` |

## Inputs

M4.2 bundle manifest `4752eef3…6b86`. The seven Git-ignored payload files were
restored from byte-identical local sources and the M4.2 verifier returned `PASS`.
The M4.3 freeze record is `4015c74b…61cc`. All rows share the same candidate rows
(82,255 pages), min-max scores, binary page qrels and `qpaf.m24.evaluator`. Learned
QARF and the frozen QPAF were reloaded from their checkpoints and reproduce the
saved M3.2/M3.4 predictions exactly (difference `0.0`, tolerance `1e-7`).

## Table (validation, nDCG@10 primary)

**Deployable baselines.** Selection: highest validation mean nDCG@10, ties within `1e-12`.

| Rank | Method | nDCG@10 | R@1 | R@3 | MRR@10 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `train_fitted_static` [0.0, 0.1, 0.9] — **strongest (only co-strongest)** | 0.871414 | 0.736842 | 0.918129 | 0.833062 |
| 2 | `colqwen25` | 0.869296 | 0.736842 | 0.912281 | 0.830472 |
| 3 | `uniform_combsum` | 0.841254 | 0.695906 | 0.894737 | 0.797034 |
| 4 | `rrf_k60` | 0.829366 | 0.678363 | 0.877193 | 0.781651 |
| 5 | `bge_m3` | 0.763862 | 0.584795 | 0.795322 | 0.705518 |
| 6 | `learned_qarf`* | 0.752147 | 0.584795 | 0.783626 | 0.696888 |
| 7 | `bm25` | 0.725095 | 0.549708 | 0.736842 | 0.665314 |

**Proposed method (not eligible for selection).**

| Method | nDCG@10 | R@1 | R@3 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| `qpaf` frozen (M4.3)* | 0.866280 | 0.736842 | 0.906433 | 0.828279 |

\* Checkpoint selected on this validation split; optimistic.

**Oracle context (label-using upper bounds, never selectable).**

| Grid | Global | Per-query (oracle QARF) | Per-page (oracle QPAF) |
| --- | ---: | ---: | ---: |
| W7 | 0.869296 (profile [0, 0, 1]) | 0.911029 | 0.942870 |
| W66 | 0.871743 (profile [0, 0.3, 0.7]) | 0.911900 | 0.940125 |

## Single-seed exploratory paired statistics (QPAF − baseline, nDCG@10)

10,000 query-bootstrap resamples, seed `20260820`. This is not the three-seed test.

| Baseline | Mean delta | CI95 | W/T/L | Top-5% share |
| --- | ---: | --- | --- | ---: |
| `train_fitted_static` | −0.005134 | [−0.013457, +0.002783] | 3/161/7 | 1.000 |
| `colqwen25` | −0.003016 | [−0.007933, +0.000417] | 1/167/3 | 1.000 |
| `uniform_combsum` | +0.025026 | [−0.000713, +0.050405] | 31/122/18 | 0.444 |
| `rrf_k60` | +0.036914 | [+0.012234, +0.062588] | 32/123/16 | 0.443 |
| `bge_m3` | +0.102417 | [+0.065228, +0.141704] | 51/104/16 | 0.323 |
| `learned_qarf` | +0.114132 | [+0.077501, +0.152040] | 57/101/13 | 0.281 |
| `bm25` | +0.141184 | [+0.101564, +0.182060] | 63/97/11 | 0.267 |

The `learned_qarf` row reproduces the M3.5 comparison exactly.

## Reading and limits

- On validation, the frozen QPAF does **not** exceed the strongest deployable
  baseline (`train_fitted_static`) or ColQwen2.5 alone. Both deltas are small and
  negative, and their CIs include 0. Under `baseline_policy.md` §3.5, QPAF must
  beat every co-strongest baseline. This evidence is validation-only and
  single-seed, so it is input to the M4.5 audit and the M4.6 decision; it does
  not decide either.
- Learned QARF, the G2 comparator, ranks 6 of 7 deployable rows, so the G2
  margin was measured against a weak comparator.
- The per-page oracle is the frozen greedy two-sweep search, which starts from
  the per-query optimum. It is not monotone in grid size, which is why W66 ends
  slightly below W7.
- The oracle headroom over the frozen QPAF is +0.0738 (W66 per-page) and +0.0456
  (W66 per-query).

## Replay

With the M4.2 payload restored (`scripts/run_m44_evaluation.py restore-inputs`):

```powershell
.venv/Scripts/python.exe scripts/run_m44_evaluation.py verify --experiment MTH --run results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01 --expected-manifest-sha256 aa2ab51814c883b5552b1b45136c1f25dd7d9921a074891f4ae0397f4b03e4a7
.venv/Scripts/python.exe scripts/run_m44_evaluation.py verify --experiment ORC --run results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01 --expected-manifest-sha256 6d796a27537c191d5b39436cf6fcaffa9e58b4c01628d9558da6ba261739b5a2
```

MTH recomputes metrics, selection, table and paired statistics from
`predictions.csv.gz`. ORC re-scores the saved oracle predictions and reruns the
oracle (about 4.5 minutes).
