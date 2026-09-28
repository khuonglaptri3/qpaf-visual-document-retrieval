# M1 readiness correction and remediation record — 2026-09-28

Status: `WORKING_CORRECTION_REVIEW_PENDING`. Baseline inspected: `765803fee5465006658de35a4272414b27a5bb53` (`develop`). This record corrects interpretation of earlier evidence; it is not a named member's approval, a protocol adoption, a G1 decision, or an M1 closure.

The [readiness audit](m1.1-m1.8-readiness-audit-2026-09-28.md) is the source of findings F01–F09 and actions A01–F07. Dates and passing software tests do not establish corpus readiness. Original documents and historical evidence remain unchanged. Adjacent correction sidecars direct readers here so signed or hashed bytes retain their original identity.

## Corrected evidence matrix

| Item / owner | Evidence that exists | Supported scope | Remaining acceptance evidence |
|---|---|---|---|
| M1.1 / Thanh | [Historical report and source manifest](../results/m1.1/README.md); new Oracle pipeline and exported software fixture | Historical feasibility accepted in its original scope; reproduction and independent review **unverified**. New solver is a distinct study | Historical input/cache/config provenance and per-query reproduction review, or an explicitly separate new Oracle study |
| M1.2 / Phát | [Status](m1.1-m1.2-status.md), local `synthetic_software_verification` and completion receipt | Synthetic method-core verification; no learned real-data retrieval result | Another member's acceptance, and a separately approved learned-study protocol before research claims |
| M1.3 / Khương | [m1.3-001 audit report](../evidence/revisions/m1.3-001/audit_report.json) & [splits](../evidence/revisions/m1.3-001/splits/); read-only verifier | Real corpus verified: 292 PDFs, 5,385 pages, 1,142 queries, positive qrels bound, zero-leakage splits | Independent review of real corpus splits and qrels |
| M1.4 / Khương | [m1.4-004](../evidence/revisions/m1.4-004/audit_metadata.json): 631 files (28 source, 295 data, 2 config, 227 run) | Current repository snapshot excluding temporary files; verified 631/631 hashes | Independent review of provenance links |
| M1.5 / Phát; Thanh review | Historical protocol; ledger records A001/A002 as `APPROVED`; [m1.5-002 draft](../evidence/revisions/m1.5-002/README.md) | Recorded amendments plus proposed implementation reconciliation | Owner adoption, exact final implementation/config identity, independent reviewer and approved effective contract |
| M1.6 / Khương | [m1.6-002 report](../evidence/revisions/m1.6-002/collision_report.md) & [summary](../evidence/revisions/m1.6-002/collision_summary.json) | Real corpus audit: 292 docs, 5,385 pages, 1,142 queries, 0 leakage, 0 orphan queries; 205 shared docs (`REVIEW_REQUIRED_OVERLAP`) | Team review of document/content overlap policy for shared retrieval corpus |
| M1.7 / Thanh | [Registry package](../evidence/M1_FINAL/04_experiment_registry/README.md), traceability, issue log and evidence audit | Draft governance exists; no longer a placeholder. `DRAFT_NOT_FROZEN`; independent QA not established | Bind the adopted protocol and selected evidence hashes; named independent review and final registry freeze |
| M1.8 / Khương | [m1.8-001 policy revision](../evidence/revisions/m1.8-001/ocr_failure_threshold.md) and software helpers | Preparation policy with **PROVISIONAL** thresholds; mock text checks do not calibrate OCR | Review M1 policy scope; calibration scheduled M2.3, full OCR M2.6; integrated runtime evidence tracked separately |

This matrix records the baseline correction. Later remediation outputs must be linked with their exact revision and verification result before any row is promoted. A local implementation change alone does not close owner review or real-corpus acceptance.

## Corrections to previous claims

