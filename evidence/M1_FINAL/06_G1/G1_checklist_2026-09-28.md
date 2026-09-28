# G1 Checklist v2 — NEW-repository preparation

> **Document status:** `PREPARED_NOT_TEAM_REVIEWED`
>
> **Owner:** Tấn Phát — Research Lead / Protocol & Gate Owner
>
> **Refreshed:** 28/09/2026 against `origin/develop` `2e74b97`
>
> **Current readiness:** `BLOCKED_FOR_G1_FIRST_REVIEW`
>
> **Execution authorization:** `CLOSED`

This checklist maps the timeline's G1 requirements to the NEW repository. It is
preparation, not an official G1 review, blocker log, Final G1 decision, Technical
Sign-off, QA Sign-off, or execution authorization.

## Review vocabulary

| Status | Meaning |
| --- | --- |
| `PASS` | The required artifact and semantics were independently reviewed and accepted. |
| `PARTIAL` | Real evidence exists but remains incomplete; owner and closure criterion are required. |
| `BLOCKED` | A mandatory dependency/evidence item prevents review or decision. |
| `FAIL` | Reviewable evidence violates an acceptance criterion. |
| `NOT_REVIEWED` | No qualifying review has occurred; never interpret as PASS. |

## Entry criteria for G1 First Review

- [ ] M1.4 has a selected, reproducible audit revision whose inventories reflect
      actual research source, data, configs and runs sufficiently for team review.
- [ ] M1.5 has an active NEW-repository protocol version. The imported OLD freeze
      is hash-valid historical evidence but remains pending adoption/reconciliation.
- [ ] M1.6 contains real page/alias/duplicate/collision and split-leakage results.
- [ ] M1.7 is Final, bound to the adopted protocol hash, and includes traceability.
- [ ] M1.8 contains calibrated, reviewed threshold/namespace evidence or an
      explicit team scope decision on provisional thresholds for First Review.
- [ ] Thanh has completed an independent evidence audit and issue log.
- [ ] The review package has a selected commit/snapshot and reproducible hashes.

If any mandatory entry criterion is missing, readiness is `BLOCKED`. The team may
triage candidates, but it must not call that activity a G1 PASS.

## M1.4 — Repository Audit

- [ ] `repo_inventory.csv` identifies actual research modules and status.
- [ ] `data_inventory.csv` records dataset identity/revision/location/availability.
- [ ] `config_inventory.csv` maps configs to task/method/adoption state.
- [ ] `run_inventory.csv` classifies historical and current runs without promoting
      anonymous or fixture-only outputs.
- [ ] `git_snapshot.txt`, `hash_manifest.csv`, and `gap_log.md` identify the exact
      reviewed revision and unresolved owners/closure criteria.

Current NEW state: `m1.4-003` inventories 307 files (20 source, 0 data, 2
config, 225 run entries) but declares `PARTIAL`; data and provenance gaps remain.
This is not an accepted complete M1.4 package.

## M1.5 — Frozen Protocol

- [x] Nine imported Markdown files match the OLD freeze manifest byte-for-byte
      after restoring the original ledger from import commit `c82dd5a`.
- [x] The historical canonical package digest recomputes exactly.
- [x] The imported manifest records dirty/uncommitted source provenance,
      independent sign-off pending, and `execution_authorized=false`.
- [x] A001/A002 Research Lead approvals are preserved in the separate
      post-import ledger; A001 identifies the pairwise method-core reference.
- [ ] Tấn Phát has completed a reviewed NEW successor learned-training contract,
      including model/config/candidate/seed decisions and exact A002 split hashes.
- [ ] A NEW-relative manifest binds the adopted implementation/config and paths.
- [ ] Thanh has independently reviewed the adopted byte-identical package.

Historical import and Research Lead approval are not active adoption. The
[`adoption readiness`](../02_protocol/adoption_readiness.md) document and
[`candidate manifest`](../02_protocol/protocol_adoption_candidate.json) name the
remaining identities and reviewer gate.

## M1.6 — Collision and Split Integrity

- [ ] Page and alias manifests contain hash-valid real corpus rows and
      resolvable source identities for the selected scope.
- [ ] Duplicate/collision analysis covers the protocol-selected corpus and
      has independently reproducible payload hashes.
