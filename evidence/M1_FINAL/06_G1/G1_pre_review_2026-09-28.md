# G1 Pre-review — NEW-repository readiness

> **Status:** `PRE_REVIEW_REFRESHED_G1_FIRST_REVIEW_BLOCKED`
>
> **Owner:** Tấn Phát — Research Lead / Protocol & Gate Owner
>
> **Refreshed:** 28/09/2026
>
> **Source snapshot:** `origin/develop` `2e74b97e1836213f07510a4075c3b53389bd04c5`
>
> **Preparation branch:** `feature/tan-phat-m1-continuation` (not a selected G1 package)
>
> **Scope:** `INTERNAL_SOURCE_VERIFICATION_NOT_INDEPENDENT_QA`
>
> **Official G1 decision:** `NOT_RUN`
>
> **Execution authorization:** `CLOSED`

## Outcome

**Readiness is `BLOCKED_FOR_G1_FIRST_REVIEW`.** This refresh checks whether
M1.4–M1.8 evidence is reviewable in the NEW repository. It does not act for
Khương, Thanh, or the whole-team G1.

| Area | Current NEW evidence | Finding |
| --- | --- | --- |
| M1.4 | `m1.4-003` inventories 307 files but reports `PARTIAL`, zero data assets and unresolved provenance | `BLOCKED_PARTIAL_NOT_REVIEWABLE` |
| M1.5 | OLD freeze is restored to 9/9 matching hashes and its original package digest; A001/A002 Research Lead approvals are preserved separately with a NEW-relative candidate manifest | `BLOCKED_CANDIDATE_NOT_ADOPTED` |
| Split/data activation | ViDoSeek A002 70/15/15 policy exists, but exact ID manifests/hashes, source/qrels, overlap, cache and coverage evidence are absent | `BLOCKED_MISSING` |
| M1.6 | `m1.6-001` reports five documents/20 pages and `PASS_AUDIT`, but three payload hashes mismatch, five source PDFs are unresolved and full-corpus scope is unverified | `BLOCKED_INTEGRITY_AND_SCOPE` |
| M1.7 | Thanh's post-merge Draft has 14 events, 14 traces and 16 issues; Final binding is blocked | `BLOCKED_DRAFT_NOT_FINAL` |
| M1.8 | `m1.8-001` has four hash-valid payloads and provisional numeric thresholds; calibration or explicit G1 scope decision is pending | `BLOCKED_PROVISIONAL_SCOPE_UNDECIDED` |
| Independent audit | Thanh has a Draft source/hash audit and issue log, but no Final review of an adopted selected package | `BLOCKED_DRAFT_INDEPENDENT_AUDIT` |
| Final sign-offs | Technical Sign-off is `NOT SIGNED`; QA Sign-off is missing | `NOT_DUE_BEFORE_FIRST_REVIEW` |
| G1 preparation | Checklist/evidence/readiness documents refreshed by this sync | `READY_FOR_TEAM_REVIEW_AFTER_UPSTREAM_GATES` |
| Git/package provenance | Source base `2e74b97` is known; at this 28/09 drafting snapshot, preparation was uncommitted and no byte-identical G1 review package was selected | `SOURCE_BASE_IDENTIFIED_PACKAGE_NOT_SELECTED` |

## Pre-review blocker candidates

These are internal candidates, not entries in an official G1 blocker log.

| ID | Finding | Owner | Closure evidence |
| --- | --- | --- | --- |
| SYNC-PR-B01 | M1.4 revision remains `PARTIAL`, with zero data assets and provenance review pending | Khương | New immutable revision with actual assets or approved scope and reproducible hashes |
| SYNC-PR-B02 | A001/A002 approvals exist, but M1.5 has no complete adopted successor or independent acceptance | Tấn Phát + Thanh | Exact NEW-relative protocol/data/config hashes and Thanh's review of one selected package |
| SYNC-PR-B03 | Exact ViDoSeek split/data/cache/coverage evidence is missing | Khương + Tấn Phát | A002 ID manifests/hashes, source/qrel identities, overlap and readiness reports |
| SYNC-PR-B04 | M1.6 generated output is not byte-verifiable or proven full-corpus | Khương | Append-only revision with matching hashes, resolvable PDFs, reviewed scope and collision/leakage conclusion |
| SYNC-PR-B05 | M1.7 is a reconciled Draft, not Final independent review | Thanh | Final registry binding and re-audit of the adopted selected package |
| SYNC-PR-B06 | M1.8 thresholds are provisional and G1 scope is undecided | Khương + Tấn Phát | Representative calibration or explicit First Review scope decision, then namespace review |

After candidates `SYNC-PR-B01`–`SYNC-PR-B06` become reviewable, convening the
whole-team First Review is the next action, not another entry blocker. That review
creates the official blocker log and `G1_first_review_decision.md` (Decision
v1). `G1_final_decision.md` belongs to the later Final G1 gate.

## Safe action order

1. Complete the M1.5 successor identity and exact A002 split hashes without
   altering imported freeze bytes; obtain Thanh's independent review.
2. Khương supplies reviewable M1.4, split/data and corrected M1.6 evidence;
   Tấn Phát and Khương decide the M1.8 provisional-versus-calibrated scope.
3. Thanh freezes M1.7 against the adopted protocol and selected package after
   independent evidence re-audit.
4. Select and hash one final review package; refresh this Pre-G1 assessment.
5. Only when entry evidence is reviewable, convene G1 First Review and create the
   official blocker log and First Review decision.
6. Require Technical and QA Sign-offs before Final G1; keep execution separately
   authorized under the adopted run policy.

## Conclusion

The post-merge refresh makes current evidence and owner dependencies visible,
but it does not remove upstream blockers. G1 First Review remains `NOT_RUN` and
Final G1 remains `NOT_REACHED`; no PASS, scientific result, execution authority,
or M1 closure is implied.
