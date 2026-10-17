# ViMDoc archive content audit v1 — local preparation review

Prepared: 2026-09-10; locally repaired and reclosed 2026-09-11. Status: `PREPARED_LOCAL_REVIEW_EXECUTION_CLOSED`.

## Outcome

The package for a future read-only source-archive audit is implemented and locally testable. It is not approved to execute: `execution_authorized=false`, approved invocations/time/retries are all zero, and the current Modal command must refuse before an attempt directory is created. This local repair did not contact Modal. The consumed Function invocation described below failed before opening the 17.5-GB archive or creating audit output; neither it nor this repair ran OCR, extracted retriever scores, used a GPU, or trained a model.

The audit has one scientific purpose: determine whether the 6,267 assets that share extension-stripped page IDs are safe byte-identical aliases or conflicting images. It reads only `ViMDoc_pages.tar.gz`; it does not read query text, qrels or the query Parquet.

## Consumed submissions and repairs

The approved config `baeb51bd5429a32443c64d4620928c75b06e65f722c33f24ec3c1a8f924d4013` was activated in commit `20b65c0b7e2d0733f94fc50025342563f751aaac`. Its recorded `modal run` command exited locally while importing this wrapper, before app submission or Function-call creation: on Windows, `str(Path("/root"))` produced `\root`, which `modal.Image.add_local_file` rejected as a non-absolute remote path. `run_audit` was never entered, no `_ATTEMPTED.json` was created by that control flow, and no archive, OCR, extraction, GPU or training work ran. The old authorization and command are non-reusable; no retry occurred.

The repaired wrapper kept Modal-facing `/root` and `/vol` values as literal POSIX strings and converted them to `Path` only inside the Linux Function body. A source-level regression test froze those two absolute strings, the Volume mount key and the absence of local Windows `Path` serialization.

The repaired config `f3eadaa97ff0df20f5e2ad288aed5cea920502321cd42b18cf2d687192950014` was activated in commit `6a0db676a8b5b43d14081463f835ec6b0fcb8abc`. Its sole approved command created remote Function `audit_vimdoc_archive`, then exited with `Source/input hash drift: artifacts/dataset_materialization_vimdoc.json`. The wrapper declared this receipt as a required hashed source but had not mounted it into the image. Source validation occurs before the archive path is opened, before the output directory is created and before `_ATTEMPTED.json` is written, so this control flow produced no archive scan or audit artifact. The Function invocation is nevertheless consumed; its authorization and command are non-reusable, and no retry occurred.

The current local-only repair adds exactly that receipt to the image at `/root/artifacts/dataset_materialization_vimdoc.json`. A regression test requires the local receipt constant and its absolute POSIX remote mount. This repair is execution-closed and does not authorize a Modal invocation.

## Frozen input and decision

- Dataset: `kaistdata/ViMDoc`, revision `25657f1fe0358f49147148ca89e231291ba42788`.
- Existing Volume: `qpaf-artifacts`; source archive path `/vol/datasets/vimdoc/25657f1fe0358f49147148ca89e231291ba42788/ViMDoc_pages.tar.gz`.
- Expected compressed archive SHA-256: `de569c8d4d499b8fac84d4d03a0ddb59054e30351dcb7b1e6da3d1945d2d2c71`.
- Expected historical size: 17,455,193,968 bytes. Size is supporting metadata; SHA-256 is authoritative.
- Expected inventory: 76,347 image assets, 70,080 page IDs, 6,267 extra aliases and 1,247 document IDs.
- PASS requires exactly zero same-page-ID/different-content collisions. Same-page-ID/same-content files become retained aliases; same-content/different-page-ID files remain distinct page identities.

The semantic rules are frozen in `configs/vimdoc_ocr_page_identity_v1.json`. The runner streams the compressed archive hash and each uncompressed image hash. It never extracts members to disk or decodes images.

## Resource and cost proposal

The separate app `qpaf-vimdoc-archive-audit-v1` uses one physical CPU core, 4,096 MiB memory, no GPU, no secret, no region constraint, no network requirement and no Python package installation. Timeout is 21,600 seconds (six hours), retries zero, evidence cap 128 MiB and required free Volume space 1 GiB. The timeout is an uncalibrated resource cap, not a runtime prediction.

