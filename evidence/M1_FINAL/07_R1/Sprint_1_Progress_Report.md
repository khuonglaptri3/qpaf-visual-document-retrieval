# Sprint 1 Progress Report — current draft

> **Report status:** `DRAFT_CURRENT_G1_BLOCKED_CLOSURE_NOT_REACHED`
>
> **Period:** 23/09/2026 – 27/09/2026
>
> **Snapshot date:** 27/09/2026
>
> **Prepared by:** Tấn Phát — Research Lead / Protocol & Gate Owner
>
> **Source branch:** `sync/tanphat`
>
> **Integration base:** `0bc865e` (`origin/develop`)
>
> **Independent review:** `PENDING`
>
> **G1 First Review:** `NOT_RUN`
>
> **Final G1:** `NOT_REACHED`
>
> **M1 closure:** `NOT_REACHED`
>
> **Result-bearing execution:** `CLOSED`

This draft reflects the NEW repository after the bounded Tấn Phát
synchronization was committed as `c82dd5a` and reconciled with
`origin/develop`. The user's pre-existing untracked
`SYNC_TAN_PHAT_PROMPT.md` remains excluded. This branch is not a G1-selected
immutable review snapshot or protocol freeze commit. The report does not
authorize OCR, extraction, oracle, optimizer, training, Modal/GPU, or sealed
external evaluation.

## 1. Sprint objective

Sprint 1 prepares an auditable research starting point:

1. inventory source, data, configs, runs and hashes;
2. freeze and independently review a precise research protocol;
3. audit identity, duplicates, collisions, split leakage and qrels;
4. freeze experiment registry and traceability rules;
5. calibrate OCR failure handling and artifact namespace;
6. conduct G1 only from reviewable evidence;
7. report status, blockers, risks and the bounded path to the next milestone.

Scientific success in this sprint is not a positive QPAF number. The deliverable
is trustworthy preparation and governance for a future matched learned
QARF/QPAF comparison.

## 2. Current timeline position

The active date is 27/09/2026, the final day of M1 in `TIMELINE_fixed.md`.
The planned order is:

`Technical Sign-off + QA Sign-off → Final G1 → Final R1 → M1 closure`.

That chain is not satisfied in the available evidence. Schedule dates do not
override the artifact gates.

## 3. Tấn Phát task status

| Task | Current status | Evidence / limitation |
| --- | --- | --- |
| M1.5 Protocol Freeze | `PARTIAL_IN_NEW` | OLD `QPAF-M1.5-v1` bytes and hashes were imported; active NEW adoption, loss-contract reconciliation and independent review remain pending |
| G1 Checklist Preparation | `DONE_PREPARATION_ONLY` | Current checklist and 36-row evidence matrix exist; they do not constitute review |
| Pre-G1 | `DONE_BLOCKED_OUTCOME` | Current readiness matrix finds G1 First Review blocked |
| M1.9 G1 First Review | `NOT_RUN / BLOCKED` | Entry evidence, official blocker log and team decision are absent |
| M1.9 Final G1 | `NOT_REACHED` | Technical and QA Sign-offs are absent |
| M1.10 Progress Report | `CURRENT_DRAFT` | This file; independent review and Final G1 fields remain pending |
| M1 Closure | `NOT_REACHED` | No closure record is created before the required gate sequence |

## 4. Upstream evidence state

| Area | Owner | Current NEW state | Gate effect |
| --- | --- | --- | --- |
| M1.4 Repository Audit | Khương | `PARTIAL`; canonical files exist but research source/data/config assets remain missing | Not accepted for G1 |
| M1.5 Protocol | Tấn Phát | Historical freeze imported and byte-verified; active adoption blocked | M1.7 cannot bind an adopted NEW hash yet |
| M1.6 Collision Audit | Khương | `BLOCKED / NOT RUN`; CSVs are header-only | Collision/leakage state unknown |
| M1.7 Registry / QA | Thanh | Owner placeholder only | Traceability and independent audit missing |
| M1.8 OCR / Artifacts | Khương | Policies are Draft; Technical Sign-off `NOT SIGNED` | M1.8 and Final G1 blocked |
| Independent audit / Final QA | Thanh | No evidence audit, issue log, traceability matrix or QA Sign-off | First Review lacks audit evidence; Final G1 lacks QA Sign-off |

## 5. Evidence synchronized in this draft cycle

| Evidence | Classification | Current meaning |
| --- | --- | --- |
| `evidence/M1_FINAL/02_protocol/` nine Markdown files + manifest | Historical governance evidence | OLD freeze bytes verified; not automatically adopted in NEW |
| `02_protocol/sync_reconciliation.md` | Synchronization/adoption record | Documents path mapping, semantic conflict and successor requirements |
| `06_G1/G1_checklist.md` | Governance preparation | Current entry/final criteria; not reviewed outcome |
| `06_G1/G1_evidence_matrix.csv` | Governance preparation | 36 requirements mapped to paths, owners and current state |
| `06_G1/G1_pre_review.md` | Internal readiness assessment | `BLOCKED_FOR_G1_FIRST_REVIEW`; not independent QA |
| `06_G1/G1_readiness_matrix.csv` | Internal finding matrix | 14 current findings and required next actions |
| This report | M1.10 draft | Current status and handoff; not Final R1 or closure |

No `G1_blocker_log.md`, `G1_final_decision.md`, `qa_signoff.md`, learned
checkpoint, learned metric or `M1_closure_record.md` is listed because no such
qualifying artifact exists.

