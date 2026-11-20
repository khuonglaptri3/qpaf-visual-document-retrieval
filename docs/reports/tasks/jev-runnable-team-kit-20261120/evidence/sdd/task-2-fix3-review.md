# Task 2 fix round 3 review

2026-11-20. Reviewed `710c7e4..3362d38` against finding 1 from the [round 2 review](task-2-fix2-review.md#L7).

- **1. ADDRESSED.** The fingerprint reads the effective local Transformers config and gives `transformers_weights` precedence over default archive names. It hashes the selected archive, the index itself when sharded, and every root-relative shard selected by that index. The same identity calculation runs before chunk lookup and immediately after model load, including for the local base declared by a Kev checkpoint. [Archive selection](../../../../../../src/qpaf/jev/backends.py#L47), [index and shard hashing](../../../../../../src/qpaf/jev/backends.py#L86), [Kev base identity](../../../../../../src/qpaf/jev/backends.py#L143), [pre-cache check](../../../../../../src/qpaf/jev/backends.py#L387), [post-load check](../../../../../../src/qpaf/jev/backends.py#L404)
- **New breakage in the fix diff.** None found.
- **Out-of-scope observations.** None.

## Verification

- Inspected the patch and checked the explicit filename and versioned-config rules against the installed Transformers 5.17.0 resolver. Independently matched both changed-source SHA-256 values to the recorded values. [Source hashes](task-2-report.md#L117)
- Confirmed the implementation report contains the focused RED and GREEN commands, exit codes and outcomes. It records three passing GREEN regressions and a passing opt-in offline CPU test with a custom BGE archive, a version-selected Qwen index, one official Kev training step and checkpoint reload. The test assertions compare actual baseline results with independent forwards and bind the selected bytes to the manifest fingerprints. The review relied on these recorded runs. [Test commands and results](task-2-report.md#L110), [focused regressions](../../../../../../tests/test_jev_backends.py#L44), [CPU fixtures](../../../../../../tests/test_jev_backends.py#L297), [Kev reload assertions](../../../../../../tests/test_jev_backends.py#L359)
- Applied the Superpowers 7.0.1 `subagent-driven-development/re-review-prompt.md` workflow. Read `using-superpowers/SKILL.md`, its Codex reference, and `verification-before-completion/SKILL.md`. Full-size and GPU runtime verification remained outside this review. [Task brief](task-2-brief.md)

**Approved.** Finding 1 is addressed.
