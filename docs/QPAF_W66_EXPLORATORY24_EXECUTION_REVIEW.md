# Exploratory-24 W66 sensitivity: preparation and execution review

**PREPARED; RESOURCE REVIEW AND EXECUTION REMAIN CLOSED.** This document records a separately versioned W66 sensitivity proposal on the same 24 queries used by the completed exploratory-24 W7 study. It does not authorize execution, consume an invocation, produce a W66 result, execute formal P1-03, or change the frozen P1-02 status.

## Why this is review-eligible

The independently reviewed exploratory-24 W7 result reports mean QPAF-minus-QARF nDCG@10 `0.05001054981241935`, bootstrap CI95 `[0.008343883145752686, 0.10192128410987107]`, and top-5% gain share `0.6663150804360639`. These values clear the predeclared exploratory signals for considering W66. They remain subset evidence and cannot satisfy the formal Phase 1 dependency or gate.

## Frozen scientific contract

| Item | Prepared contract |
| --- | --- |
| Classification | Exploratory W66 sensitivity on the frozen exploratory-24 subset; not formal P1-03 |
| Queries | The same 24 ordered ViDoSeek query IDs as W7; no reselection |
| Query-list SHA-256 | `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b` |
| Candidates | All 5,385 pages/query; 129,240 query-page pairs |
| Inputs | Existing normalized BM25, dense, and visual scores; byte SHA-256 `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b` |
| Grid | 66 unique non-negative simplex profiles at 0.1 increments |
| Profile-list SHA-256 | `c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973` |
| Global | One W66 profile selected across only these same 24 queries |
| QARF | Exhaustive query-local selection across W66 |
| QPAF | QARF-initialized, fixed-order coordinate ascent with at most two sweeps |
| Tie-breaks | Ascending page ID; profile metrics ordered by nDCG@10, Recall@3, then MRR@10 |
| Bootstrap | Query bootstrap; 10,000 resamples; seed 20260820; percentile CI95 |
| Device | Local CPU only; one worker and one thread per numeric library |
| Attempts | Zero authorized; zero automatic retries |
| Time budget | Zero seconds approved; separate resource review required |
| Output | `runs/vidoseek_w66_exploratory24_v1/`; it must not exist before a future approved attempt |

The W7 run took 8,700.394 seconds. W66 has 66 profiles versus 7 in W7, and each candidate search considers 65 alternative profiles versus 6. The ratios `66/7` and `65/6` describe increased search work only; they are not runtime estimates. No safe timeout or invocation budget has been approved.

## Guarded implementation

- [Runner](../scripts/run_vidoseek_exploratory24_w66.py) validates Git provenance, source and evidence hashes, package versions, the frozen query list, the W66 grid, and the parent W7 continuation evidence.
- [Closed config](../configs/vidoseek_w66_exploratory24_v1.json) pins the prepared checkout and keeps resource and execution authorization false.
- [Focused tests](../tests/test_vidoseek_exploratory24_w66.py) cover exact synthetic W66 equivalence, immutable checkpoint reuse, tamper refusal, closed authorization, failure evidence, and no retry.
- Read-only preflight validates IDs and metadata without loading relevance or running the W66 oracle.
- The run command checks authorization before validation, input access, or any output write.

The worker uses two passes. First, it hash-seals metrics for all 66 profiles for every query and freezes one shared Global profile only after all 24 Global checkpoints validate. Second, it creates one query-level QARF/QPAF checkpoint per query. Every checkpoint is bound to the exact run identity, input-query hash, and shared Global selection.

Missing checkpoints may be created only inside an authorized attempt. Existing checkpoints are reusable only after exact envelope, identity, content-hash, input-hash, and inventory checks. Any mismatch fails closed. The normal command refuses any existing output directory; recovery requires a separately reviewed amendment and approval.

Only a complete manifest followed by independent hash, ranking, metric, and bootstrap review permits reporting a result. Partial metrics cannot be reported as complete.

## Commands and approval boundary

The read-only command is:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe scripts\run_vidoseek_exploratory24_w66.py preflight
```

The following command is documented for future review but is **not authorized**:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
C:\Python313\python.exe scripts\run_vidoseek_exploratory24_w66.py run --actor codex
```

A future approval must set a reviewed positive timeout, exactly one invocation, the execution actor, approval text, and timestamp in a clean direct-child commit with an exact changed-path allowlist. The live preflight must then pass again. Preparation does not authorize that amendment or command.

This study can compare W7 and W66 only on the same 24-query subset. It cannot issue the formal P1-03 `proceed_qpaf`, `revise`, or `stop` decision because P1-02 remains blocked. Training, learned QPAF, CARF, Modal/GPU, ViDoRe, and frozen P1-02 changes remain outside scope.
