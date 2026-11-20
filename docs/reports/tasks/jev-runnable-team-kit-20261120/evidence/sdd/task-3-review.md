# Task 3 review, 2026-11-20

Reviewer: `jev_owner_workflows_review`, isolated gpt-6.2-sol/high. Range `3362d38..944f306`; [brief](task-3-brief.md), [report](task-3-report.md). Applied the installed Superpowers 7.0.1 task-reviewer template; read-only review and no repeated suite run.

**Spec compliance: issues found. Task quality: Needs fixes.** No Critical findings.

## Important

1. The matched baseline report carries the wrong score-mode label. The documented `--scores "$run/base.json"` command computes baseline metrics, but report consumers see `score_mode: pure`. Use `--baseline` in the primary matched-baseline example and keep the saved-cache example identified as cache validation or reuse. This is a documentation fix and preserves the shared CLI contract. Evidence: common README.md:135 and src/qpaf/jev/cli.py:292.

## Minor

1. Khương's demo forwards arbitrary trainer arguments from its config. The shipped values produce CPU plans. A config edit can add `--execute` or override fixture paths during the demo. Expose `max_steps` as a config value and construct the fixed dry-run arguments in the wrapper. Evidence: src/qpaf/jev/owners.py:62.
2. Green logs include expected diagnostics from existing negative-path tests. Those diagnostics accompany passing assertions. Capturing those streams in the existing tests would make unexpected output easier to spot. Evidence: evidence/task-3-green.log:9.

## Strengths and scope

Subprocess tests inspect actual artifacts from an arbitrary working directory under `-I -S`, verifying Phát's byte-bound cache, Thanh's synthetic metrics/CSV and Khương's page labels/matched plans. The adapter matches the historical native loader's development role/query/document schema, rejects ambiguous inputs, requires a complete explicit map and preserves outside-pool positives. Compare regressions cover changed known sidecar hashes and unknown legacy hashes. Logs record three default demos and both suites with named skips; reviewer directly checked bundle/planning layouts.

Outside-diff check: historical loader schema in src/qpaf/lab/data.py:66, to verify native adapter compatibility. Controller-owned owner-branch updates, clone smoke, remote refs and main preservation remain to verify. Private-data/GPU quality remains explicitly unverified.
