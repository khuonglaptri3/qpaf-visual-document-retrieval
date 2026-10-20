# M2.8 — Real ViDoSeek three-retriever cache

## Authorized scope

The user requested completion of M2.8 after deep research, real GPU execution on
Modal, removal of obsolete exported OCR review HTML, and a measured report in chat.
This implements the concrete M2.8 pipeline described and accepted in the preceding
conversation. Work is on `feature/m2-8-score-cache`, based on PR #17's M2.7 freeze.
No learned QARF/QPAF research training is part of this task.

## Scientific inputs and interfaces

- ViDoSeek revision `e91a92ba5f38690696c7e66be5c5474b54c6e791`: 1,142 queries,
  5,385 canonical pages, 292 PDFs; splits 799/171/172 from M2.1-002/M2.5.
- Reuse M2.6 run `RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01` read-only:
  verify handover, text/preprocessing/policy identities and page image hashes.
  Preserve all page IDs, including empty text and technical-failure fallback.
- Preserve BM25, BGE-M3 and ColQwen2.5 revisions/settings from
  `configs/m2.2/retriever_smoke.toml`; float32 neural inference, no finetuning.
- All remote execution uses `gpu="A10"`, CUDA availability/device evidence;
  BM25 and serialization use host code inside that GPU worker. Neural inference
  and neural score computation use CUDA. No CPU fallback.
- Full-corpus scores cover all 1,142 x 5,385 query-page pairs per channel.
  Top-200 per channel, raw-score descending/page-ID ascending, qrels-free union,
  at most 600 pages/query, union output page-ID ascending, all three scores.
- Raw/normalized output float64, min-max on each query's frozen union;
  range <=1e-15 gives exact zero. Trainer consumes RAW five-column
  `qpaf_score_rows_v1`; normalization is independently auditable, not applied twice.
- Freeze candidate artifacts/hashes before parsing qrels. Export separate page
  qrels and query text. Page coverage >=0.95 and zero queries without positives;
  no dropping/injecting pages or changing depth in response to labels.
  Audit coverage by split without producing test ranking metrics.

## Architecture and persistence

`m28/preflight.py` verifies local pinned inputs without reading relevance and
creates input manifest/query-only payload; `m28/worker.py` executes one GPU
container with read-only M2.6 and shared M2.2 model-cache Volumes plus a new
M2.8 output Volume. Save checksummed embedding/score shards and stage status;
resume only an identical run/source/config, reuse verified completed shards,
retain invocation/failure lineage, no automatic cloud retries. Hard timeout
6 hours, 4 CPU cores, 32 GiB host RAM, one GPU container.

`m28/bundle.py` handles label-free candidate construction and local Parquet
publication, then coverage/qrels export, full semantic/hash verification and
M2.4/M2.5 adapter checks. Local collection reads only result artifacts from
the output Volume, with hash checks and recoverable partial downloads.
`scripts/run_m28_cache.py` prepares/executes/collects/finalizes/verifies a run.
The M2.7 frozen manifest is preserved; real input hashes belong in the new
M2.8 handover and subsequent M3 run manifests.

## Verification and closure

Unit tests exercise deterministic ties, missing/NaN/Inf scores, normalization,
coverage failure with positives outside union, malformed IDs, changed shard
hashes and source/config mismatch. Run small independent GPU score/embedding
parity checks with M2.2 predeclared tolerances. Verify all real raw scores,
top-lists, union, normalization, split/namespace/hash consistency and loader
compatibility. PASS requires coverage; a complete cache with failed coverage
is honestly BLOCKED, retained with report and cannot be silently repaired.

## Research sources (2026-10-20)

- https://modal.com/docs/guide/gpu — explicit GPU selection and CUDA check.
- https://modal.com/docs/guide/volumes — persist closed shards with commit;
  reload mounts between invocations; do not mutate the upstream OCR Volume.
- https://huggingface.co/BAAI/bge-m3 — normalized dense embeddings, no query
  instruction prefix, frozen max sequence length 8192.
- https://huggingface.co/vidore/colqwen2.5-v0.2 and
  https://github.com/illuin-tech/colpali/blob/main/colpali_engine/utils/processing_utils.py
  — batched image/query encoding and multi-vector MaxSim scoring. Continue the
  exact already-calibrated base/adapter/processor pins rather than upgrading.

## OCR HTML cleanup

No review HTML was found in M2.4; existing exports were in results/m2.3.
The user explicitly confirmed removal of those exports while retaining the
source templates. Ten exported HTML files were removed, with exact path/size/SHA
inventory in results/m2.8/verification/ocr-review-html-removal.json. Templates
and scientific OCR data are preserved.
