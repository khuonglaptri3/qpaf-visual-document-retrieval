### Task 3: Clone-and-run owner workflows and delivery

Files: create scripts/run_jev_{phat,thanh,khuong}.py or equivalent owner wrappers, configs/jev/{phat,thanh,khuong}.json, tests/test_jev_owner_workflows.py; update main README/docs index, common task README/evidence, each owner's existing task README/spec/plan during distribution.

Consumes shared CLI/contracts/adapters. Default owner action is a deterministic offline demo/self-check, not paid model job. Explicit commands expose actual prepare/score/evaluate/export/train with file arguments. Outputs are separate by owner/run and synthetic flag; configs never hardcode another person's private path or token.

- [ ] Write failing subprocess tests for each owner one-command workflow in a clean temporary output directory; verify actual JSON/CSV/artifact content and bad-input failures.
- [ ] Implement owner wrappers/configs and Vietnamese quickstarts with exact Windows/Linux commands: no-install offline run, optional isolated GPU setup, private data paths/doctor, baseline cache reuse, local/Modal scoring, training and evaluation. Document prerequisites and remaining full-model verification honestly.
- [ ] Run all Jev tests and actual three owner demos; run full project suite once and record named failures/environment limitations. Save outputs/logs under evidence; no synthetic result presented as retrieval improvement.
- [ ] Complete review/fixes; commit shared implementation. Fast-forward/cherry-pick onto each existing research branch without overwriting remote work; preserve owner brief, update status/commands, verify clone/checkouts and repeat owner smoke on branch tree.
- [ ] Push ordinary fast-forward updates to all three branches and confirm remote SHAs. Preserve main checkout/index, leave managed worktree clean/detached, finalize hashes/provenance/report.
