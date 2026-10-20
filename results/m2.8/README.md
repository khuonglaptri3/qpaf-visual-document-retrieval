# M2.8 real-data score cache

Current full-corpus GPU run:
`RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01`.

The authoritative final status is the run's `bundle/handover.json`, after
collection, candidate freeze, coverage and independent checksum/numeric replay.
Prepared-only folders are not completed cache runs.

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
| `bundle/coverage_report.json`, `bundle/candidate_verification.json`, `bundle/handover.json` | Final coverage/integrity/loader evidence |

Commands from repository root:

```powershell
./.venv/Scripts/python.exe scripts/run_m28_cache.py --collect results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python scripts/run_m28_cache.py --finalize results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python scripts/run_m28_cache.py --verify results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01
python -m unittest discover -s tests -p 'test_m28*.py' -v
```

The existing `.venv` has the Modal client; base Python has NumPy/Pandas/PyArrow
for local closure. Its separate existing Torch DLL issue is irrelevant to the
GPU inference runtime. Large arrays/Parquet/embeddings stay in local storage and
the Modal Volume; Git retains portable reports/manifests/receipts.

OCR review cleanup: `verification/ocr-review-html-removal.json` records all
10 exported HTML files removed following explicit user confirmation. Both
source/evidence templates and the OCR scientific inputs are preserved.
