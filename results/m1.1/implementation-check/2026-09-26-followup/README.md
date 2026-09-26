# M1.1 continuation verification — 2026-09-26

**Software verification: PASS. Real Modal inference: NOT RUN. Independent
research review: PENDING.** No historical reference report was changed.

This directory records the continuation of the PDFium compatibility and review
fixes. Verification ran on Windows with Python 3.11.16, Modal 1.5.5 and PDFium
4.30.0. It does not verify the Linux GPU image or the full ViDoSeek corpus.

## Fixes verified

1. Evidence verification previously accepted an export with missing upstream
   metadata because it selected receipt entries from files still on disk. It now
   requires every metadata file selected by the receipt and export policy before
   checking hashes. Deleting each of 26 metadata files reproduced the issue;
   those cases now fail validation as intended. See
   [before](regression-before.log) and [after](regression-after.log).
2. The first persisted fixture failed with `PermissionError: [WinError 5]` while
   atomically replacing `status.json` inside this OneDrive workspace. A separate
   probe saw one failure in 100 workspace writes and none in 100 temporary-folder
   writes; the process causing the access denial was not identified. Atomic JSON
   writes now retry that specific Windows error up to five attempts, with at most
   1.5 seconds of backoff. Persistent failures still raise and preserve the old
   file. The regression exercises both temporary and persistent denial. See
   [original fixture failure](fixture-smoke.log),
   [filesystem probe](filesystem-probe.json), and
   [pre-fix regression](windows-lock-before.log).

## Final checks

Exact commands, UTC times and exit codes are in [checks-final.json](checks-final.json).
All seven final commands exited successfully.

| Check | Result | Evidence |
| --- | --- | --- |
| Full unittest suite | 44 run, 43 passed, 1 skipped | [tests-final.log](tests-final.log) |
| M1.1 subset in that suite | 29 passed, no skips | Same log |
| Actual PDF render/extract path | Passed with a generated two-page PDF | Same log |
| Persistent software fixture and local evaluator CLI | Passed | [fixture-smoke-final.log](fixture-smoke-final.log) |
| Compile source, scripts and tests | Passed | [compile-final.log](compile-final.log) |
| Construct Modal App without execution | Passed | [modal-sdk-final.log](modal-sdk-final.log) |
| Config overrides for GPU, Volume and paths | Passed dry-run | [dry-run-final.log](dry-run-final.log) |
| Installed dependency compatibility | 43 packages compatible | [dependencies-final.log](dependencies-final.log) |
| Tracked diff whitespace | Passed | [diff-final.log](diff-final.log) |

The skipped test requires unprivileged Windows symlink creation; the PDF test ran.
The initial [checks.json](checks.json) retains the failed fixture attempt and is
superseded by `checks-final.json` for final status. Expected failure logs are
reproduction evidence, not successful checks.

## Software fixture

[fixture_smoke.py](fixture_smoke.py) uses two synthetic queries and three text
pages, executes real BM25, and supplies synthetic dense/visual score caches. It
executes Oracle, verifies resume, exports and verifies evidence, then invokes
`scripts/evaluate_m11.py` as a subprocess. Query IDs, per-query metrics, summary
and Oracle decisions must match the stage pipeline byte for byte.

The portable reports are under
[software-fixture-final/exported-evidence](software-fixture-final/exported-evidence/).
Large-payload extensions remain subject to the repository ignore rules; rerun the
fixture to regenerate score arrays if copying this evidence from Git.

Reproduce with a **new** output directory:

```powershell
.venv/Scripts/python.exe results/m1.1/implementation-check/2026-09-26-followup/fixture_smoke.py --output results/m1.1/implementation-check/another-fixture
```

`source.json` records the verified implementation/config/test hashes and local
environment. `hashes.csv` covers the portable verification files and exported
fixture evidence; raw working directories and this manifest itself are excluded.

## Remaining acceptance

- Authenticate and execute the actual dataset/model pipeline on the owner's
  Modal account; check the resulting query table, statistics and provenance.
- Obtain review by another group member. The generated summary still records
  `independent_review=pending`; this continuation is not an independent review.
- Linux GPU runtime and CI matrix execution were not performed in this session.
