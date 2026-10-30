# SDD ledger — plan: docs/reports/tasks/lab-f3-objective-20261030/superpowers/plan.md

2026-10-30, direct execution of an existing research protocol.

## Pre-flight

- Task 1 → Task 2: pinned Python interpreter plus exact input cache hashes; Task 2 gates on baseline parity.
- Task 2 → Task 3: schema qpaf-lab-v1 per-query JSON, same method/query IDs; compared by existing paired().
- Ruling: use this evidence/ ledger and run-state.json instead of the skill's .superpowers/sdd scratch workspace —
  the owner's explicit artifact convention requires task records under evidence/ — no experiment semantics change.
- Ruling: apply existing tests as verification, without a fabricated RED→GREEN cycle —
  no production code is being implemented — existing source quality remains bounded by these tests.
- Ruling: proceed with eligible ViDoSeek runs while ViMDoc is unavailable —
  local searches and configured Modal volume listing found no ViMDoc cache — overall F3 remains partial.
- Ruling: run unchanged scripts/run_lab.py with --output to evidence/results instead of the one-command share runner —
  that runner requires both datasets in qpaf-lab-share; exact reference hashes and baseline gate remain enforced —
  report must make the missing ViMDoc scope explicit.
- Thread budget: OMP_NUM_THREADS=2, MKL_NUM_THREADS=2; all model settings remain unchanged.

## Task 1

- Isolated managed worktree on feature/lab-f3-objective; original checkout untouched.
- Existing .venv diagnosis: torch_cpu.dll missing, pandas metadata absent. New task-local .venv imports
  torch 2.7.1+cpu, numpy 2.2.6, pandas 2.2.3, pyarrow 20.0.0 successfully.
- ViDoSeek raw_scores.parquet recovered from original .cache/m52-inputs; SHA-256
  56d0c82efda9264c117611ddd7135fe2384b68a3ec60fbdfd80fb964c386622b matches committed source.
- python -m unittest tests.test_lab tests.test_lab_f3 -v: 17 tests, OK (74.368s); see unit-tests.log.
- Smoke and full experiment stages are recorded live in execution.log and run-state.json.
- Task 1 complete for eligible ViDoSeek: both 120-query / 2-fold / 2-epoch smokes passed;
  f3_approxndcg compute 19.1s, f3_topk_hard compute 12.2s. ViMDoc remains unavailable.

## Task 2

- Full baseline completed 2026-10-30T14:12:00Z, source 41bc94e.
- Baseline means reproduce the committed reference exactly: static/qarf/qpaf gaps all 0.0;
  tolerance 5e-5, input hashes and development query IDs match.
- Full f3_approxndcg started immediately after the parity gate passed.
- Ruling: interrupt the incomplete 2-thread ApproxNDCG attempt after fold-0 QARF and rerun with
  OMP/MKL=6 — measured loss forward/backward 0.2592s at 2 threads vs 0.1899s at 6 threads,
  equal loss and nonzero gradients within rtol=1e-10 / atol=1e-12 — discarded compute is recorded,
  no incomplete attempt contributes metrics. Logs are preserved in attempt-threads2/.
- Reuse the completed 2-thread baseline (same interpreter/packages/source/input/recipe, exact parity);
  rerun selected tests and smokes at 6 threads. Thread allocation is execution configuration,
  not a model hyperparameter. Final report must disclose per-stage thread settings.
- Ruling: fix redundant all-pairs ApproxNDCG computation before restarting full experiments —
  only positive units contribute gain, so ranks for negative units are unused; exact positive ranks still
  compare against every masked candidate — preserve the objective and verify loss/gradient equivalence.
  Original dense 2-thread and 6-thread partial attempts are excluded and archived.
  Canonical spec/plan amended before changing production code; no retrospective TDD claim.
- Performance RED observed: original dense implementation allocated 131072 elements, violating the 8192 bound.
- Performance GREEN: 20 selected tests, OK (9.792s), including loss/gradient equivalence, multiple positives,
  padding, invalid queries, and the working-set bound.
- Full repository suite: 802 tests, OK (skipped=6), 440.112s; see full-suite.log.
- Actual microbenchmark: ~21.3x faster loss forward/backward; all meaningful loss/gradient checks agree.
- Performance prerequisite complete at commit e3252f6:
  selected tests rerun after commit: 20 tests, OK (9.851s).
  Both optimized smokes exactly match every per-query score and mean from the original 6-thread smokes.
  Baseline reuse verified by git diff of all shared harness/baseline files and original input hashes.
  Full optimized ApproxNDCG started 2026-10-30T14:43:02Z.

## Task 2 completed for eligible ViDoSeek

- ApproxNDCG completed 2026-10-30T14:52:21Z (536.195s); top-k/hard completed 15:02:49Z (603.364s).
- Three full records: 970 dev query IDs, five folds, original recipe, finite scores, clean recorded source.
- Both variants use e3252f6. Shared baseline/harness files are unchanged from the completed baseline source.
- ViMDoc remains missing; no real-data LSE or ViMDoc result was fabricated.

## Task 3 — final handoff

- All four paired deltas, 10,000-resample CIs and W/T/L computed and checked. Every CI crosses zero.
- Fresh-context review completed after the first reviewer turn hit a usage limit; user explicitly requested continuation.
- Review found no Critical/Important issue. Stale status minor is routine planned finalization, now completed;
  no separate production-code fix pass or deferred code minor is needed.
- Final: Ruling: leave ViMDoc unmeasured until exact cache arrives — missing evidence cannot establish effectiveness —
  cost: overall F3 scope remains partial.
- Final: Ruling: preserve verdict n/a — policy was not frozen before results —
  cost: no automatic KEEP/DROP or architecture selection.
- Final: Ruling: preserve agreed CV/harness — task executes the existing protocol —
  cost: no claim about alternative evaluation designs.
- Final: Ruling: restrict claims to pinned CPU environment — GPU/general version support was not requested —
  cost: no portability guarantee beyond that environment.
- Final: Ruling: retain run_f3.py as a historical execution artifact — report requires fresh output paths and clean tree —
  cost: future replay needs output setup rather than a general-purpose rerun framework.
- Final: Ruling: claim only measured microbenchmark speed and loss/gradient/smoke agreement —
  no full dense-versus-optimized bitwise experiment was completed — cost: no whole-pipeline or bitwise full-run speed claim.
- Final: Ruling: independent review recomputes statistics from recorded runs, without repeating training/full suite —
  direct recorded verification is already available — cost: this is not independent machine replication.
- All review dispositions are preserved in final-review.md; original checkout remains untouched and no remote push/merge occurred.