1. `m1-restart-handoff.md`, `khuong-m1-checklist.md` and `m1.4-m1.5-m1.6-audit-report.md` overstate M1.6 when they treat the fixture as a completed primary-corpus audit or as G1-COL evidence. Those conclusions are withdrawn for the real corpus. The recorded fixture result remains historical software evidence.
2. The 27 September G1/R1 descriptions of missing code/config and an M1.7 placeholder describe their old snapshot. Source/config and Draft registry artifacts now exist. Their existence does not confer independent QA, sign-off, adoption or freeze.
3. The historical M1.5 manifest describes pre-amendment bytes. The readiness audit found 8/9 Markdown hashes match current files; A001/A002 are recorded amendments, not proof that the complete current implementation has been adopted. The old manifest is preserved.
4. The readiness audit found 2/5 M1.6-001 hashes match current bytes; the three CSV differences are explained by LF/CRLF reproduction. Preserve those bytes and publish an explicitly new revision; do not rewrite historical hashes to obtain a passing check.
5. M1.4-003 reports its historical inventory, including a temporary artifact with incomplete source-commit provenance. A new snapshot must exclude temporary files and identify committed inputs versus a recorded working-tree state. It must not retrospectively certify the old snapshot.
6. A002's label-free query splitting does not establish zero document/content overlap. Record all three overlap levels and a reviewable handling decision. Never silently repartition after examining metric outcomes.

## F03: real-input completeness acceptance contract

The M1.3/M1.6 path must inventory actual PDFs, open each PDF to obtain its page count, reject unreadable/empty inputs, and pass the complete document/page inventory to annotation validation. Every positive qrel target must resolve to one known document and an in-range one-based page. A query with one valid target and another missing target is invalid. Report missing documents, invalid pages, unknown aliases and conflicting duplicate IDs explicitly. A successful CLI exit requires validated nonempty coverage, not an empty list of detected errors.

Split verification must read the submitted artifacts without rewriting them, reject duplicate/unknown/missing IDs, compare complete partitions to the expected corpus, and preserve input bytes on both success and failure. Query-disjoint splits remain distinct from document/content-disjoint splits. The selected policy and every actual overlap must appear in new corpus evidence.

## A01–A05: decisions and deliverables

| Action | Deliverable in this correction | State / required decision |
|---|---|---|
| A01 | Corrected matrix, adjacent notices and append-only [governance sidecar](../evidence/revisions/m1.5-002/governance_events.jsonl) | Correction issued for review; no historical evidence modified |
| A02 | Separate ViDoSeek primary/page-level proposal, Oracle discovery, learned development and future ViMDoc confirmation/document-level scope in [successor contract](../evidence/revisions/m1.5-002/scoped_contract.md) | A002 primary-dataset ledger entry retained; full evaluation-role adoption remains pending Phát/Thanh |
| A03 | Exact feature/rank/loss/normalization/model/top-K/seed/metric behavior and explicit historical differences | Current implementation inventoried; proposed effective reconciliation awaits review, learned-run settings not inferred from a software preset |
| A04 | Proposed M1 review of provisional OCR policy; calibration M2.3 and full OCR M2.6 | Team must record the effective G1 requirement. The old calibration-before-First-Review wording is disputed, not silently accepted or replaced |
| A05 | New repo-relative draft contract, source/config hashes, package manifest and governance event | Draft successor exists; independent review, effective amendment ID and freeze/adoption remain pending |

## G1 and R1 interpretation

G1 First Review remains `NOT_RUN` and Final G1/M1 closure remain `NOT_REACHED` in the available governance records. Technical Sign-off and QA Sign-off are not issued by this correction. Real-data readiness, scientific claims and permission for a specific execution are separate records. Neither a draft contract nor a passing test changes the team's gate decision.

Proposed dependency order: review provisional OCR policy at M1; calibrate measured thresholds at M2.3; perform full OCR at M2.6. Phát and Thanh must reconcile that schedule with G1's older entry checklist and record any accepted change. Do not require an unapproved M2 output as an M1 entry condition, and do not claim this proposal has already changed G1.

## Outstanding decisions

- Phát: adopt or amend the scoped protocol, including the precise learned experiment candidate depth, feature/rank normalization, seeds, metric unit and OCR preset.
- Thanh: independently review source/config identity, A001/A002 effects, candidate/ID/qrel mapping, statistical scope and the proposed successor; decide registry freeze only after evidence is bound.
- Khương with Phát/Thanh: document real-corpus overlap handling and calibrated OCR scope when measurements exist.
- Whole team: record G1 entry requirements, conduct the review, resolve its blockers and issue actual sign-offs/decisions in the required order.

Implementation and verification tracking is in the [remediation plan](superpowers/plans/2026-09-28-readiness-remediation.md). No box is marked complete merely because a document was drafted.
