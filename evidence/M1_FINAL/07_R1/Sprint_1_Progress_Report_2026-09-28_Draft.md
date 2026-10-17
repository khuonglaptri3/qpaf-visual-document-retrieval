# Sprint 1 Progress Report — post-merge draft

> **Status:** `DRAFT_REFRESHED_G1_BLOCKED_CLOSURE_NOT_REACHED`
> **Period:** 23/09/2026–27/09/2026; evidence refresh 28/09/2026
> **Document owner:** Tấn Phát — Research Lead / Protocol & Gate Owner
> **Source snapshot:** `origin/develop` `2e74b97e1836213f07510a4075c3b53389bd04c5`
> **Preparation branch:** `feature/tan-phat-m1-continuation`; no selected immutable G1 package
> **Independent review:** `PENDING`
> **G1 First Review:** `NOT_RUN`; **Final G1:** `NOT_REACHED`
> **Result-bearing execution:** `CLOSED`; **M1 closure:** `NOT_REACHED`

This draft updates the Tấn Phát timeline against the 28/09 post-merge
repository evidence. Planned dates are not acceptance evidence. It is an
internal status report, not a team G1 decision, Final R1, sign-off, or approval
to run extraction, Oracle, learned training/evaluation, Modal/GPU, or an external
benchmark.

## 1. Sprint objective and task status

Sprint 1 aims to establish a reviewable source/data inventory, adopted research
protocol, collision and split evidence, experiment registry, OCR/artifact policy,
and a whole-team G1 decision before any M1 closure claim.

| Tấn Phát task | Current status | Evidence and remaining work |
| --- | --- | --- |
| M1.5 historical freeze | `IMPORTED_AND_BYTE_VERIFIED` | Nine OLD Markdown files and the package digest again match the OLD manifest. This is historical evidence, not NEW adoption. |
| M1.5 A001/A002 and successor | `RESEARCH_LEAD_APPROVED_CANDIDATE_BLOCKED` | Both approvals are preserved in `../02_protocol/amendments_after_import.md`; a NEW-relative candidate binds reference source/config hashes. Exact ViDoSeek split/data hashes, learned contract and independent review remain missing. |
| G1 checklist and evidence mapping | `PREPARATION_REFRESHED` | Checklist, 36-row evidence matrix and 14-row readiness matrix now reflect the 28/09 source snapshot. They are not team review outcomes. |
| Pre-G1 | `REFRESHED_BLOCKED_FOR_FIRST_REVIEW` | `../06_G1/G1_pre_review_2026-09-28.md` records current owner gaps and internal candidates only. |
| M1.9 G1 First Review | `NOT_RUN` | No selected review package, official blocker log or `G1_first_review_decision.md` exists. |
| M1.9 blocker fix/recheck and Final G1 | `NOT_REACHED` | These require official First Review findings, owner fixes, recheck and both named sign-offs. |
| M1.10 report | `CURRENT_DRAFT` | This document is refreshed; Final R1 depends on Final G1 and independent report review. |
| M1 closure | `NOT_REACHED` | No closure record has been created. |

## 2. Current evidence and dependencies

| Area | Owner | Observed 28/09 evidence | Effect on Tấn Phát's gate work |
| --- | --- | --- | --- |
| M1.4 repository audit | Khương | `m1.4-003` inventories 307 files, but metadata says `PARTIAL`, data count 0 and provenance review required | A new selected revision or explicit approved scope is needed before First Review. |
| M1.5 protocol | Tấn Phát; independent review by Thanh | A001 pairwise loss and A002 ViDoSeek primary are Research Lead approved. Historical freeze is byte-valid; the NEW candidate is not adopted. | Exact affected data/split and learned-config identities plus independent package review are needed. |
| ViDoSeek data/split | Khương + Tấn Phát | Pinned dataset revision and 70/15/15 label-free algorithm are documented, but no exact ID manifests, source/qrel/cache hashes, overlap or coverage review are present. | No data-ready training/evaluation contract can be asserted. OLD ViMDoc split counts do not apply to A002. |
| M1.6 collision audit | Khương | `m1.6-001` reports five documents/20 pages and `PASS_AUDIT`; three declared payload hashes mismatch, five source PDFs are unavailable and selected-corpus scope is unverified. | The generated PASS label cannot be used as G1 acceptance; a corrected append-only revision and review are needed. |
| M1.7 registry and audit | Thanh | Reconciled Draft has 14 events, 14 traces, 16 issues and a source/hash audit; `DRAFT_RECONCILED_FINAL_BLOCKED`. | Thanh must independently bind and review one adopted M1.5/evidence package; Final QA is absent. |
| M1.8 OCR/artifact policy | Khương + Tấn Phát for scope | `m1.8-001` has four hash-valid payloads and provisional numerical thresholds; representative calibration is deferred to M2.3. | An explicit G1 First Review scope decision or calibration is required. Technical Sign-off is still `NOT SIGNED`. |

