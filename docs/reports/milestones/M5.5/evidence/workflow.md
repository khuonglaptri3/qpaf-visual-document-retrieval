# Workflow — PR #45 continuation, 2026-10-27

## Authority and scope

Current user request: `https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/pull/45 làm tiếp đi nó vẫn chưa làm xong`.
This authorizes continuing the existing PR, fixing its checks, verifying evidence,
and updating its branch. No merge or independent human acceptance is inferred.
The prior explicit prohibition on Modal/GPU remains effective until the pending
clarification is answered. No Modal connectivity probe or GPU request has run.

Start: PR HEAD `1bdb491ec3b74f578c31dda5ba796d1d375ac586`.
Original checkout was clean on `feature/m5-2-cache-parity`; native managed
worktree created at `C:/Users/lanph/.codex/worktrees/6a15/Artificial_Intelligent_Project`.
Execution branch: `feature/m5-5-diagnostics`, tracking the PR head branch.
No repository/ancestor AGENTS.md or AGENTS.override.md was found; the policy
provided in this conversation applies.

## Skills actually read

All process skills are from the installed Superpowers **7.0.1** package:
`C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/`.

- `using-superpowers/SKILL.md` and `references/codex-tools.md`: read; applied initial discovery and process-first order.
- `systematic-debugging/SKILL.md`: read; investigating CI failure before any fix.
- `using-git-worktrees/SKILL.md`: read; detected checkout state, listed native attachments and created one from the exact PR ref. Routine reversible isolation proceeded under the developer's standing authorization.
- `writing-plans/SKILL.md`: read; applied to continuation of the approved scope, with the user's mandatory locations.
- `executing-plans/SKILL.md`: read; execution inline for this small fix.
- `test-driven-development/SKILL.md` and `writing-good-tests.md`: read; regression must fail before the fixture fix.
- `verification-before-completion/SKILL.md`: read; no completion claim yet.

Reading is not evidence of executing every phase. Historical CPU execution
predates this continuation and is not attributed to this session.

## Planning and decisions

Canonical files: `../superpowers/spec.md`, `../superpowers/plan.md`.
Moved the PR's existing spec/plan here without parallel copies. Their original
bytes remain in Git at the starting commit.

Ruling: continue the approved CPU design and execute the CI repair inline — the
user requested continuation; no new research behavior is being designed — GPU
execution still needs the outstanding answer; human acceptance cannot be inferred.

Pre-flight: fixture changes must not touch M5.5 source/authority pins; replay
must preserve all original run bytes and use the recorded numerical runtime.
Planning migration must leave working report/index links.

## Investigation

- No PR review comments or submitted reviews.
- Push workflow `40446100915` passed; PR workflow `40446210251` failed.
- Failing job: `method-core (ubuntu-latest)`, Python 3.11.17, Git 2.55.0.
- 635 tests, one cleanup error, 4 skipped. Failure in `test_m34_supervisor.SupervisorTests.test_an_unapproved_or_mismatched_authorization_is_refused`: `OSError: [Errno 39] Directory not empty: 'objects'` from TemporaryDirectory cleanup.
- Hypothesis: automatic Git maintenance detaches during fixture commits and writes objects while cleanup removes the repository. Forced-maintenance reproduction required before treating this as confirmed.

## Execution and verification

- Real forced-maintenance regression failed before the fix: Git spawned a worker
  with `--detach`. After setting both `maintenance.autoDetach=false` and
  `gc.autoDetach=false` only in the test helper, it passed; all 18 M3.4 tests passed.
- The initial system-Python 3.14.6 full-suite run was unsuitable: 537 tests,
  14 failures, 55 errors, 43 skipped, caused by absent torch/pypdfium2 and other
  optional dependencies. Full named output is `full-suite-python314.txt`;
  it is not a passing verification claim. A dependency-complete run is underway.
- Local M4.2 restoration from its existing isolated worktree checked the external
  manifest and every source/target hash before copying seven missing payloads.
  Historical M5.5 result/evidence/source/authority bytes were unchanged:
  `local-restoration.json`. Numerical replay has not yet run.

## Successor GPU authorization and workflow

The user explicitly replied: `Cho phép chạy Modal/GPU để hoàn tất số đo M5.5`.
After explaining the 171-ID versus >=1,000-event counting choice, the user replied:
`Tự quyết chi tiết và triển khai trong phạm vi validation`.
This supersedes the old machine-specific prohibition and delegates protocol
details within validation. No additional scope/approval question is needed.

- `brainstorming/SKILL.md`: read when GPU implementation became authorized.
  Compared validation-event repetition, broader distinct-ID input and historical
  reuse. The user opted out of further questions and delegated details; the skill's
  explicit opt-out exception ends its design approval gate. Recorded the actual
  choices in the canonical spec before implementation.
- `modal/SKILL.md`, version 1.5.5, at
  `C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/.agents/skills/modal/SKILL.md`:
  read after process skills. Consulted official llms.txt, GPU docs and current
  pricing. An authorized read-only `modal app list --json` succeeded; no application
  was created and no GPU was allocated (`modal-connectivity.json`).
- Applying `writing-plans` again to extend the same canonical plan for R5-04;
  executing inline using TDD. Original CPU source and authorization remain frozen.

Ruling: use 20 warm-up events plus six full validation passes, 1,026 timed events
over 171 distinct IDs, and report both counts — preserves registered validation
scope under the user's delegation — results must not be represented as M3.6's
1,000-distinct-ID protocol or as independent human acceptance.
Ruling: one A10/2-core/5GiB/900s invocation, budget target USD0.50 with no automatic
retry — reuses the prior measured runtime and adequate RAM, bounded by current
listed allocated-compute estimate ~USD0.309 — provider billing is not a hard cap.

## Fresh review and current verification

- Applied `requesting-code-review/SKILL.md` and its `code-reviewer.md` template;
  fresh read-only agent `/root/m55_gpu_review` reviewed implementation and constraints.
  Findings/disposition: `engineering-review.md`. This is not human acceptance.
- Full pinned-PDFium software suite: **645 tests OK, 4 skipped** in
  `full-suite-pinned-pdfium.txt`. This preceded one additional review regression;
  the final suite will include it. Method-core verifier: **23 tests, no skips**,
  successful synthetic software verification in `method-core/`.
- Previous complete Python3.13 run had 636 tests, 3 failures, 3 errors, 4 skipped
  because PDFium5.14 differed from required4.30 (`full-suite-python313.txt`).
  Used an isolated dependency overlay; did not change the old worktree environment.
- GPU workload/auth contract tests observed RED then GREEN. Review-driven
  candidate/CUDA consistency and runtime declaration regressions observed RED.
  Source-only and validation-only bundle preparation precedes any remote call.

Final: Ruling: missing global event statistics are a material spec gap, despite
the reviewer's Minor grade — add them under the same observed RED-to-GREEN pass —
without them the promised description of repeated-event timing would be incomplete.
Final: minor (deferred): worker-level malformed-reference guard; current exact
reference hashes/coverage/finiteness are checked before the authorized invocation.
