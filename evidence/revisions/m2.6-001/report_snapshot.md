# M2.6 — Full OCR execution report

Status: **COMPLETE / VERIFIED_FULL_OCR_BUNDLE**.

All **292 PDFs / 5,385 canonical pages** have terminal records and independently
verified local artifacts. There are **1 technical failures
(0.0186%)**, within the frozen 1% cap. Failed pages remain
in the corpus and the explicit failure list. Technical completion does not
certify OCR accuracy.

Owner: Khương. Authority: `POAI_Milestone_Group01_Hoan_Chinh.xlsx`, Milestones
row 31 — run full OCR and verify page-level hashes.

Branch: `feature/M2.6-full-ocr-page-hashes`.
Processing source commit: `9976150de48a6b20cafc36ffc651d8353f2a285b` (develop base `6cb2e88`).
Run: `RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01`.
Worker completed: `2026-10-19T15:21:50.253596+00:00`.

## Measured result

| Measure | Result |
|---|---:|
| Scheduled and retained pages | 5,385 |
| Documents | 292 |
| Technical failures | 1 |
| Successful frozen-policy replays | 5,384 |
| Failed-page fallback replays | 1 |
| Declared page artifacts verified | 37,695 |
| Total manifest files verified | 43,384 |
| Total manifest bytes verified, including archive copies | 17,488,277,993 |
| OCR returned no detected words | 63 |
| Empty final text pages retained | 19 |
| Pages with quality warnings | 700 |
| Worker wall time through archive creation | 4846.42 seconds |
| Peak Python and children RSS during extraction | 1431.91 MiB |
| Per-document raw archive bytes | 8,729,397,596 |

Extraction states:

| State | Pages |
|---|---:|
| NATIVE_PLUS_OCR | 3,428 |
| NATIVE_TEXT_USED | 1,804 |
| NO_TEXT_DETECTED | 19 |
| OCR_TEXT_USED | 133 |
| OCR_TIMEOUT | 1 |

Final text sources:

| Source | Pages |
|---|---:|
| native | 1,805 |
| native+ocr | 3,428 |
| ocr | 152 |

Quality warning counts (one page can have several):

| Warning | Occurrences |
|---|---:|
| low_ocr_confidence | 307 |
| native_quality_rejected | 18 |
| no_text_requires_visual_channel | 19 |
| suspected_native_encoding | 364 |

## Failures and interpretation

- `038c7d9e4cc19a5b729d9d2a7ca5b304e6756ea1_page_0007`: OCR_TIMEOUT; text source `native`. ocr: Per-page or remaining wall-time cap exceeded

The frozen policy permits no retries. Retained native text and available raw
artifacts are included in each failure record. Empty OCR is a retained state,
not proof that an image has no text. The technical-failure denominator is all
5,385 scheduled pages; it is not an accuracy metric.

## Inherited milestones and runtime

M2.1/M2.5 frozen splits passed verification: 799 train / 171 validation / 172
test, with zero overlap. OCR consumes source pages without relevance labels.
All source PDFs and the 758,769,613-byte dataset archive passed SHA-256 checks
at pinned revision `e91a92ba5f38690696c7e66be5c5474b54c6e791`.

M2.3 native-preserving text fusion, geometry, TSV parsing, warnings and failure
semantics were reused unchanged: Tesseract 5.3.0 / eng, PDFium 4.30.0, 300 DPI,
OEM 3 / PSM 3, two OCR workers, one subprocess thread, CPU4, RAM4096 MiB,
40,000,000 pixels and a 15-second OCR timeout. All measured resource checks pass.

Frozen policy SHA-256:
`c0fcf0b3b13b27070716179d75545ba33ae406cc99a74902737bcf2dad19c4b8`.

M2.4 canonical page identities and M2.5 split isolation are preserved. The
handover supplies text, namespace and preprocessing identities to M2.8, which
will produce the shared `qpaf_score_rows_v1` scores and <=600-page candidate
unions consumed by M2.4. This task produces no retrieval scores or training.

## Verification and provenance

