# M2.2 — Bounded retriever smoke runs

Start with the [documentation index](../../docs/superpowers/README.md).
The [config](../../configs/m2.2/retriever_smoke.toml) pins BM25, BGE-M3 and
ColQwen2.5 separately from the historical M1.1 configuration.

Selected PASS run: [RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01](RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01/report.md).
Handover: [m2.2-001](../../evidence/revisions/m2.2-001/README.md).
The selected visual preset is float32. The recorded bfloat16 attempt failed
token-embedding parity; its tolerances were kept unchanged when selecting float32.

## Execute

From the repository root, using the existing Modal profile:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m22_smoke.py
```

The runner verifies M2.1 payload/split hashes, renders a deterministic sample,
then starts CPU preprocessing/BM25 and GPU dense/visual stages on Modal.
No local PyTorch import is needed to prepare the sample or launch the cloud run.

Inspect inputs without starting cloud resources:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m22_smoke.py --prepare-only
```

Execute that prepared run once, with the same config and source code:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m22_smoke.py `
  --execute-prepared results/m2.2/<run-id>
```

Verify a completed run read-only, optionally publishing a new create-once revision:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m22_smoke.py `
  --verify results/m2.2/<run-id>

.venv/Scripts/python.exe -X utf8 scripts/run_m22_smoke.py `
  --verify results/m2.2/<run-id> `
  --publish evidence/revisions/m2.2-new-revision
```

## Run layout

```text
<run-id>/
  resolved_config.json, source.json, source_snapshot.zip
  execution_started.json
  inputs/                  # query/page IDs, native text, images, input hashes
  remote/
    inputs/                # verified deployed sample
    prepare/               # final shared text, OCR decisions and failures
    bm25/                  # scores, index, checks, resources, environment, logs
    dense/                 # scores, embeddings, batch-1 reference, model hashes
    visual/                # scores, multi-vector embeddings, batch-1 reference
  summary.json, report.md, hashes.json
```

Every completed stage has `summary.json`, `resources.json`, `environment.json`,
`run.log` and `hashes.json`. Failures preserve stage evidence; subsequent stages
requiring failed preprocessing are marked `NOT_RUN`. Failed runs remain preserved.
Source hashes and the source snapshot identify uncommitted implementation bytes;
the Git commit alone is not claimed to contain those changes.

## Limits and interpretation

Default sample: 4 validation queries and 16 ID-selected pages, seed 2026.
Visual images are capped at 200,704 pixels (256 visual tokens), with batch size 2.
Each stage has a 1,800-second platform timeout, no automatic retry, four CPUs and
32 GiB allocated RAM. Observed process RSS, PyTorch reserved VRAM (22 GiB), and
artifact size (512 MiB) are checked separately; the latter checks are acceptance
thresholds, not allocator-level hard stops. The input payload is capped at 64 MiB.
RSS samples cover the Python process at 20 ms intervals; OCR subprocess RAM and
system/driver GPU overhead are not represented by these metrics.

`download_models` measures cache resolution/download plus file hashing. A persistent
model cache can make a later run warm; the first observed download and later warm
loads must be distinguished when interpreting timings. Encoding/scoring are measured
after model loading, with CUDA synchronization. References incur additional work.

Models stay frozen. This small-page smoke test does not measure full-corpus recall,
seal learned training settings, or calibrate OCR thresholds (M2.3).
Scores/embeddings and rendered PNGs remain outside Git; their hashes and small
reports are retained. Remote payloads also persist under the configured Modal Volume.

## Tests

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p 'test_m22_*.py' -v
```

The complete repository suite is `python -m unittest discover -s tests -v` in an
environment with working PyTorch. Test receipts from the pinned Modal Linux image
are stored in `results/m2.2/verification/`.

Run the complete suite on the pinned Modal CPU environment:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/verify_m22_smoke.py
```

The helper sends a source/test snapshot into a temporary synthetic Git checkout
for the existing CLI tests. The receipt records source hashes, test hashes,
uploaded snapshot hash, environment and full unittest output. This checkout is
test infrastructure, not a research source commit.
