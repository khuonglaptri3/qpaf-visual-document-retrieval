# Workflow provenance

Started: 2026-10-30 (Asia/Saigon).
Authorization: user explicitly requested immediate execution of F3.
Source: 2f15eb19b1a224f5768a5cfaa28692fb06e55b95, origin/feature/lab-f3-objective.
Task bundle: docs/reports/tasks/lab-f3-objective-20261030.
Canonical planning: [spec](../superpowers/spec.md), [plan](../superpowers/plan.md).

## Skills actually read

Installed package root: C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/
- using-superpowers/SKILL.md (also references/codex-tools.md read earlier in this conversation): initial workflow selection.
- writing-plans/SKILL.md: proportional execution plan and self-review; existing F3 design reused.
- executing-plans/SKILL.md: direct execution, owner-convention evidence ledger, and completed fresh-context final review.
- using-git-worktrees/SKILL.md: checked existing isolation and native attachments, created managed worktree.
- test-driven-development/SKILL.md and writing-good-tests.md: applied to the exact ApproxNDCG performance fix.
- systematic-debugging/SKILL.md: applied to broken local torch import; torch/lib/torch_cpu.dll is absent.
- verification-before-completion/SKILL.md: applied before the performance commit and final handoff.
- requesting-code-review/SKILL.md and code-reviewer.md: applied; fresh-context gpt-6-astra agent reviewed source and evidence
  and independently reproduced all four paired statistics. See [review](final-review.md).
- finishing-a-development-branch/SKILL.md: read only; integration/merge is outside this experiment request,
  and full F3 remains incomplete without ViMDoc. Preserve the local branch/worktree for handoff.

## Decisions

- Existing authorization covers routine environment setup and local execution; no additional approval is requested.
- User storage convention supersedes skill scratch/output defaults: all task records remain in evidence/.
- Worktree native path: C:/Users/lanph/.codex/worktrees/2e13/Artificial_Intelligent_Project.
- Original checkout remains on feature/m5-2-cache-parity.
- Separate environment avoids modifying the original broken .venv.
- modal skill read at C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/.agents/skills/modal/SKILL.md
  (metadata version 1.5.5); only read-only volume listing/downloading was in scope.
- Use existing run_lab.py with explicit --output to keep JSON under task evidence.
- Do not implement verdict() after viewing results; preserve n/a.
- A005/F3 implementation predates this task; this record does not certify prior development.
- ViMDoc share package was not found in searched local locations or the configured Modal account.
  User confirms they do not know of it; ViMDoc is explicitly ineligible until the three matching cache files arrive.

## Actual verification

- Existing .venv torch import failed WinError 126; torch_cpu.dll absent, pandas metadata missing.
- New task-local environment imports all four pinned core packages successfully.
- Original tests: 17/17 passed. Both original smokes passed.
- Original full baseline: 970 queries, all five folds, means exactly match committed reference (all gaps 0).
- Dense ApproxNDCG attempts at 2 and 6 threads were deliberately interrupted for performance;
  their logs are archived, and no partial metric is used.
- Performance RED: intermediate allocation test failed on the original formula: 131072 elements > 8192 bound.
- Performance GREEN: 20/20 selected tests passed, including dense/sparse loss and nonzero-gradient equivalence.
- Microbenchmark [16,579], two positives/query, 6 threads: dense 0.23624s vs positive-rank 0.01108s per
  forward/backward (~21.3x); largest intermediate 5363856 vs 18528 elements. This is not a full-run latency claim.
- Full repository command python -m unittest discover -s tests -q: 802 tests, OK (skipped=6), 440.112s.
- Optimized full runs completed: ApproxNDCG 536.195s and top-k/hard 603.364s, each 970 queries / 5 folds.
  Full variants source e3252f669cb76c1256cbc5149793c7eadd27c878; baseline source 41bc94e56e7f550436899780e76e68376b6aebd3.
- Three full JSON records have smoke=false and tracked_changes=false; shared harness/baseline code unchanged.
- All four paired CI95 cross zero; verdict remains n/a. No confirmation/test labels or cloud compute used.
- Fresh-context independent agent review: no Critical/Important findings. Its status-finalization minor was completed
  as the already-planned handoff work. Reviewer did not rerun training/tests; it independently checked stats and evidence.
- User requested continuation after a reviewer usage limit; no completed experiment was rerun.
- Captured PowerShell UTF-16 logs were losslessly converted to UTF-8 before final hashing;
  original/converted hashes are recorded in encoding-normalization.json.
- Exact evidence bytes and traceback whitespace are preserved by the task-specific .gitattributes rule.
- Layout, links, source provenance, means, W/T/L, baseline parity, and recorded hashes are verified by validate_delivery.py.
- Remaining: receive matching ViMDoc cache and run its three variants; no overall F3 completion claim.