## 6. Current blocker candidates

The following are Pre-G1 candidates only. An official blocker log can be created
only when the team starts G1 review.

| ID | Blocker candidate | Owner | Closure evidence |
| --- | --- | --- | --- |
| SYNC-PR-B01 | M1.4 lacks reviewable research-asset inventories | Khương | New immutable audit revision with actual assets and reproducible hashes |
| SYNC-PR-B02 | Imported M1.5 is not adopted; loss contract conflicts with integrated M1.2 | Tấn Phát + Thanh | Successor/amendment, NEW-relative manifest and independent review |
| SYNC-PR-B03 | Exact split/data/cache/coverage evidence missing | Khương + Tấn Phát | ID/hash/overlap/readiness artifacts |
| SYNC-PR-B04 | M1.6 not run on real corpus | Khương | Populated audit and reviewed conclusion |
| SYNC-PR-B05 | M1.7 Final/traceability/audit missing | Thanh | Final registry and independent audit package |
| SYNC-PR-B06 | M1.8 remains Draft and lacks calibration evidence | Khương | Reviewed calibration/threshold/namespace evidence sufficient for First Review |

After `SYNC-PR-B01`–`SYNC-PR-B06` become reviewable, the team can convene First
Review. Technical and QA Sign-offs are required later, after blocker resolution and
recheck, for Final G1.

## 7. Scientific claim boundary

- The available ViDoSeek Oracle report is bounded upper-bound evidence and still
  lacks complete raw/per-query provenance in this integration target.
- The M1.2 handoff integrated in `develop` reports local synthetic method-core
  verification. It is not learned retrieval evidence.
- The imported OLD M1.5 policy is historical governance evidence, not proof that
  its ViMDoc data, candidates, loss, training or evaluation ran.
- No learned QPAF checkpoint, matched learned QARF comparison, confidence interval,
  confirmation result, external result or production-readiness claim exists here.

The research direction remains a future matched learned QPAF-versus-QARF test
under one adopted protocol. A valid negative result is acceptable; evidence gates
must not be weakened to obtain a positive result.

## 8. Risks

| Risk | Impact | Control / stop rule | Owner |
| --- | --- | --- | --- |
| Historical protocol is mistaken for active NEW adoption | Invalid registry/run contract | Keep imported bytes historical; require successor/amendment and review | Tấn Phát + Thanh |
| Partial/placeholder artifacts are treated as completed | Premature G1/M1 PASS | Use artifact states and independent review, not file existence or dates | Whole team |
| Oracle or synthetic core evidence is overstated | Invalid scientific claim | Keep `oracle_upper_bound`, software verification and learned results separate | Tấn Phát + Thanh |
| Schedule pressure bypasses sign-offs | Untraceable closure | Final G1 and closure remain blocked until both named sign-offs exist | Whole team |
| Other members' Draft work is silently imported | Ownership and architecture conflict | Synchronize only interfaces/status; owners finalize their tasks | Tấn Phát |

## 9. Required next work

1. Tấn Phát and Thanh resolve the method/loss contract and create an adopted
   NEW-relative M1.5 successor or approved amendment.
2. Khương produces a reviewed M1.4 revision with actual research assets, exact
   split/data evidence, real M1.6 results and calibrated M1.8 evidence.
3. Thanh freezes M1.7 against the adopted protocol and completes independent
   traceability/evidence audit.
4. The team selects one byte-identical package and conducts G1 First Review.
5. Official non-PASS findings go into `G1_blocker_log.md`; resolved evidence is
   rechecked before Technical and QA Sign-offs.
6. Tấn Phát issues Final G1 only after both sign-offs, then updates this report
   to Final and creates an M1 closure record if the gate permits closure.

## 10. Authorization and compute ledger

| Activity | Current authority | Observed execution in this sync |
| --- | --- | --- |
| Documentation/provenance synchronization | Authorized by the sync request | Local file inspection, hashing and validation only |
| OCR/extraction/oracle result run | Not granted | `NOT_RUN` |
| Learned QARF/QPAF training or evaluation | Not granted | `NOT_RUN` |
| Modal/GPU/external sealed evaluation | Not granted | `NOT_RUN` |

## 11. Pending final fields

| Field | Draft value |
| --- | --- |
| G1 First Review decision | `NOT_RUN` |
| Official blocker log | `NOT_CREATED_REVIEW_NOT_RUN` |
| G1 Recheck | `NOT_REACHED` |
| Technical Sign-off | `NOT_SIGNED` |
| Independent QA Sign-off | `MISSING` |
| Final G1 decision | `NOT_REACHED` |
| Final Progress Report | `PENDING_FINAL_G1` |
| M1 closure | `NOT_REACHED` |

## 12. Sign-off state

| Role | State | Evidence |
| --- | --- | --- |
| Report owner — Tấn Phát | `DRAFT_PREPARED` | This file; independent review pending |
| Technical owner — Khương | `NOT_SIGNED` | `../05_ocr_artifacts/technical_signoff.md` |
| Independent QA — Thanh | `MISSING` | No QA Sign-off exists in NEW |
| G1 team | `NOT_CONVENED` | Entry evidence remains blocked |

This file becomes Final only after the official gate evidence is inserted, paths
and hashes are refreshed, an independent reviewer is recorded, and the selected
package is frozen. Until then, M1 remains open.
