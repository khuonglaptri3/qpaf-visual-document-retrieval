# Controller rulings

Collected in ledger order. These are implementation and delivery choices within the user-authorized scope.

1. Ruling: report full-suite environment failures rather than repair pre-existing global Torch/ABI during this feature; newly changed toolkit tests and real CLI runs must pass. No claim of GPU training quality is made from offline tests.

   Cost if wrong: Historical environment failures remain unresolved; new toolkit and actual clone runs are verified separately.

2. Ruling: scratch path is evidence/sdd per explicit user artifact rules, overriding default .superpowers path. Task briefs use the installed extractor's explicit output parameter.

   Cost if wrong: Documentation or artifact organization may require reversible follow-up; provenance remains in Git.

3. Ruling: prepare supports explicit split filtering and score-cache remapping by pair IDs; filtered files receive new byte hashes. This prevents accidentally evaluating an adapted model on training queries and allows safe reuse of original F9 raw scores.

   Cost if wrong: Documentation or artifact organization may require reversible follow-up; provenance remains in Git.

4. Ruling: core tests run under isolated Python (-I -S) to prove no optional model/data dependency is required. Heavy CPU integration uses a fresh external Python 3.13 environment, leaving user runtime untouched.

   Cost if wrong: Historical environment failures remain unresolved; new toolkit and actual clone runs are verified separately.

5. Ruling: standalone top-K evaluation is shortlist-only. Document aggregation may differ from full F9 tail rankings; exact replay stays in legacy screen/stack. New results must not be compared as identical protocol to historical full-ranking means.

   Cost if wrong: Results could be compared under different label/ranking protocols; raw manifests permit diagnosis.

6. Ruling: reconstructible review-package diffs under evidence/sdd are ignored local scratch to avoid recursively committing diffs of diffs; actual briefs/reports/reviewer findings and validation remain committed. Final artifact hashes cover permanent delivered files and list scratch exclusions. Retain required audit evidence instead of deleting this user-mandated evidence workspace.

   Cost if wrong: Documentation or artifact organization may require reversible follow-up; provenance remains in Git.

7. Ruling: owner wrapper defaults write within common task evidence/runs/<owner>, with generated private/checkpoint paths ignored locally; actual test/provenance summaries are committed. This honors user artifact rules without incomplete per-owner task folders on a shared integration tree. Insert docs-index common row away from owner EOF additions for conflict-free delivery.

   Cost if wrong: Documentation or artifact organization may require reversible follow-up; provenance remains in Git.

8. Ruling: Task3 implementer owns runnable wrappers/configs/docs/tests; controller owns cherry-picks, owner brief status and publication after task/final reviews. Delivery checklist remains pending until actual remote proof, and no worker may push before review. No duplicate legacy full-suite run without new concern; full Jev/integration checks still required after edits.

   Cost if wrong: Review SHA links could become unreachable or integration could need rework; owner/main history is preserved.

9. Ruling: official pinned Kev trainer unconditionally imports Unix resource only for peak RSS; Windows needs a child-local launcher mapping actual psutil peak_wset bytes to KiB. Permit new train_worker.py, never modify upstream/global environment, and test clean-clone/arbitrary-cwd launching without pip -e. Linux/Modal keeps normal official training. Cost if wrong: isolated Windows training fail; actual one-step test required.

   Cost if wrong: Windows training could fail; Linux/Modal stays on the official path.

10. Ruling refinement: the Windows adaptation fits the already-planned scripts/train_jev_reranker.py with an absolute child script path. Do not create a redundant train_worker.py; canonical plan corrected before delivery. Resource binding remains child-local and source-pinned.

   Cost if wrong: Windows training could fail; Linux/Modal stays on the official path.

11. Ruling: actual one-step Windows integration exposed transitive kev.suite fcntl import after resource adaptation worked. Inspect use; allow child-local unused-lock capability guard that raises if invoked for our --data-only path, never a no-op lock. If locking is required, use real Windows semantics or report blocker. Full suite freezing remains Linux-only; source Linux/Modal path unchanged. Check reload/provenance lazy suite imports too.

   Cost if wrong: Windows training could fail; Linux/Modal stays on the official path.

12. Ruling: focused source inspection (not actual labels) found native ViMDoc dev_qrels is role-nested positive-document lists, while core API intentionally takes flat numeric judgments. Task3 owns an explicit CLI native-dev adapter + fixture tests and documentation, preserving canonical API and no sealed-label discovery. This is required glue for actual existing data, not a new research method.

   Cost if wrong: Results could be compared under different label/ranking protocols; raw manifests permit diagnosis.

13. Ruling: deliver reviewed shared commits by an internal feature-branch merge into each owner research branch, not cherry-pick copies, so actual SHA references in review/TDD reports remain reachable on GitHub. Preserve owner history/briefs; ordinary fast-forward remote updates only, no main/develop merge or force. Docs-index common row is separate from owner EOF additions. Regenerate branch-local documentation manifests after owner-specific status updates.

   Cost if wrong: Review SHA links could become unreachable or integration could need rework; owner/main history is preserved.

14. Ruling: Modal docs confirm last-write-wins across independent mounts; portable atomic nonempty-directory claim protects a coherent filesystem only. Quickstarts use separate owner/job Volumes for concurrent runs (including HF_HOME isolation), or sequential shared Volume runs. GPU fingerprint keys hardware class/capabilities/runtime settings, not physical UUID, so same-class sequential reallocations remain reusable.

   Cost if wrong: Concurrent cache corruption or duplicated inference if the storage assumption is wrong.

15. Ruling: Task3 explicit native-label adapter may touch CLI/data/evaluation with fixture tests. Also match known external units_sha256 in compare (existing result field), retaining legacy unknown and generic pipeline semantics; no new comparison framework. This is small protocol consistency glue alongside known qrels hash check.

   Cost if wrong: Results could be compared under different label/ranking protocols; raw manifests permit diagnosis.

16. Ruling: preserve byte-exact archived bootstrap documents and explicitly exclude only their moved relative navigation links, while including their bytes in current hashes. Current report/spec/plan links remain checked.

   Cost if wrong: Archive navigation requires the original location or Git history; the narrow exclusion is visible in validation output.

17. Ruling: use private per-input snapshots for preparation provenance and coherent new output directories for prepared/shared-demo runs, as verified by the combined review fixes. Each hash identifies consumed bytes; the data owner still coordinates versions across independent source files.

   Cost if wrong: Snapshotting adds temporary disk and IO proportional to the inputs. A reused destination requires a new run path.

18. Ruling: preserve the pinned upstream scheduler and document its exact ten-effective-step limitation; preserve expected diagnostic output in passing tests instead of changing unrelated tests. The final suite exit codes and named skips remain authoritative.

   Cost if wrong: Both training controls need the same adjusted budget, and expected test noise requires careful log reading.

19. Ruling: retain first runnable publication evidence in the common bundle and write final remote-ref proof to the existing uncommitted research evidence, avoiding a cycle where recording a commit changes that same commit.

   Cost if wrong: The common registry describes the dated initial publication; the final research registry identifies the latest verified remote heads.

20. Ruling: accept the scoped review's two Minor residuals without a second code wave: abrupt POSIX publication termination can leave an empty destination, and malformed raw-input diagnostics can name the snapshot path. Keep them visible in the review and use new run paths.

   Cost if wrong: A forcibly interrupted run may need a new destination, and input-error diagnosis may require checking the original CLI arguments. Targeted WSL tests cover ordinary failures and racing writers, not process-kill recovery.
