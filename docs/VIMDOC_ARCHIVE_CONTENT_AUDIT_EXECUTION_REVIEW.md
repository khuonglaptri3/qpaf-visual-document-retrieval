# ViMDoc archive content audit v1 — local preparation review

Prepared: 2026-09-10. Status: `PREPARED_LOCAL_REVIEW_EXECUTION_CLOSED`.

## Outcome

The package for a future read-only source-archive audit is implemented and locally testable. It is not approved to execute: `execution_authorized=false`, approved invocations/time/retries are all zero, and the current Modal command must refuse before an attempt directory is created. This preparation did not contact Modal, open the 17.5-GB archive, run OCR, extract retriever scores, use a GPU, or train a model.

The audit has one scientific purpose: determine whether the 6,267 assets that share extension-stripped page IDs are safe byte-identical aliases or conflicting images. It reads only `ViMDoc_pages.tar.gz`; it does not read query text, qrels or the query Parquet.

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

The Modal pricing snapshot checked 2026-09-10 lists `$0.0000131/core-second` and `$0.00000222/GiB-second`. At exactly the requested reservation for six hours, the arithmetic ceiling is `(1 × 0.0000131 + 4 × 0.00000222) × 21,600 = $0.474768`. The review budget is `$0.60`. This is not a guaranteed bill because pricing and actual metered usage can change; `modal billing rates --json` must be checked before approval. A region or non-preemptible multiplier is not authorized.

## Execution and immutability contract

`vimdoc_archive_audit_modal.py` is separate from the historical `modal_app.py`. It attaches the existing Volume with `create_if_missing=false`, includes no `gpu=`, no Secret, no `.remote()` call and no local entrypoint. Importing or testing the package cannot invoke Modal.

The future function first verifies exact config/source hashes, actor, source commit, timeout, one approved invocation and zero retries. It verifies input/output paths and free space before creating output. The create-once output is `/vol/audits/vimdoc/vimdoc_archive_content_audit_v1`; its `_ATTEMPTED.json` is committed before scanning. Therefore a failure, timeout, interruption or platform reschedule leaves a consumed attempt, and any later start refuses because the output already exists.

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

The currently resolved config SHA-256 is `a5d12b2a74ca14af24eb93f9a01b0bbc45dc1441289547ad14b12744cbf6bce8`. The following command shape is documented for review only and **must not be run now**:

```powershell
modal run vimdoc_archive_audit_modal.py::audit_vimdoc_archive --config-sha256 <APPROVED_CONFIG_SHA256> --actor <APPROVED_ACTOR> --source-commit <CLEAN_APPROVAL_COMMIT>
```

There is deliberately no executable live command yet. A later authorization amendment must bind the clean commit, actor, approved config hash, refreshed pricing and exactly one invocation with the same CPU/memory/timeout and zero retries. The approved config will be a separately preserved snapshot rather than a silent rewrite of this closed preparation record.

## Stop conditions and interpretation

Stop on any hash/count/path/source mismatch; unsafe or duplicate tar member path; malformed page ID; different-content collision; evidence-size breach; existing output; timeout/interruption; or missing success marker. Do not rename conflicting pages, prefer an image extension, delete an asset, retry, or proceed to OCR.

A PASS establishes only a stable page inventory suitable for preparing OCR. It does not validate OCR quality, score extraction, candidate coverage, QARF/QPAF training or QPAF improvement. A collision failure requires a new data-protocol review. A clean PASS permits the next preparation step: OCR runtime calibration and a bounded OCR execution proposal.