The Modal pricing snapshot refreshed from the official pricing page on 2026-09-11 lists `$0.0000131/core-second` and `$0.00000222/GiB-second`. At exactly the requested reservation for six hours, the arithmetic ceiling is `(1 × 0.0000131 + 4 × 0.00000222) × 21,600 = $0.474768`. The review budget is `$0.60`. This is not a guaranteed bill because pricing and actual metered usage can change. Pricing must be refreshed again before approval; a region or non-preemptible multiplier is not authorized.

## Execution and immutability contract

`vimdoc_archive_audit_modal.py` is separate from the historical `modal_app.py`. It uses literal POSIX remote roots, mounts the materialization receipt at `/root/artifacts/dataset_materialization_vimdoc.json`, attaches the existing Volume with `create_if_missing=false`, includes no `gpu=`, no Secret, no `.remote()` call and no local entrypoint. Importing or testing the package cannot invoke a Function.

The future function first verifies exact config/source hashes, actor, source commit, timeout, one approved invocation and zero retries. A failure in that pre-output validation creates no audit directory or marker but still consumes the approved Function invocation. After validation, it verifies input/output paths and free space before creating the create-once output `/vol/audits/vimdoc/vimdoc_archive_content_audit_v1`; `_ATTEMPTED.json` is committed before scanning. Any later failure, timeout, interruption or platform reschedule leaves a consumed attempt, and a later start refuses because the output already exists.

Success evidence:

- `_ATTEMPTED.json`
- `source_snapshot/**`
- `asset_inventory.jsonl`
- `audit_summary.json`
- `canonical_pages.jsonl`
- `run_manifest.json`
- `_SUCCESS.json`

`asset_inventory.jsonl` records every tar path and uncompressed content hash. `canonical_pages.jsonl` records each canonical page and all aliases. The runner compares persisted JSONL hashes/counts with the in-memory audit, checks the 128-MiB output cap, snapshots all bound source files, and emits `_SUCCESS.json` only after those checks. Failures emit `_FAILED.json`, never success. The dataset archive is opened only for binary reads; evidence is written in the separate audit directory.

## Local verification and current command boundary

Safe local review command:

```powershell
C:\Python313\python.exe scripts/prepare_vimdoc_archive_content_audit.py
$env:PYTHONPATH = 'src'
C:\Python313\python.exe -m pytest tests/test_vimdoc_archive_content_audit.py tests/test_vimdoc_ocr_page_identity.py -q
```

The currently resolved closed config SHA-256 is `d68aa576a088081002d1e938e19a2c443ad8cd570c35c618173d54be26609253`. The following command shape is documented for review only and **must not be run now**:

```powershell
modal run vimdoc_archive_audit_modal.py::audit_vimdoc_archive --config-sha256 <APPROVED_CONFIG_SHA256> --actor <APPROVED_ACTOR> --source-commit <CLEAN_APPROVAL_COMMIT>
```

There is deliberately no executable live command yet. Neither the superseded `baeb51bd...` command nor the consumed `f3eadaa9...` command may be reused. A later authorization amendment must bind the repaired clean commit, actor, new approved config hash, refreshed pricing and exactly one invocation with the same CPU/memory/timeout and zero retries. The approved config will be a separately preserved snapshot rather than a silent rewrite of this closed preparation record.

## Stop conditions and interpretation

Stop on any hash/count/path/source mismatch; unsafe or duplicate tar member path; malformed page ID; different-content collision; evidence-size breach; existing output; timeout/interruption; or missing success marker. Do not rename conflicting pages, prefer an image extension, delete an asset, retry, or proceed to OCR.

A PASS establishes only a stable page inventory suitable for preparing OCR. It does not validate OCR quality, score extraction, candidate coverage, QARF/QPAF training or QPAF improvement. A collision failure requires a new data-protocol review. A clean PASS permits the next preparation step: OCR runtime calibration and a bounded OCR execution proposal.