- [ ] Exact ViDoSeek train/val/test ID manifests and hashes, counts and union
      are recorded under A002's 70/15/15 label-free split with zero query overlap.
- [ ] Document overlap, qrel consistency, orphan records, and serious collisions
      are measured and resolved or explicitly blocking.

Current NEW state: `m1.6-001` has populated output and a generated
`PASS_AUDIT` report for five documents/20 pages, but three payload hashes
mismatch, five source PDFs are unavailable and full-corpus scope is unverified.
The report cannot establish a G1 collision/leakage PASS.

## M1.7 — Registry and Independent Evidence

- [ ] Registry/naming/classification/append-only rules are Final.
- [ ] Registry records the adopted protocol path/hash and controlled vocabulary.
- [ ] `traceability_matrix.csv` supports a sample end-to-end trace.
- [ ] `evidence_audit.md` and `issue_log.csv` record Thanh's independent review.
- [ ] Result-bearing records bind approval, commit, config/data/output hashes and
      a truthful claim boundary.

Current NEW state: Thanh's reconciled Draft contains 14 registry events, 14
traces, an evidence audit and 16 issues. It is not M1.7 Final or a Final QA
sign-off; the adopted M1.5 package and selected evidence snapshot are missing.

## M1.8 — OCR and Artifact Governance

- [ ] OCR routing/calibration rules were validated against representative data.
- [ ] Failure thresholds are numerical, evidence-backed and fail closed.
- [ ] Artifact namespace matches the Final registry and adopted protocol.

Current NEW state: revision `m1.8-001` has four hash-valid payloads and numeric
thresholds labeled `PROVISIONAL`. Representative calibration is deferred to
M2.3; Tấn Phát and Khương must record whether provisional policy is sufficient
for First Review or calibration is required before it.
Technical Sign-off is `NOT SIGNED`, but it is a later Final G1 prerequisite rather
than an entry criterion for First Review.

## Cross-cutting checks

- [ ] Oracle W7/W66 stays labeled bounded `oracle_upper_bound`, not learned evidence.
- [ ] M1.2 local/synthetic method-core verification is not reported as training or
      learned retrieval improvement.
- [ ] QARF/QPAF comparison uses one adopted loss/features/candidate/evaluation
      contract and differs only by declared gate granularity.
- [ ] Candidate construction is label-free; qrels join only after candidate freeze.
- [ ] Metric, seed, latency, memory, finite-value and reload-parity evidence paths
      are real or explicitly `NOT_RUN/BLOCKED`, never estimates presented as results.
- [ ] Protocol/G1 documentation does not authorize OCR, extraction, optimizer,
      training, Modal/GPU, oracle, or external-evaluation execution.

## G1 review procedure

1. Select and hash one byte-identical review package.
2. Thanh independently audits evidence; Khương owns technical/data responses;
   Tấn Phát coordinates the gate without replacing either sign-off.
3. At the official review, create a new reviewed matrix version from
   `G1_evidence_matrix_2026-09-28.csv` with verifier/timestamp; keep this
   preparation matrix unchanged.
4. Create and append official non-PASS items to `G1_blocker_log.md` only after
   review starts.
5. Issue G1 Decision v1 in `G1_first_review_decision.md` only after reviewing
   the evidence and official blocker log. Reserve `G1_final_decision.md` for the
   later Final G1 review after both sign-offs.
6. Keep execution authorization separate from every G1 outcome.

## Additional criteria for Final G1

- [ ] Every critical blocker has closure evidence or forces an explicit non-PASS
      final decision.
- [ ] Khương has signed the final Technical evidence package.
- [ ] Thanh has signed final independent QA and a sampled end-to-end trace.
- [ ] Protocol, registry, evidence and sign-off hashes refer to the same package.
- [ ] `G1_final_decision.md` records decision, rationale, limitations, remaining
      risks, sign-offs, timestamp and owner.

## Current conclusion

Preparation is refreshed against the 28/09 post-merge evidence, but none of the
seven entry criteria is fully satisfied.
G1 First Review remains `NOT_RUN`; current readiness is
`BLOCKED_FOR_G1_FIRST_REVIEW`.