Local collection recomputed every declared file hash, checked the exact
canonical corpus/page sequences, validated the page-hash CSV against all page
records, replayed the frozen text policy and failed-page fallbacks, and checked
the measured runtime/resource evidence and handover identities.

Manifest SHA-256: `e3b92c379a2021d8a3a4361073deaad096542d2cdef03b3ef034610b44c0cfe2`.

Preprocessing identity SHA-256:
`6bd09e6f7615cca14a20f7fa23e29d67d3589f4d18cdb8c51b8e870912b41213`.

An independent read-only code review found no outstanding material findings
after fixes. It also verified 143 source-snapshot records and exact config and
policy bytes. Review and source-snapshot receipts are separate from the full
bundle receipt; neither is a human milestone sign-off.

54 targeted M2.6/M2.3/M2.5 tests passed. Project-wide discovery has the same
pre-existing 1 failure, 39 errors and 3 skips as develop (227 baseline tests;
252 with this work). Missing pandas/pytest and Windows PyTorch `shm.dll`
loading failures remain. There are no new project-suite failures.
All 54 targeted checks also passed in a fresh run after resuming collection;
the separate resumed-checks receipt records its command and exact log hash.

## Saved files

Workspace root: `C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project`.

Full run directory: `results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01/`.

| File or directory | Purpose |
|---|---|
| `verification.json` | Independent full-bundle local verification receipt |
| `output/resolved_pages.json` | Final text and complete per-page terminal records |
| `output/page_hashes.csv` | Per-page source/PDF/image/native/OCR/text/policy hashes |
| `output/failures.json` | Explicit retained technical failures |
| `output/hashes.json` | Exact file checksums and sizes |
| `output/handover.json` | M2.8/M2.4 namespace and preprocessing identities |
| `output/summary.json`, `resources.json`, `environment.json` | Measured counts, resources and runtime |
| `output/pages/<PAGE-ID>/` | Native/final text, image, geometry, raw OCR TXT/TSV/stderr and record |
| `output/archives/<DOCUMENT-ID>.zip` | All 292 raw per-document bundles |
| `source.json`, `source_snapshot.zip`, `source_snapshot_verification.json` | Processing source and independent snapshot audit |
| `resolved_config.json`, `ocr_policy_frozen.toml`, `input_manifest.json` | Exact operating inputs |
| `collection_audit.json`, `collection_recovery.json`, `transport_*.py`, `operator_canonical_verify.py` | Local collection, transfer recovery and verifier diagnostics |

The [file index](../../../results/m2.6/README.md) provides commands and storage
details. [Immutable evidence](../../../evidence/revisions/m2.6-001/README.md)
contains compact receipts and this report. Software checks and code review are
saved under `results/m2.6/verification/`.

Large raw pages, ZIP archives and source snapshot remain locally and on Modal
Volume `qpaf-m26-full-ocr`, `/runs/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01/`.
All JSON text and hash manifests fit the portable Git size threshold and are retained directly; no compressed JSON recovery step is needed.
Historical 72-DPI `source_content_sha256` and the new 300-DPI image
SHA identify different representations and are retained separately.

## Execution recovery

An earlier preparation stalled during bulk PDF upload with SSL resets; no OCR
call was submitted. The successful run fetched the exact pinned public archive
in cloud and verified it and every PDF before OCR. No source data or OCR policy
changed. Completed immutable document bundles were prefetched during execution;
the canonical final worker manifest remained authoritative for collection and
local verification. The successful OCR run was not retried.

Overlapping operator downloads triggered two Windows `WinError 5` atomic-rename
failures after destination copies already existed. After all overlap processes
exited, the unmodified single collector extracted every declared page file.
That collector later ended during verification without a receipt or traceback;
its exit cause remains undetermined, and no matching Windows application error
was observed. All 43,384 declared files were confirmed present with correct sizes.

The unchanged canonical `verify_bundle` then ran in a separate process with
progress-only wrappers that call every original helper, crash logging and an
explicit exit receipt. It recomputed every canonical checksum and passed all
full-bundle checks with exit code 0. No OCR was resubmitted and no integrity
check was weakened. `collection_recovery.json` binds the transfer, interrupted
collection, successful verification and exact process-exit logs.
