# G1 Pre-review — NEW-repository readiness

> **Status:** `PRE_REVIEW_REFRESHED_G1_FIRST_REVIEW_BLOCKED`
>
> **Owner:** Tấn Phát — Research Lead / Protocol & Gate Owner
>
> **Reviewed:** 27/09/2026
>
> **Source branch:** `sync/tanphat`
>
> **Base commit:** `3df0016`
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
| M1.4 | Canonical files and metadata exist; status `PARTIAL`; research source/data/config inventories are empty | `BLOCKED_PARTIAL_NOT_REVIEWABLE` |
| M1.5 | OLD freeze imported; 9/9 protocol hashes and package digest verify | `BLOCKED_PENDING_NEW_ADOPTION_AND_INDEPENDENT_REVIEW` |
| Split/data activation | Exact split IDs/hashes, overlap, live cache and coverage evidence absent | `BLOCKED_MISSING` |
| M1.6 | Header-only CSVs; report says `BLOCKED / NOT RUN` | `BLOCKED_NOT_RUN` |
| M1.7 | Owner placeholder only | `BLOCKED_MISSING` |
| M1.8 | Three Draft policies; calibration evidence and numerical thresholds are missing | `BLOCKED_DRAFT_UNCALIBRATED` |
| Independent audit | No evidence audit, issue log or traceability matrix | `BLOCKED_MISSING` |
| Final sign-offs | Technical Sign-off is `NOT SIGNED`; QA Sign-off is missing | `NOT_DUE_BEFORE_FIRST_REVIEW` |
| G1 preparation | Checklist/evidence/readiness documents refreshed by this sync | `READY_FOR_TEAM_REVIEW_AFTER_UPSTREAM_GATES` |
| Git/package provenance | Dedicated sync branch exists; working tree intentionally contains uncommitted sync files and the user's untracked prompt | `NOT_A_FINAL_REVIEW_SNAPSHOT` |

## Pre-review blocker candidates

These are internal candidates, not entries in an official G1 blocker log.

| ID | Finding | Owner | Closure evidence |
| --- | --- | --- | --- |
| SYNC-PR-B01 | M1.4 lacks reviewable research-asset inventories | Khương | New immutable audit revision with actual assets and reproducible hashes |
| SYNC-PR-B02 | Imported M1.5 is not adopted and conflicts with the pending M1.2 loss contract | Tấn Phát + Thanh | Successor/amendment, NEW-relative manifest and independent review |
| SYNC-PR-B03 | Exact ViMDoc split/data/cache/coverage evidence is missing | Khương + Tấn Phát | ID manifests/hashes, overlap and readiness reports |
| SYNC-PR-B04 | M1.6 has not run on the real corpus | Khương | Populated manifests/report with collision/leakage conclusion and review |
| SYNC-PR-B05 | M1.7 Final, traceability and evidence audit are missing | Thanh | Final registry package bound to adopted M1.5 plus audit artifacts |
| SYNC-PR-B06 | M1.8 remains Draft and lacks calibration evidence | Khương | Reviewed calibration/threshold/namespace evidence sufficient for First Review |

After candidates `SYNC-PR-B01`–`SYNC-PR-B06` become reviewable, convening the
whole-team First Review is the next action, not another entry blocker. That review
creates the official blocker log and G1 Decision v1.

## Safe action order

1. Resolve/adopt the active M1.5 method contract without altering imported bytes.
2. Khương supplies reviewable M1.4, split/data, M1.6 and calibrated M1.8 evidence.
3. Thanh freezes M1.7 and performs independent evidence audit.
4. Select and hash one final review package; refresh this Pre-G1 assessment.
5. Only when entry evidence is reviewable, convene G1 First Review and create the
   official blocker log/decision.
6. Require Technical and QA Sign-offs before Final G1; keep execution separately
   authorized under the adopted run policy.

## Conclusion

The synchronization makes Tấn Phát's preparation visible in the NEW repository,
but it does not remove upstream blockers. G1 First Review and Final G1 remain
`NOT_RUN`; no PASS, scientific result, execution authority, or M1 closure is implied.
