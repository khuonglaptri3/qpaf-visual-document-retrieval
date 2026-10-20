# M2.8 - Real GPU score cache and coverage result

**GPU COMPLETE / CACHE VERIFIED / BLOCKED_COVERAGE**.

The full real-data cache is produced and verified. It does **not** meet M2.8's
zero-uncovered acceptance condition: candidate recall is **99.912434%**, but one
training query has no relevant page in its frozen union. No query was dropped,
positive page injected, top-k changed, or failed gate relabeled PASS.

Authority: `POAI_Milestone_Group01_Hoan_Chinh.xlsx`, Milestones row 33, owner
Khuong: three retriever scores, top-200 lists, at most 600-page unions,
recall >=0.95 and zero uncovered queries.

## Measured output

| Measure | Result |
|---|---:|
| Queries / pages / PDFs | 1,142 / 5,385 / 292 |
| Train / validation / test | 799 / 171 / 172 |
| Query-page scores per channel | 6,149,670 |
| Scalar scores across all three channels | 18,449,010 |
| Frozen query-page candidates | 549,689 |
| Candidate minimum / mean / maximum per query | 386 / 481.338879 / 571 |
| Channel top-list rows | 685,200 |
| Top depth per channel | 200 |
| Complete collected cloud artifacts / bytes | 281 / 251,435,113 |
| Portable bundle files / bytes | 16 / 31,473,182 |
| Verified embedding receipts / retained payload files | 129 / 129 |
| Retained embedding payload bytes in Modal | 733,248,608 |

| Split | Relevant pages captured | Macro candidate recall | Uncovered queries |
|---|---:|---:|---:|
| Train | 798 / 799 | 0.9987484355444305 | 1 |
| Validation | 171 / 171 | 1.0 | 0 |
| Test | 172 / 172 | 1.0 | 0 |
| All | 1,141 / 1,142 | 0.999124343257443 | 1 |

These are frozen candidate-coverage audits. No test ranking metric, checkpoint
selection, learned QARF/QPAF training or learned improvement result was produced.

## Why the gate is blocked

Training query: `04450a0f59f81025574451222aa26322ae7ede42_2`.
Its sole positive is `04450a0f59f81025574451222aa26322ae7ede42_page_0007`.
The frozen union contains 448 pages for this query, excluding that positive.

| Channel | Positive page rank | Positive raw score | Top-200 cutoff |
|---|---:|---:|---:|
| BM25 | 271 | 11.58600389119631 | 12.661955399583501 |
| Dense | 273 | 0.417117178440094 | 0.42588937282562256 |
| Visual | 769 | 14.120915412902832 | 15.459769248962402 |

The positive page is present, rendered successfully, has 341 characters of
native+OCR text, and is not a technical-failure page. Image/text checksums match
the frozen M2.6 input. Dense/visual full-array values match their original score
shards at this page. Other pages from the same document rank highly.

Inference from the valid timeline image and text: the relevant page supplies
little project-specific vocabulary, while other pages carry the project
context. The demonstrated failure is a retriever miss under the fixed top-200
policy. No missing-page, namespace, nonfinite-score or shard-alignment fault was
found. See [the exact train-only diagnosis](../../../results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/uncovered_diagnosis.json).
Independent artifact review reproduced the miss and detected no corruption.

## Actual GPU execution and resources

Run: `RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01`.
Completed UTC: `2026-10-20T16:15:49.671479+00:00`.
Actual GPU: **NVIDIA A10**, CUDA 12.6, PyTorch 2.7.1+cu126. One invocation,
zero requested retries, 4 host CPU cores, 32,768 MiB host memory, six-hour cap.
Neural encoding and neural scoring ran on CUDA, without CPU fallback. BM25,
serialization and file checks used host code in that same GPU container.

| Measured resource | Result |
|---|---:|
| GPU worker wall time | 5490.35 s (91.51 min) |
| Peak Python process RSS | 12005.96 MiB |
| Peak CUDA allocated memory | 14830.17 MiB |
| Peak CUDA reserved memory | 15028.00 MiB |
| Dense page encoding | 157.14 s |
| Visual page encoding | 4,627.29 s |
| Dense / visual CUDA score phases | 74.89 / 254.34 s |

The outer full-run phase overlaps its subphases; timings must not be added
together as independent elapsed time. No unverified dollar-cost estimate is made.

All M2.2 model/base/processor revisions, FP32 settings, batch sizes and visual
pixel budget remain pinned. Dataset revision is
`e91a92ba5f38690696c7e66be5c5474b54c6e791`; M2.6 OCR preprocessing and canonical
page IDs are unchanged, including 19 empty-text pages and one explicit OCR
technical-failure fallback. The upstream OCR Volume was not modified.

## Verification and limits

- All **34 targeted M2.8 tests pass**. Compile checks and staged diff checks pass.
- Every collected artifact checksum was replayed. The full read-only closure
  replay passed in 142.22 s and changed no bundle bytes.
- A fresh reviewer independently reconstructed all channel top-lists, unions,
  549,689 raw rows, normalization values and coverage from the complete matrices,
  without calling the production candidate builder. The review contains its
  verifier source and exact input hashes.
- Independent full BM25 replay: maximum absolute error 4.263256414560601e-14.
  Independent dense embedding-dot replay across all pairs: 4.172325134277344e-07.
- GPU batch-reference probe errors: dense 2.384185791015625e-07; visual
  0.00017547607421875. Independent visual MaxSim probe: 1.9073486328125e-06.
  All declared M2.2 tolerances passed. Visual reference probes cover four queries
  by sixteen pages; they are not a second full-corpus image inference run.
