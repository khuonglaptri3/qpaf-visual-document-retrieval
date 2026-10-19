# M2.6 — Full ViDoSeek OCR and page hashes

## Intent and authority

Implement and execute the user's M2.6 assignment from
`docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx`,
Milestones row 31: complete OCR bundle with page hashes and explicit failures.
Work on `feature/M2.6-full-ocr-page-hashes`, based on develop `6cb2e88`.
The user explicitly requested implementation, execution, results and saved paths.

## Inputs and unchanged contracts

- Active corpus: 292 ViDoSeek PDFs, 5,385 canonical pages from M1.6-002.
- Verify M2.1-002 source bytes and train/validation/test IDs (799/171/172).
  Reuse M2.5's read-only split verifier. Do not use relevance labels for OCR.
- Load policy through M2.3-002 handover and `load_frozen_policy`; exact SHA
  `c0fcf0b3b13b27070716179d75545ba33ae406cc99a74902737bcf2dad19c4b8`.
- PDFium 4.30.0, Tesseract 5.3.0, pinned English traineddata, 300 DPI,
  OEM 3 / PSM 3, two OCR workers, one thread per subprocess, 15-second OCR
  timeout, 40 million pixels, four CPU cores and 4,096 MiB per container.
- M2.4's dataset expects score rows produced later by M2.8. This task preserves
  its page namespace and supplies shared preprocessing identities; it does not
  fabricate scores, evaluate retrieval, or run learned training.

## Architecture

Use a dedicated M2.6 config, preflight, page engine, bundle verifier and CLI.
Keep M2.3 calibration files and immutable evidence unchanged. Execute in a
single CPU-only Modal container with at most two OCR subprocesses. Render and
extract geometry on the main thread because PDFium is not thread-safe; overlap
that work with the two external OCR jobs using a bounded pending queue.

Upload the verified input schedule, policy and source to a dedicated Modal
Volume. The worker fetches the exact M2.1-pinned public archive, verifies its
758,769,613 bytes and SHA-256, and verifies all extracted PDF identities before
OCR. This avoids stalled large-file PUTs on the local network without changing
input bytes or the OCR operating configuration. Each canonical run is
create-once. Persist terminal per-page records and raw outputs, and commit
progress with no open PDF/Volume file handles. Resume downloads by hash;
never silently rerun a completed OCR attempt. Failed execution retains evidence.
Lossless PNG compression level 1 changes storage encoding, not image pixels.

## Page output

Keep canonical page/document ID and page number, PDF hash, native text/hash,
rendered image path/hash/dimensions, geometry, raw OCR TXT/TSV/stderr,
raw OCR text hash, final resolved text/hash, policy hash, extraction status,
technical failure/reason/warnings and timings. Reuse M2.3 `run_ocr`,
`extract_native_geometry`, `tsv_words`, `resolve_page`, and failure-cap semantics.
Rendering/native/geometry/TSV/engine failures remain explicit. Successful
`NO_TEXT_DETECTED` keeps the visual page and is not a technical failure.

## Verification and publication

One terminal record per all 5,385 scheduled IDs, no duplicates/orphans; preserve
document/page identities and PDF hashes. Recompute every recorded file and text
hash locally after download, validate policy/config/source identity, re-resolve
text from saved native/TSV/OCR inputs, and enforce the 1% technical-failure cap
over all scheduled pages. The historical M1.6 content hashes describe 72-DPI
pixels: retain them as source provenance, never compare them to 300-DPI PNG bytes.

Save run inputs/provenance and downloaded outputs in `results/m2.6/<RUN-ID>/`.
Export `resolved_pages.json`, `page_hashes.csv`, `failures.json`, `summary.json`,
`hashes.json`, `handover.json`, and local `verification.json` with portable paths.
Publish a compact immutable `evidence/revisions/m2.6-001/` receipt and human-readable
run report. Large images/raw payloads stay local and in the named Modal Volume;
portable text, hashes and receipts can be tracked. An incomplete or cap-exceeding
run cannot claim M2.6 completion. FROZEN policy and technical success do not
certify corpus OCR accuracy.

## Checks

Test failure accounting, hash tampering, missing/duplicate records, path escapes,
raw-vs-normalized OCR hashes, blank-page preservation, frozen config validation,
page namespace, artifact completeness and policy replay. Run the existing M2.3,
M2.4/M2.5-compatible checks and project unittest discovery. Record pre-existing
environment failures separately. Inspect actual full-run counters and local hashes
before publishing completion.
