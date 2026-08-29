# Experiment protocol changelog

## 2026-08-29 - ViDoSeek full extraction GPU

- Status: approved by the user.
- Approval text: `Approve L4 for full ViDoSeek extraction`.
- Change: request `L4` for `modal_app.py::extract_vidoseek_scores`; keep the generic ViDoRe extractor on `A100-40GB`.
- Evidence: the bounded ViDoSeek calibration completed on NVIDIA L4 with 22.034 GiB available, 7.720 GiB maximum allocation, 100% candidate coverage, and manifest SHA-256 `2213b96ee99f4e2409355db80d650590393a8953f67f90de8259cd84373499c7`.
- Unchanged: model IDs/revisions, batches, candidate depths, 23.5 decimal-GB preflight guard, preprocessing, qrels boundary, and output integrity gates.
- Execution status: local protocol/code preparation only; no Modal command was executed for this change.
