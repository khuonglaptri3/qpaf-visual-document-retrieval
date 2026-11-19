# SDD ledger ? plan: docs/reports/tasks/jev-runnable-team-kit-20261120/superpowers/plan.md

Authorization: implement the existing three owner branches, as explicitly directed 2026-11-20. Common integration branch implementation/jev-team-kit-20261120; owner refs remain unchanged until review passes.

| Scan | Produces / consumes | Finding / ruling |
| --- | --- | --- |
| Task 1 self | Contracts/data/evaluation/CPU CLI | stdlib core; no heavy model import. Clear signatures. |
| Task 2 self | Real adapters/training/worker | Optional runtime, explicit dry-run, no automatic jobs. |
| Task 3 self | Owner commands/docs/delivery | Configs/wrappers consume shared CLI; integration verification required. |
| 1 ? 2 | Bundle + score IO ? backends/training | Task 2 may extend CLI after Task 1 review; implementation sequential. |
| 1 ? 3 | Core CLI + evaluate ? owner demos | Exact output shape in Task 1 API; Task 3 tests real subprocess output. |
| 2 ? 3 | score/export/train options ? owner quickstarts | Task 3 writes commands from actual argparse help, not invented names. |

Ruling: report full-suite environment failures rather than repair pre-existing global Torch/ABI during this feature; newly changed toolkit tests and real CLI runs must pass. No claim of GPU training quality is made from offline tests.
Ruling: scratch path is evidence/sdd per explicit user artifact rules, overriding default .superpowers path. Task briefs use the installed extractor's explicit output parameter.

Task 1: pending
Task 2: pending
Task 3: pending
