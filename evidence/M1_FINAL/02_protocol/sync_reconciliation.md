# M1.5 synchronization reconciliation

## Status and scope

- Import date: 27/09/2026
- NEW branch: `sync/tanphat`
- NEW integration base: `0bc865e` (`origin/develop`)
- Source repository: `C:\Users\HP\OneDrive\tlcn`
- Source package: `M1_FINAL/02_protocol/`
- Imported destination: `evidence/M1_FINAL/02_protocol/`
- Import status: `HISTORICAL_BYTES_VERIFIED_ACTIVE_ADOPTION_BLOCKED`
- Result-bearing execution: `CLOSED`

This record is outside the OLD freeze manifest. It documents the synchronization
without modifying any hash-addressed source file.

## What was preserved

The following files were copied byte-for-byte and rehashed after transfer:

1. `baseline_policy.md`
2. `candidate_policy.md`
3. `dataset_split_policy.md`
4. `frozen_protocol.md`
5. `metric_policy.md`
6. `protocol_amendments.md`
7. `run_policy.md`
8. `seed_policy.md`
9. `statistical_policy.md`
10. `protocol_freeze_manifest.json`

The manifest's nine protocol-file hashes and canonical package digest therefore
remain historical identifiers for the OLD package. Its 14 `source_evidence`
hashes identify files in the OLD checkout; they are not assertions about files
with similar names in the NEW checkout.

## OLD-to-NEW path mapping

| OLD manifest prefix | Imported NEW prefix | Meaning |
| --- | --- | --- |
| `M1_FINAL/02_protocol/` | `evidence/M1_FINAL/02_protocol/` | Byte-identical historical protocol package |
| `M1_FINAL/04_experiment_registry/` | No adopted equivalent; NEW has only `evidence/M1_FINAL/04_experiment_registry/README.md` | Thanh-owned external dependency remains missing |
| Root-level `TIMELINE_fixed.md`, `Tasks.md`, `Context.md`, configs and artifacts | No identity mapping | OLD source evidence; do not reinterpret as NEW current-state evidence |

## Reconciliation findings

### Method contract conflict

The OLD M1.5 package specifies a masked listwise loss for the planned ViMDoc
learned study. The M1.2 handoff integrated in `origin/develop` at merge
`0bc865e` (feature commit `7a758e3`) documents a `pairwise_logistic` loss for
the page-level synthetic method core. Those artifacts have different scopes,
but they cannot both serve as the same active learned-training contract without
an explicit decision.

The integrated ViDoSeek M1.1 settings—ColQwen2-v1.0, top-100 and a
software-verification seed—also must not be substituted for the OLD ViMDoc
M1.5 settings—ColQwen2.5, top-200 per channel and three training seeds. M1.1,
M1.2 and M1.5 evidence remain separately labeled.

### Missing adoption evidence

- Exact ViMDoc train/validation/confirmation ID files, hashes and overlap report
  do not exist in the NEW package.
- M1.4 remains `PARTIAL`; research source, data and config assets are missing.
- M1.6 is `BLOCKED / NOT RUN` on the real corpus.
- M1.7 Final, traceability and independent evidence audit are missing.
- M1.8 policies are Draft and Technical Sign-off is `NOT SIGNED`.
- No independent reviewer has accepted the imported M1.5 package in NEW.

## Adoption rule

Do not edit the imported hash-addressed files to make them look current. Active
adoption requires all of the following:

1. Tấn Phát records an explicit decision resolving the loss/config contract and
   issues a successor protocol version or approved append-only amendment.
2. The successor manifest uses NEW repository-relative paths and binds the exact
   integrated method/config revision.
3. Khương supplies the exact split, data, collision, OCR/cache and coverage
   evidence required by the adopted protocol.
4. Thanh freezes M1.7 against the successor protocol hash and independently
   reviews the same byte-identical package.
5. G1 records the resulting state. Protocol adoption still does not grant an
   execution invocation; authorization remains separate under `run_policy.md`.

Until then, the valid statement is limited to: the OLD M1.5 protocol-layer freeze
was imported and its bytes were verified; NEW adoption, independent acceptance,
data readiness, G1 and result-bearing execution remain open or blocked.
