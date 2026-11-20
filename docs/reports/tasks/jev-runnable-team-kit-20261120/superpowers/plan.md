# Runnable Jev team kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task, with task reviews and a final whole-branch review.

**Goal:** Ship runnable code and owner commands on Khương/Phát/Thanh research branches.
**Architecture:** Shared stdlib CPU toolkit and isolated lazy GPU adapters/trainer; preserve F9. Each owner branch receives identical tested shared code and its own runnable entry/config/quickstart.
**Tech Stack:** Python >=3.11 core, unittest; optional torch/transformers/PEFT/Kev/Modal pinned environments.
**Spec:** [spec.md](spec.md)

## Global Constraints

- CPU/offline demo must run with Python >=3.11 and stdlib only.
- No edits to existing src/qpaf/lab or f9, sealed qrels, frozen receipts, original result JSON, or main checkout/index.
- F9 pair order is page order, NOT ranking; baseline/blend requires explicit aligned base_scores.
- Score coverage exact, finite, non-boolean and bound to input bytes by pairs_sha256; no silent fallback.
- No paid GPU job, large weight download, private-data publication, force push or shared main/develop merge.
- Task bundle has exactly README.md, evidence/, superpowers/; canonical spec.md/plan.md only; all evidence under evidence/.

## Review Focus

- Duplicate/missing IDs, stale cache hash and score length/NaN fail explicitly.
- Gold outside pool and document aggregation do not inflate recall/nDCG.
- Split/group overlap and unjudged negatives cannot leak into train by default.
- Help/demo/dry-run never import heavy runtimes, download weights or invoke cloud jobs.
- Real backend/trainer commands preserve head/base/revision and resumable provenance; tests separate contracts from real GPU verification.

### Task 1: Shared data contracts, preparation, evaluation and offline CLI

Files: create src/qpaf/jev/{__init__,contracts,data,evaluation,cli}.py, scripts/run_jev.py, tests/test_jev_contracts.py, tests/test_jev_evaluation.py, tests/test_jev_cli.py, optional small synthetic fixture under tests/fixtures/jev/. No heavy runtime or dependency imports in core.

Interfaces: `load_pairs(path)->dict`, `sha256_file(path)->str`, `load_scores(path,pairs_path)->dict`, `write_scores(path,pairs_path,scores,manifest,details=None)->dict`; `evaluate(bundle,scores,qrels,k=10)->dict` with `mean` and `per_query`; `compare(left,right,seed=20260820,resamples=10000,groups=None)->dict`; `blend_scores(bundle,scores,lam)->list[float]`; `validate_splits(bundle,manifest)->dict`; `main(argv=None)->int`.

- [x] Write tests first, observe intended RED, then implement contracts and stdlib atomic cache IO; duplicate pairs, missing text, score mismatch/NaN/hash and baseline-without-base_scores must reject.
- [x] Implement candidate preparation using explicit supplied base/channel scores, preserve label-free top-K selection. Support importing byte-exact F9 pairs. Real F9 bundle bridge must not read sealed qrels or silently invent/re-fit fusion from evaluation labels. Input missing diagnostics should list paths/next command.
- [x] Implement unit-aware metrics and per-query output; include gold outside pool and full cohort. Test hand-computed ranking, document pooling, duplicate/coverage errors, pure-vs-explicit blend and paired/group bootstrap cases.
- [x] Implement doctor, prepare, evaluate, compare, demo CLI; doctor/demo/help require no torch/numpy/Modal. Demo data and result metadata clearly synthetic and use toy lexical/known fixture scoring, never Jev labels. Tests run subprocess CLI from arbitrary cwd.
- [x] Run focused stdlib tests, record RED/GREEN evidence, self-review and commit own paths. Do not modify model/training modules reserved for Task 2.

### Task 2: Real inference backends, train data/export and execution workers

Files: create src/qpaf/jev/{backends,training}.py, scripts/modal_jev_rerank.py, scripts/train_jev_reranker.py, requirements/jev-baselines.txt, requirements/jev-kev.txt, configs/jev/models.json, tests/test_jev_backends.py, tests/test_jev_training.py; extend cli.py only to wire score/export-train/train. The existing train script may supply the Unix resource peak-RSS interface on Windows from actual psutil peak_wset measurements; it must not alter upstream/global modules outside its child process, must work without editable install, and stays lazy until explicit execution. If a transitive Unix lock import blocks custom-data training, an unused-lock capability guard must fail explicitly when invoked, never simulate successful locking; suite freezing remains Linux-only. Linux/Modal uses the normal official trainer.

