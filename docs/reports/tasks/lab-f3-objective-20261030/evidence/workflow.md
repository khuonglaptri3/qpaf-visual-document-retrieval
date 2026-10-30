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
- executing-plans/SKILL.md: direct execution and evidence ledger; final fresh review still pending.
- using-git-worktrees/SKILL.md: checked existing isolation and native attachments, created managed worktree.
- test-driven-development/SKILL.md and writing-good-tests.md: applied to the exact ApproxNDCG performance fix.
- systematic-debugging/SKILL.md: applied to broken local torch import; torch/lib/torch_cpu.dll is absent.
- verification-before-completion/SKILL.md: applied before the performance commit and final handoff.
- requesting-code-review/SKILL.md and code-reviewer.md: read; fresh whole-task review is pending.
- finishing-a-development-branch/SKILL.md: read only; integration/merge is outside this experiment request,
  and full F3 remains incomplete without ViMDoc. Preserve the local branch/worktree for handoff.

## Decisions

- Existing authorization covers routine environment setup and local execution; no additional approval is requested.
- User storage convention supersedes skill scratch/output defaults: all task records remain in evidence/.
- Worktree native path: C:/Users/lanph/.codex/worktrees/2e13/Artificial_Intelligent_Project.
- Original checkout remains on feature/m5-2-cache-parity.
- Separate environment avoids modifying the original broken .venv.
- modal skill read at .agents/skills/modal/SKILL.md (metadata version 1.5.5); only read-only volume listing/downloading is in scope.
- Use existing run_lab.py with explicit --output to keep JSON under task evidence.
- Do not implement verdict() after viewing results; preserve n/a.
- A005/F3 implementation predates this task; this record does not certify prior development.
- ViMDoc share package has not been found; user confirms they do not know of it. Search and eligibility remain pending.

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
- Optimized full F3 runs and final evidence review remain pending.
