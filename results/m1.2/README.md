# M1.2 — local QARF/QPAF method core

**Owner: Tấn Phát. Implementation: COMPLETE. Local software verification: PASS.**
Independent reproduction by another group member remains pending. This package
does not report learned retrieval quality on a real corpus.

The [26 September handoff status](../../docs/m1.1-m1.2-status.md) distinguishes
local completion from group acceptance. A new
[handoff verification](handoff-check-2026-09-26/README.md) binds the updated
specification; earlier verification inputs and receipts remain unchanged.

The new method core implements the design in
[docs/m1.2-method-core.md](../../docs/m1.2-method-core.md):

- A fully defined `qpaf13_v1` schema from scores/ranks, channel margins,
  disagreement and query length; no qrels or Oracle decisions in features.
- Matched QARF query pooling and QPAF page conditioning, with linear or shallow
  MLP gates, softmax weights and weighted normalized-score fusion.
- Query-balanced pairwise logistic loss, padding/error handling and a detached
  boundary to frozen retriever scores.
- Hand-calculated tests, finite-difference gradient checks, a synthetic learning
  check and an executable evidence-producing verification command.

## Verified evidence

| Check | Result |
| --- | --- |
| Full repository suite | 69 tests: 68 passed, one Windows symlink privilege skip |
| M1.2 tests, including CLI integration | 25 passed, no skips |
| Fresh copied source tree and new Python environment | Same 25 tests passed, no skips |
| Installed package outside source checkout | Import passed |
| Local vs fresh-environment outputs | Features, predictions, final gate parameters and learning trace matched byte for byte |
| Compile and dependency compatibility | Passed |

Read the [implementation check report](implementation-check/2026-09-26-core-v1/README.md)
for commands, logs and before-implementation failures. The retained run is
[local-core-2026-09-26-001](local-core-2026-09-26-001/verification/20260925T185407-b9f9151b/verification.md).
It contains config, fixture, feature table, predictions, loss/gradient trace,
source/environment provenance, hashes and a completion receipt.

## Run again

From the repository root with Python 3.11:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements/m12-cpu.txt
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_m12*.py" -v
.venv/Scripts/python.exe scripts/verify_m12.py --config configs/m1.2/core.toml --output results/m1.2/local-check-002
```

Use a new output directory every time. `verify_m12.py` prints the attempt path;
the parent `verification/complete.json` identifies its receipt and checksum.
All outputs are software fixtures, not new Oracle/ViDoSeek experiment results.

## Handoff to the next phase

M1.2 supplies the verified core for the dataset/trainer/evaluator in M2.4 and the
matched learned pilot in M3. Freeze real-data feature/loss choices and retriever
settings with the experiment protocol. `qpaf13_v1` is a documented initial
design, not evidence that these 13 features are empirically optimal. The original
research documents and workbook were not edited to claim empirical success.
