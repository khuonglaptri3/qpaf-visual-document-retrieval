# M2.6 — Full OCR outputs

M2.6 processes all 292 ViDoSeek PDFs / 5,385 canonical pages using the frozen
M2.3 policy. The exact run ID, measured result and verification receipt are
recorded in the [run report](../../docs/superpowers/reports/2026-10-19-m26-full-ocr.md).

## Saved files

Each run is stored in `results/m2.6/<RUN-ID>/`:

| Path | Contents |
|---|---|
| `input_manifest.json` | Verified corpus, canonical scheduled pages, source PDF hashes and frozen splits |
| `resolved_config.json`, `source.json`, `source_snapshot.zip` | Exact run configuration and implementation provenance |
| `ocr_policy_frozen.toml` | Exact frozen M2.3 operating policy |
| `execution.json` | Modal app, function-call ID and durable Volume location |
| `output/resolved_pages.json` | Final text, canonical IDs, extraction states, warnings, failures and artifact paths |
| `output/page_hashes.csv` | Page/PDF/image/native/OCR/final-text/policy SHA-256 values |
| `output/failures.json` | Explicit technical failures; successful empty OCR is kept separately in page states |
| `output/hashes.json` | Complete file SHA-256 and size manifest |
| `output/handover.json` | Text/namespace/policy identities for M2.8 and the M2.4 shared-input contract |
| `output/environment.json`, `output/resources.json`, `output/summary.json` | Actual engine identity, measured resources and counters |
| `output/pages/<PAGE-ID>/` | `native.txt`, `geometry.json`, `image.png`, `ocr.txt`, `ocr.tsv`, `ocr.stderr.txt`, `text.txt`, `record.json` |
| `output/archives/<DOCUMENT-ID>.zip` | Portable per-document raw bundles |
| `verification.json` | Independent local full-corpus, hash, CSV, runtime and policy-replay checks |

Large page payloads, archives and source snapshot ZIPs are retained locally and
in Modal Volume `qpaf-m26-full-ocr`; Git retains the portable manifests, text and
receipts. Original PDFs remain under `data/raw/vidoseek-e91a92b/pdfs/pdf/`.
The Volume path is `/runs/<RUN-ID>/` (mounted at `/m26/runs/<RUN-ID>/`).

## Commands

Use the workspace virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/run_m26_full_ocr.py --prepare-only
.\.venv\Scripts\python.exe scripts/run_m26_full_ocr.py --execute-prepared results/m2.6/<RUN-ID>
.\.venv\Scripts\python.exe scripts/run_m26_full_ocr.py --status results/m2.6/<RUN-ID>
.\.venv\Scripts\python.exe scripts/run_m26_full_ocr.py --collect results/m2.6/<RUN-ID>
.\.venv\Scripts\python.exe scripts/run_m26_full_ocr.py --verify results/m2.6/<RUN-ID>
```

Preparation does not execute OCR. Submitted attempts are create-once. Collection
resumes verified downloads and uses atomic extraction. If a worker terminates
before final manifests exist, collection saves `partial-output/` and
`partial_collection.json` with `PARTIAL_NOT_COMPLETE`; it never creates a full
verification receipt for an incomplete run.

M2.6 creates OCR inputs. Retriever caches belong to M2.8 and learned training to
later milestones. Technical completion does not certify corpus OCR accuracy.
