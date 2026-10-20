# M2.8 real-data score cache

Measured status: **GPU COMPLETE / CACHE VERIFIED / BLOCKED_COVERAGE**.
Macro candidate recall is **0.999124343257443** (1,141/1,142), with one
uncovered **train** query. Validation (171) and test (172) both have full coverage.
The zero-uncovered acceptance gate is not met; this is not learned-pilot
readiness. The frozen cache is retained for independent review.

Full-corpus GPU run:
`RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01`.

The authoritative final status is the run's `bundle/handover.json`, after
collection, candidate freeze, coverage and independent checksum/numeric replay.
Prepared-only folders are not completed cache runs.

The run contains 549,689 candidate rows (386–571/query), 685,200 channel top-list
rows and 18,449,010 full-corpus scores. Actual NVIDIA A10 worker wall time was
5,490.35s, with no neural CPU fallback or synthetic research output.

See the [measured report](../../docs/superpowers/reports/2026-10-20-m28-score-cache.md)
and [immutable evidence](../../evidence/revisions/m2.8-001/README.md).

| Artifact | Purpose |
|---|---|
| `resolved_config.json`, `input_manifest.json`, `source.json`, `source_snapshot.zip` | Pinned scientific inputs and exact GPU implementation |
| `execution.json` | Modal app/call ID, GPU request and durable Volume location |
| `queries.json`, `split_ids.json` | Label-free query text and frozen split IDs |
| `remote/<channel>/scores.npy` | Full 1,142 x 5,385 raw score arrays |
| `remote/*/parity.json`, `remote/environment.json`, `remote/resources.json` | GPU/reference/resource evidence |
| `remote/portable_manifest.json`, `collection.json` | All collected file sizes/checksums |
| `bundle/raw_scores.parquet` | Five-column M2.4/M2.5 shared trainer input |
| `bundle/normalized_scores.parquet` | Independently auditable union min-max values |
| `bundle/channel_top_lists.parquet`, `bundle/candidate_set.parquet` | Label-free top-200/channel and deterministic union |
| `bundle/candidate_freeze.json` | Pre-qrels candidate identities/counts/hashes |
| `bundle/qrels_development.json`, `bundle/qrels_test_sealed.json` | Separate page labels; test used only for frozen candidate coverage |
| `bundle/queries.json`, `bundle/split_ids.json`, `bundle/splits/*_ids.txt` | Exact portable inputs for M2.4, with frozen role hashes |
| `bundle/coverage_report.json`, `bundle/candidate_verification.json`, `bundle/handover.json` | Final coverage/integrity/loader evidence |
| `bundle/hashes.json` | Exact byte manifest for the complete portable handover |
| `uncovered_diagnosis.json`, `artifact_review.json` | Train-only failure diagnosis and fresh independent artifact review |
| `closure_verification.json`, `cloud_closure_verification.json` | Read-only replay and exact cloud upload/readback evidence |

Commands from repository root:

```powershell
./.venv/Scripts/python.exe scripts/run_m28_cache.py --collect results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python scripts/run_m28_cache.py --finalize results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python scripts/run_m28_cache.py --verify results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python -m unittest discover -s tests -p 'test_m28*.py' -v
```

`--status` and resume checks recover a local Modal result-deserialization error
only through a committed terminal JSON summary with matching run/config/source/
input identity and a timestamp newer than the latest invocation. Timeouts still
mean running; unrelated errors propagate. This recovered the existing Windows
Torch DLL issue without rerunning the completed GPU job.

The existing `.venv` has the Modal client; base Python has NumPy/Pandas/PyArrow
for local closure. Its separate existing Torch DLL issue is irrelevant to the
GPU inference runtime. Large arrays/Parquet/embeddings stay in local storage and
the Modal Volume; Git retains portable reports/manifests/receipts.

OCR review cleanup: `verification/ocr-review-html-removal.json` records all
10 exported HTML files removed following explicit user confirmation. Both
source/evidence templates and the OCR scientific inputs are preserved.