- All 85 visual page shards cover the 5,385-page namespace, and visual query
  embeddings cover all 1,142 queries. Receipt hashes and payload bindings pass;
  full visual embedding payloads remain in Modal rather than being downloaded
  and independently re-encoded locally. Saved page sequences have 239-263
  positions including processor tokens, with embedding width 128.
- The exact five-column RAW trainer schema and M2.4/M2.5 row audit pass. Actual
  M2.4 portable split loading passes; development records retain all 799 train
  and 171 validation queries. Normalized scores are a separate union min-max
  audit artifact, with constant-range epsilon 1e-15.
- Candidate freeze time is `2026-10-20T16:21:49.185938Z`. Candidate construction accepts
  no qrels; the relevance mapping/coverage is built after freeze and full-array
  replay. Query-only preflight ignores annotation relevance metadata. Development
  and test qrels are separate files; the test file is used only for coverage.

The existing local Windows Torch DLL issue affected result unpickling after the
GPU had completed. A narrow Modal DeserializationError fallback now validates a
committed terminal JSON summary's identity and timestamp. Five new regression
tests reproduced the issue, then passed after the fix; the real status command
now returns COMPLETE. It triggered no new GPU invocation. Local closure uses
base Python with NumPy/Pandas/PyArrow; actual neural execution used the pinned
cloud CUDA stack. The targeted test result is not a claim about the entire
legacy repository test suite on the broken local Torch environment.

## Provenance and durable handover

PR #17's M2.7 work froze matched configs and checked parity on synthetic
fixtures; it did not build this real cache or train learned models. This work
is on `feature/m2-8-score-cache`, based on M2.7 head
`fcf41beec800121fa72d4784a75a771ef542d7ae`. M2.7 evidence is unchanged.
The launched source includes implementation changes captured byte-for-byte in
`source_snapshot.zip`: 151 source files plus resolved configuration. Closure-only
CLI fixes are bound separately, without altering the completed GPU computation.

| Identity | SHA-256 |
|---|---|
| GPU source manifest | `5582b7a540c3453808b2efbdb6bd13d613a728a2c45b6b4364c33667c158d686` |
| GPU source snapshot ZIP | `b085a150a8161e0fd725cf1d5b876747c3912ba9d8f2ef9928290d95bc8b91d7` |
| Resolved config object | `0a60bbc36d1a26db97ec51986c61da2c06c08f247b105f1b4cdb9457b169c0f9` |
| Scientific input object | `d1bbd303835c11e8cdb0db5b53bc32aad096f770a0236e23c3cdc486ced74d8d` |
| Closure CLI source | `7ef8b221bcf23df7aad43cb5a9b043f8e81856c5479d8f694461a83c2ed0ccb5` |
| Candidate freeze | `4ff420008b9ccaa3a4d3afc565c43e2c974b3f95dd39a22a742b47297aead06e` |
| Raw score Parquet | `1556bd330af560a42e30299e46acdaa40654e5b8522cc3cda4d15bd1942177ca` |
| Bundle byte manifest | `a31e072022f8b5088bac7f7a477d214301dc191abc4bfb48a5663121cecfb6e4` |

[Modal app](https://modal.com/apps/tlcn-group1/main/ap-HNWFiUPRZS12OoWYOBr138).
Function call: `fc-01M5CWA5A503AXSS1NKZNP0G4Q`.
Volume: `qpaf-m28-score-cache`; remote prefix: `/runs/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/`.
The three full matrices, raw score shards and embedding indexes are retained
there. The new portable `bundle/`, original source snapshot, current finalizer
and closure evidence were uploaded without overwrite, then read back byte-for-byte:
**32 files / 31,921,646 bytes**, plus the
cloud verification receipt itself, also read back. Scientific status remains
BLOCKED_COVERAGE in both local and cloud handovers.

The local bundle is `results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/bundle/`.
Large arrays, Parquet and tensor payloads remain local/cloud; Git retains the
reports, receipts, exact source archive and hash manifests. Reproduction commands
and complete artifact roles are in [the saved-file index](../../../results/m2.8/README.md).

## OCR review cleanup and next action

Removed all **10 exported OCR review HTML files under results/m2.3/** after the
user confirmed that scope. No exported review HTML existed in M2.4. Both
`src/qpaf/m23/review_template.html` and the M2.3 evidence template are retained.
The deletion inventory records each path, size and SHA-256. Scientific OCR
payloads and historical evidence other than the authorized HTML exports remain.

M2.8 technical execution, cache construction and verification are closed with a
negative acceptance result. **M2.8 is not accepted as ready for learned pilots.**
M2.10/D1 must independently review the training miss and decide a documented
protocol amendment if retriever/candidate settings are to change. A revised
policy requires a new run and evidence revision; this freeze must remain intact.
No named human M2.10/D1 approval is claimed by the Codex code/artifact reviews.

## Research used before implementation

Explicit GPU selection and durable closed-shard commits follow the official
[Modal GPU guide](https://modal.com/docs/guide/gpu) and
[Volume guide](https://modal.com/docs/guide/volumes). Model use was checked against
the [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3),
[ColQwen2.5 model card](https://huggingface.co/vidore/colqwen2.5-v0.2) and official
[ColPali scoring implementation](https://github.com/illuin-tech/colpali/blob/main/colpali_engine/utils/processing_utils.py).
The frozen M2.2 revisions/settings were preserved rather than upgraded.