The 27/09 G1 and R1 snapshots have been refreshed here for current-state
reporting. Historical M1.7 issue rows remain append-only; their later findings
`M17-ISS-011`–`M17-ISS-016` describe the post-merge gaps.
Thanh's Draft rows that cite the 28/09 amendment bytes at the OLD ledger path
must be superseded by new rows pointing to the separate post-import ledger;
Tấn Phát has not changed Thanh's historical records.

## 3. Protocol integrity and claim boundary

The 28/09 amendment commit placed A001/A002 inside the OLD freeze's
hash-addressed `protocol_amendments.md`, invalidating one of nine recorded
hashes. This preparation restores that historical file byte-for-byte from
import commit `c82dd5a` and preserves the approved entries in
`../02_protocol/amendments_after_import.md`. The restored 9/9 hashes and
historical package digest verify; the separate candidate manifest is explicitly
`PREPARED_BLOCKED_NOT_ADOPTED`. No amendment evidence is discarded or treated as
an independent sign-off.

M1.1 W7/W66 remains bounded `oracle_upper_bound` evidence, with historical
per-query reproduction limitations. M1.2 pairwise method-core checks are local
software evidence, not a trained QPAF model or learned retrieval gain. M1.3 and
M1.6 software checks do not establish complete live-corpus data readiness.
No learned QPAF checkpoint, matched learned QARF comparison, confirmation
result, confidence interval or deployable result is claimed.

## 4. Pre-G1 findings and official gate order

The internal candidate groups are: M1.4 data/provenance (`SYNC-PR-B01`), M1.5
successor and independent review (`B02`), exact ViDoSeek split/data readiness
(`B03`), M1.6 hash/source/scope repair (`B04`), M1.7 Final independent binding
(`B05`), and M1.8 provisional-versus-calibrated G1 scope (`B06`). These are
**not** entries in an official `G1_blocker_log.md`.

1. Khương supplies selected, reproducible M1.4, split/data and M1.6 evidence;
   Tấn Phát and Khương record the M1.8 scope decision.
2. Tấn Phát completes the NEW M1.5 successor and hashes; Thanh independently
   reviews it and freezes M1.7 against the same selected package.
3. The team selects one immutable review snapshot and conducts G1 First Review.
   Only that review creates the official blocker log and Decision v1 in
   `G1_first_review_decision.md`.
4. Owners address official blockers; the team rechecks closure evidence.
5. Khương supplies Technical Sign-off and Thanh supplies Final QA Sign-off before
   Tấn Phát issues any Final G1 decision.
6. Only then may Tấn Phát prepare Final R1 and an M1 closure record if the
   documented gate result permits it.

Neither a future G1 result nor this report automatically authorizes a
result-bearing invocation. The adopted run policy requires a separate exact
authorization record.

## 5. Pending final fields

| Field | Current value |
| --- | --- |
| Adopted NEW M1.5 version and independent review | `PENDING` |
| Selected immutable G1 package | `NOT_SELECTED` |
| G1 First Review decision and official blocker log | `NOT_RUN` / `NOT_CREATED` |
| G1 Recheck | `NOT_REACHED` |
| Khương Technical Sign-off | `NOT_SIGNED` |
| Thanh Final QA Sign-off | `NOT_CREATED` |
| Final G1 decision | `NOT_REACHED` |
| Final R1 independent review | `PENDING_FINAL_G1` |
| M1 closure | `NOT_REACHED` |

This report remains a Draft until the official gate evidence, exact paths and
hashes, independent review and final decision can be recorded truthfully.
