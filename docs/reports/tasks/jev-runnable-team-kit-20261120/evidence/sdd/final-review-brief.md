# Whole-branch review brief

Review the runnable Jev toolkit against the [canonical spec](../../superpowers/spec.md) and [plan](../../superpowers/plan.md), including the ordinary expectations of a teammate following the commands. The shared branch starts at F9 `842176c5b707298672629738390a09e222f47e86`. No quality improvement is claimed from synthetic demos, small random CPU models or saved historical rankings.

Implementation reports and task reviews are in this directory; exact source ranges and source-byte hashes are recorded there. [Workflow](../workflow.md), [ledger](progress.md), [rulings](../rulings.md) and [review reconstruction](../review-reconstruction.md) preserve the recovery history. Administrative [packaging probes](../controller-packaging.md) distinguish temporary rehearsal from final clone/remote delivery proof.

The code phases of Tasks 1–3 have their own review gates. Task 3's controller-owned distribution follows this whole-branch gate: merge reviewed ancestry into each existing research branch, update owner documents, validate hashes/layout/current links, run clean-clone Python 3.11 `-I -S` demos, then perform authorized ordinary fast-forward publication and match remote refs. Main checkout branch/HEAD/index must remain as recorded in delivery-before.json. Publication/final-quality checks not yet performed must not be reported as completed code tests.

## Binding constraints

- CPU/offline demo must run with Python >=3.11 and stdlib only.
- No edits to existing src/qpaf/lab or f9, sealed qrels, frozen receipts, original result JSON, or main checkout/index. The original uncommitted research report may receive its planned final status/proof update; its source checkout HEAD/index stay unchanged.
- F9 pair order is page order, NOT ranking; baseline/blend requires explicit aligned base_scores.
- Score coverage exact, finite, non-boolean and bound to input bytes by pairs_sha256; no silent fallback.
- No paid GPU job, large weight download, private-data publication, force push or shared main/develop merge.
- Task bundle has exactly README.md, evidence/, superpowers/; canonical spec.md/plan.md only; all evidence under evidence/.

## Evidence and remaining limits

- Task 3 isolated Jev suite: 64 total, 60 pass/4 named skips; with PyArrow 62 pass/2 named skips. Three real role demos and two offline Modal previews passed. Task reports/logs carry actual commands.
- Task 2 opt-in CPU evidence covers real BGE/Qwen readouts, official Kev one-step base training, saved adapter/head reload and custom-weight fingerprints. It uses locally initialized small models. Full Kev4B/warm-start/GPU/cloud/data-quality execution remains unverified.
- Task 1 ran the historical full repository suite once: 635 tests, 14 failures, 72 errors and 44 skips, named in its report. The user-authorized scope records these environment/pre-existing limitations rather than repairing unrelated source or declaring the whole repository green.
- Deferred Task 2 Minor: the pinned upstream OneCycleLR configuration has an exactly-ten-effective-step edge; source/pin remain fixed and runbook documents adjustment of both controlled budgets together.
- Deferred Task 3 Minor 1: default Khương demo passes configured trainer argv; a config edit can introduce execution/path overrides. Triage against the offline-demo guarantee.
- Deferred Task 3 Minor 2: expected diagnostics from negative-path tests appear in passing logs; output cleanup is unperformed, assertions passed.

Review read-only, without subagents. Use the provided package for the whole change, not a new review of only the latest commit. Check concrete boundary risks and tests; do not repeat reported suites without an unanswered specific doubt. State every behavior you decline to judge and why, all Critical/Important/Minor findings with file:line and practical impact, and whether the code is ready for the authorized owner-branch integration.