Consumes Task 1 contract functions and validated bundle dict. Real scoring produces ordered numeric vectors plus provenance; core writer generates cache. Exact model defaults from original F9: BGE revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e; Qwen3-Reranker-4B revision 22e683669bc0f0bd69640a1354a6d0aebcfeede5. Kev4B revision 6cfce5c2fa4b4bd64026336ab649c5ca78857d52; official Kev source 5e22da2be8ecb2f38790d81d87bb55b0be61a6e2. Preserve base tokenizer/head; read official APIs rather than guessing. Lazy imports, configurable device, batch/input cap, error accounting and no silent zero fallback. `build_training_records` creates official noul state/question requests with boolean label only from assigned train query/page judgments; explicit opt-in for unjudged negatives; reject document-level page training. `build_train_command` returns inspectable argv; --execute starts trainer explicitly, dry-run does not import torch/Modal.

- [x] Write failing contract/behavior tests first and record RED before production code.
- [x] Implement actual BGE sequence-classifier logits, Qwen yes/no log-odds with official prompt, Kev official Checkpoint/admit/to_answers readout and local adapted checkpoints; no stubs/fake model score. Tests verify input/readout/status using pure helpers and unavoidable dependency injection, not only mock-call counts.
- [x] Implement score chunking/resume with full model/revision/input/pool fingerprint, exact-order reconstruction and atomic final outputs. Stale chunk/config and partial failures reject; record runtime/token/peak memory as actual measurements only when backend runs.
- [x] Implement training export and command runner with source/base/init pin, same-backbone base control, configurable seeds/LR/LoRA/head/budget. Check upstream record schema and flags, disable unintended augmentation defaults for controlled relevance training. Save data/checkpoint/run provenance; no eval-label training.
- [x] Implement local and Modal worker paths, isolated requirement sets and source pins; help/dry-run are side-effect free; explicit Modal command is the only cloud trigger. No jobs submitted during implementation.
- [x] Focused tests and compile/help checks, self-review, record actual limitations and commit own paths. Real GPU/inference/training verification is not claimed from contract tests.
- [x] In the isolated CPU runtime, run opt-in integration with locally initialized tiny HF models: real BGE/Qwen readout, official Kev one-step base training, saved adapter/head reload and scoring. No Hub weights/GPU; generated weights stay outside Git and only logs/results are evidence. This verifies runtime plumbing, not Kev4B quality.

### Task 3: Clone-and-run owner workflows and delivery

Files: create scripts/run_jev_{phat,thanh,khuong}.py or equivalent owner wrappers, shared src/qpaf/jev/owners.py if needed, configs/jev/{phat,thanh,khuong}.json, tests/test_jev_owner_workflows.py; update cli.py/data.py/evaluation.py only for explicit native development-label ingestion and known external unit-map hash consistency; update main README/docs index, common task README/evidence, each owner's existing task README/spec/plan during distribution.

Consumes shared CLI/contracts/adapters. Default owner action is a deterministic offline demo/self-check, not paid model job. Explicit commands expose actual prepare/score/evaluate/export/train with file arguments. Outputs are separate by owner/run and synthetic flag; configs never hardcode another person's private path or token.

Role demos exercise Phát's prepare/split/cache path, Thanh's baseline/toy-score evaluation/comparison, and Khương's train export plus dry-run Kev/base plans. No real model training occurs by default.

- [x] Write failing subprocess tests for each owner one-command workflow in a clean temporary output directory; verify actual JSON/CSV/artifact content and bad-input failures.
- [x] Implement owner wrappers/configs and Vietnamese quickstarts with exact Windows/Linux commands: no-install offline run, optional isolated GPU setup, private data paths/doctor, baseline cache reuse, local/Modal scoring, training and evaluation. Document prerequisites and remaining full-model verification honestly.
- [x] Bridge the actual native ViMDoc development qrels shape explicitly (role -> query -> positive document IDs) to canonical flat judgments via a documented CLI format flag or conversion command; require document units and reject duplicate/ambiguous assignments. Do not auto-read sealed labels or change the flat evaluation API. Cover the real source schema with synthetic fixtures.
- [x] Run all Jev tests and actual three owner demos; retain the Task 1 full-project suite results and named failures/environment limitations without rerunning that unchanged suite. Save outputs/logs under evidence; no synthetic result presented as retrieval improvement.
- [ ] Complete review/fixes; commit shared implementation. Merge the reviewed implementation into each existing owner research branch to retain the actual reviewed commit ancestry, without overwriting remote work; preserve owner brief, update status/commands, verify clone/checkouts and repeat owner smoke on branch tree. Remote updates remain ordinary fast-forwards; do not merge into main/develop.
- [ ] Push ordinary fast-forward updates to all three branches and confirm remote SHAs. Preserve main checkout/index, leave managed worktree clean/detached, finalize hashes/provenance/report.

Controller evidence helpers `evidence/update_owner_docs.py`, `evidence/finalize_artifacts.py` and `evidence/verify_delivery.py` archive bootstrap status, validate exact bundle/link/hash invariants, smoke actual fresh local clones under Python 3.11 `-I -S`, and then match published refs to the tested commits. They do not submit jobs or push; publication is a separate controller action after both review gates. Record immutable commit/clone/remote proofs without self-referential hashes. Final research-status update links the published GitHub runbook because the main checkout intentionally stays at its original source tree.
