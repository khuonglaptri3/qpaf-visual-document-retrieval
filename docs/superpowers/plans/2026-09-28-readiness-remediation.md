# M1.1–M1.8 readiness remediation plan — 2026-09-28

Baseline: `765803fee5465006658de35a4272414b27a5bb53`. Authority: user-requested implementation of the readiness audit. Evidence and governance decisions remain separate from software completion. Historical signed/hashed bytes are preserved; publish new revisions and correction sidecars.

## 1. Fail closed on real-input audits (F01–F04)

- [x] Add failing regression tests for empty/missing inputs, corrupt PDFs, unknown documents/pages, partial-positive orphan qrels, duplicate/conflicting IDs and false PASS.
- [x] Wire actual PDF inventory/page counts through M1.3 and M1.6; require complete positive-target validation.
- [x] Make split verification read-only; reject duplicates, missing/unknown IDs and incomplete partitions.
- [x] Reconcile canonical page IDs and split interchange; measure query/document/content overlap separately.
- [x] Run focused tests and malicious/invalid-input CLI probes; record outputs before stating completion.

## 2. Runtime safeguards and OCR (F05–F06)

- [x] Connect authorization checks at launch and in callable execution stages.
- [x] Integrate native-text/OCR fallback, timeout, confidence/quality classification, error-rate stop, failure records and namespace metadata.
- [x] Preserve scope-specific preset identity; thresholds remain provisional until measured calibration.
- [x] Verify blocked execution and runtime failure cases without claiming full corpus OCR or research inference.

## 3. Real corpus and evidence revisions (F03, F08)

- [x] Locate or fetch pinned ViDoSeek annotation/PDF payloads into ignored/external storage; record license/revision/size/hash/location.
- [x] Run corrected CPU inventory, exact split generation/verification and real collision audit after task 1 passes.
- [x] Report all overlap and target failures honestly; retain fixed split identities and request policy review where required.
- [x] Publish new immutable M1.3/M1.6 revisions bound to commands, source/config hashes and actual input hashes.
- [x] Publish a new M1.4 snapshot after implementation and documents settle, excluding temporary files and identifying working-tree provenance accurately.

## 4. Contract and status correction (F07–F09; A01–A05)

- [x] Draft an evidence-scoped status correction and preserve historical bytes using adjacent notices.
- [x] Inventory exact current M1.1/M1.2 contract and distinguish it from legacy protocol and proposed learned scope.
- [x] Draft a repo-relative M1.5 successor package and append-only governance sidecar.
- [ ] Review/adopt effective dataset/evaluation unit, feature/rank/loss/model/depth/seed/metric/OCR choices with named owners.
- [ ] Resolve G1 OCR dependency schedule: proposed M1 policy review, M2.3 calibration, M2.6 full OCR.
- [ ] Bind final source/config/package identity, independent review and effective amendments before any freeze claim.

## 5. Verification and handoff

- [x] Run the full relevant suite with UTF-8 propagated to subprocesses and record exact pass/failure/skip counts.
- [x] Verify new manifests against bytes and preserve previous package hashes/results without modification.
- [x] Update the correction with actual completed implementation/evidence links and unresolved decisions.
- [ ] Complete independent member review, registry adoption/freeze and team G1/R1 decisions only through actual authorized governance records.

Dependency order: input validation → real corpus audit → fresh inventory; runtime safety can proceed independently; owner protocol/G1 decisions remain pending until a concrete package is reviewed. No task here authorizes inventing sign-offs or relabelling synthetic evidence as research results.
