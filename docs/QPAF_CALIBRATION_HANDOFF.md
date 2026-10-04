# QPAF: prepared CPU calibration handoff

Updated on 2026-09-06. **Calibration completed and passed review; the one attempt is consumed. Do not run the launcher again.** See [the verified result and proposed next step](QPAF_CALIBRATION_REVIEW_AND_NEXT_STEP.md). The preparation details and command below are historical records.
This calibration measures runtime using synthetic relevance. It cannot establish a QPAF retrieval improvement.

## Prepared checkout and verified evidence

- Execution directory: `C:\Users\HP\.codex\tmp\qpaf-calibration-b252080`
- Detached commit: `b252080d4ea32ea7b5b11450b54a7cb58f214990`
- Required parent: `9821d100a4d64d73e8772f48f68f30388f851c06`
- The repository's own calibration approval guard passed: exact parent, seven-file approval allowlist, clean tracked checkout, protocol, and CPU-thread conditions.
- The input preflight passed for 6,149,670 rows, 1,142 queries, 5,385 pages per query, and coverage 1.0. It verified byte hashes, Parquet schema/shape, source contracts, and the pinned integrity review. Semantic integrity is inherited from that hash-pinned review; this preparation did not recompute every original semantic check.
- Retrieval-score payload: 248,445,561 bytes; SHA-256 `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b`.
- Protocol SHA-256 under its UTF-8/LF convention: `8d37e6c4dbe46146e9f2d5d3da439a2c72f4e06f3d9c8ce33511484fceccbe34`.
- Protocol, safeguard, and sharded-wrapper tests: `35 passed in 13.94s`. These tests use fixtures, not a live full-page calibration.
- At the original preparation handoff, no calibration attempt existed. The later human invocation completed; both the attempt marker and PASS manifest now exist in both checkouts. Zero attempts remain.

Local evidence: [preflight JSON](../runs/calibration_preparation_20260906/preflight.json) and [test output](../runs/calibration_preparation_20260906/targeted_tests.txt).

The original branch and existing user files were preserved. The prepared checkout contains a separate copy of the required retrieval-score payload. No source, protocol, threshold, or authorization flag was changed; no commit or push was made.

## Historical human invocation — consumed; do not repeat

The existing approval explicitly says `execution_actor: human` and permits one invocation with no retry. Its source is `authorization.full_page_calibration_execution` in [the protocol](../configs/vidoseek_p1_02r_oracle_w7_v1.yaml), lines 146–171. The launcher below contains the protocol's exact approved command and changes to the verified checkout first. Do not use the original checkout to run the calibration.

The completed human invocation used this CMD command. It is retained for provenance only; do not run it again:

```bat
call "C:\Users\HP\OneDrive\tlcn\runs\calibration_preparation_20260906\RUN_CALIBRATION_ONCE.cmd"
```

The [launcher](../runs/calibration_preparation_20260906/RUN_CALIBRATION_ONCE.cmd) starts the live calibration immediately when invoked. It was inspected and checked against the protocol without being executed. It also refuses to start if a calibration attempt marker already exists in the original or prepared checkout.

Limits: query index 570; all 5,385 pages; 100 bootstrap resamples; one CPU worker and one thread per numerical library; synthetic relevance only. The worker has a 2,700-second timeout. Input preflight and process startup add time outside that worker timeout. No GPU is used.

After the command returns, run this separate line to read its exit code:

```bat
echo %ERRORLEVEL%
```

Expect `0` and a printed path ending in `run_manifest.json` on success. A zero exit code alone is not sufficient: the manifest must also pass the review below. On failure, stop and preserve the terminal output and any marker. Do not run the command again, delete its marker, or create another checkout to repeat the attempt.

## Reviewed outputs

Output directory:

```text
C:\Users\HP\.codex\tmp\qpaf-calibration-b252080\artifacts\vidoseek_p1_02r_oracle_w7_v1_full_page_calibration
```

- `_ATTEMPTED.json`: create-once evidence that the permitted attempt was consumed, even if later work fails.
- `run_manifest.json`: created on success, containing status, timing, source/protocol identity, environment, limits, and non-scientific boundaries.

The completed review verified the items below; its result is saved in rtifacts/vidoseek_p1_02r_full_page_calibration_review.json:

1. `status=PASS`, `classification=engineering_full_page_calibration_not_result`, source commit and protocol hash match this handoff, and the manifest's attempt-marker hash matches the actual marker bytes.
2. Query index 570, query ID matching candidate-audit order, 5,385 pages, 100 resamples, one worker/thread, and the 2,700-second worker limit match the approved contract.
3. Timing is finite and positive; actual-relevance loading, scientific oracle analysis, full W7, Modal/GPU, and learned-QPAF execution are all false.
4. Record the result and consumed authorization through a separate precise evidence update. Do not overwrite immutable execution evidence.

## What follows

A successful calibration permits a runtime/resource review. It does not itself authorize W7. The next concrete deliverable is a separately reviewed W7 execution amendment with the measured runtime, resource limits, exact checkout, checkpoint/resume conditions, and output contract.

W7 then measures Global, query-level QARF, and page-level QPAF on actual relevance labels under the separately authorized post-hoc protocol. The current QPAF-minus-QARF discovery gates are: below 0.01 mean nDCG@10 means stop learned QPAF; at least 0.03 with a positive 95% CI lower bound and top-5%-gain share below 0.90 permits separate W66 review; otherwise revise or stop after review. A positive oracle result shows headroom, not learned-model improvement.

Frozen P1-02 remains BLOCKED. W66, learned training, and external validation have not been executed or authorized by this preparation.
