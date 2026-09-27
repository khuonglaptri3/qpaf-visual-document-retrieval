# Tấn Phát — Weekly Synchronization Plan

## Current Week

- Week: ISO Week 39 (active timeline window 23–27/09/2026)
- Milestone: M1 — final-day evidence, gate, report, and closure sequence
- Branch: `sync/tanphat`
- Base: `develop` at `3df0016`
- Scope rule: synchronize only Tấn Phát's current-week work or a documented strict dependency; do not commit or push.

## Success Criteria

1. Preserve the OLD M1.5 freeze as identifiable historical evidence without presenting it as automatically adopted by the NEW repository.
2. Refresh G1 preparation against the NEW repository's actual evidence state.
3. Produce a current M1.10 draft that does not invent Final G1, sign-offs, learned results, or M1 closure.
4. Keep other members' implementation out of the sync; document it only as an external dependency.
5. Validate hashes, schemas, links, tests, Git scope, and the final diff.

## Timeline Tasks

| Date | Task | Owner | Status before sync | Expected Output |
| ---- | ---- | ----- | ------------------ | --------------- |
| 23/09 | M1.5 Protocol Freeze – Draft | Tấn Phát | PARTIAL — OLD protocol package exists; NEW has a placeholder only | Protocol draft with explicit NEW adoption boundary |
| 24/09 | M1.5 Final Freeze | Tấn Phát | PARTIAL — OLD protocol-layer freeze is hash-valid but not adopted in NEW | Frozen/adopted NEW protocol or explicit unresolved reconciliation |
| 24/09 | G1 Checklist Preparation | Tấn Phát | PARTIAL — OLD checklist is tied to a stale OLD snapshot | Current checklist and requirement-to-evidence-to-owner matrix |
| 25/09 | G1 Pre-review | Tấn Phát | PARTIAL — OLD Pre-G1 snapshot is stale | Current readiness assessment and blocker candidates |
| 25/09 | M1.10 Draft Report | Tấn Phát | PARTIAL — OLD draft is stale; NEW has a placeholder | Current Sprint Report draft with provisional gate fields |
| 26/09 | Protocol / Governance Fix | Tấn Phát | BLOCKED — G1 First Review produced no official blocker list | Amendment/fix only after official reviewed issues exist |
| 26/09 | M1.10 Progress Report | Tấn Phát | PARTIAL — no current NEW report | Updated evidence, risk, status and next work |
| 27/09 | M1.9 Final G1 | Tấn Phát | BLOCKED — First Review, recheck and sign-offs are absent | Evidence-backed Final G1 decision |
| 27/09 | M1.10 Final Report | Tấn Phát | BLOCKED — Final G1 is absent | Final Sprint 1 Progress Report |
| 27/09 | Close M1 | Whole team | NOT STARTED / BLOCKED | M1 closure only after Final G1 and Final R1 |

## External Dependencies

| Dependency | Owner | Required By | New Repo State | Required Action |
| ---------- | ----- | ----------- | -------------- | --------------- |
| M1.4 reviewable repository/data/config/run audit | Khương | G1 First Review | `PARTIAL`; research source/data/config remain missing | Supply actual assets and create a selected, reproducible audit revision |
| Exact ViMDoc split and data-readiness evidence | Khương + Tấn Phát | Active M1.5 adoption, M1.6, G1 | Missing | Materialize IDs/hashes, verify overlap and coverage under an adopted protocol |
| M1.6 collision/leakage audit | Khương | Pre-G1, M1.9 | `BLOCKED / NOT RUN`; CSV files are header-only | Run against the real corpus and obtain review |
| M1.7 final registry and traceability | Thanh | M1.5 adoption, M1.9, Final G1 | Placeholder in NEW; OLD copy remains Draft | Freeze against the adopted protocol and add traceability/audit records |
| M1.8 calibrated OCR/artifact policy | Khương | G1 First Review | Policies are Draft; calibration is missing | Produce reviewable calibration, thresholds and namespace evidence |
| Independent evidence audit and issue log | Thanh | G1 First Review | Missing | Audit the selected review package and record findings |
| Technical Sign-off | Khương | Final G1 | `NOT SIGNED` | After blocker fixes and recheck, sign the selected final technical package |
| Final QA Sign-off | Thanh | Final G1 | Missing | After governance fixes and recheck, sign the selected final QA package |
| Team G1 review/recheck | Whole team | M1.9, M1.10 final, closure | Not convened in available evidence | Conduct review; create official blocker/decision artifacts |

## New Repository Status

### M1.5

`evidence/M1_FINAL/02_protocol/README.md` is a waiting placeholder. The pending NEW remote branch `origin/feature/m1-1-m1-2-handoff` contains a locally verified M1.2 method core, not an adopted M1.5 real-data protocol. Its pairwise-logistic page-level fixture contract conflicts with the OLD M1.5 masked-listwise ViMDoc contract and must remain an explicit reconciliation item.

### M1.9

`evidence/M1_FINAL/06_G1/README.md` states that no G1 review or official decision exists. M1.4 is partial, M1.6 is blocked, M1.7 is a placeholder, M1.8 is draft, and the independent audit is missing, so First Review lacks reviewable entry evidence. Technical and QA Sign-offs are separate later prerequisites for Final G1. A refreshed Pre-G1 can be produced; neither gate can be fabricated.

### M1.10 / Closure

`evidence/M1_FINAL/07_R1/README.md` is a placeholder. A current draft report is possible, but the timeline orders Technical Sign-off + QA Sign-off → Final G1 → Final R1 → M1 closure. That dependency chain is not satisfied.

## Old Repository Findings

- `M1_FINAL/02_protocol/` contains nine Markdown policies and `protocol_freeze_manifest.json`. All 9 protocol hashes and all 14 source-evidence hashes match the OLD manifest. The package was frozen in an untracked, dirty working tree, has no freeze commit or independent sign-off, and keeps execution closed.
- The OLD M1.5 package is repository-specific: paths, source hashes, registry links, Git HEAD, and method semantics refer to `C:\Users\HP\OneDrive\tlcn`.
- `M1_FINAL/06_G1/` contains a checklist, evidence matrix, internal pre-review, and readiness matrix. It explicitly says G1 First Review was not run. Its `PR-B01`–`PR-B07` entries are candidates, not an official blocker log.
- `M1_FINAL/07_R1/Sprint_1_Progress_Report.md` is a 25/09 draft tied to OLD commit `20cb3bf` and stale evidence counts. No OLD `M1_closure_record.md` exists.
- OLD M1.7 artifacts belong to Thanh and remain Draft. OLD training configs, scripts, model code, Modal flows, datasets, runs, and generated outputs are not required for this synchronization.

## Sync Matrix

| Timeline Task | Old Component | New Component | Decision | Reason | Required Action |
| ------------- | ------------- | ------------- | -------- | ------ | --------------- |
| M1.5 | Nine protocol Markdown files | `evidence/M1_FINAL/02_protocol/*.md` | BRING | Hash-addressed historical source is directly relevant | Transfer byte-identically; do not silently edit frozen bytes |
| M1.5 | `protocol_freeze_manifest.json` | Same directory | BRING | Preserves source HEAD, hashes, dirty-state disclosure, and closed execution | Transfer byte-identically and verify 23/23 referenced hashes against OLD sources |
| M1.5 | Mixed-EOL hash-addressed policy bytes | `.gitattributes` | UPDATE | Existing global LF normalization would change the imported bytes when staged | Disable text normalization only for the nine immutable historical Markdown files |
| M1.5 | OLD repository-specific freeze context | `02_protocol/sync_reconciliation.md` | ADAPT | NEW needs a repository-relative adoption boundary | Record source mapping, unresolved semantic conflict, missing review, and required successor-version process |
| M1.5 | OLD freeze status plus NEW placeholder | `02_protocol/README.md` | UPDATE | The existing README must distinguish import from active adoption | Record historical status and keep execution closed |
| M1.5 | OLD training configs/scripts/model code | NEW code/config areas | SKIP | Not a current-week deliverable and not required to preserve the protocol evidence | Document exclusion; do not migrate execution implementation |
| M1.5/M1.9 | OLD M1.7 Draft | `04_experiment_registry/` | EXTERNAL DEPENDENCY | Owned by Thanh and absent as Final in NEW | Do not copy; keep links/dependency status explicit |
| G1 Prep | `G1_checklist.md` | `evidence/M1_FINAL/06_G1/G1_checklist.md` | ADAPT | Checklist logic is reusable but paths/statuses are stale | Rebase paths and entry criteria on NEW evidence |
| G1 Prep | `G1_evidence_matrix.csv` | Same directory | ADAPT | Requirement set is useful; current states and hashes are OLD-specific | Regenerate current state without marking internal checks as independent review |
| Pre-G1 | `G1_pre_review.md`, `G1_readiness_matrix.csv` | Same directory | UPDATE | OLD snapshot incorrectly says M1.4/M1.8 directories are absent | Produce a fresh NEW-repo snapshot with `BLOCKED_FOR_G1_FIRST_REVIEW` outcome |
| M1.9 | Missing blocker log/final decision | Canonical G1 paths | SKIP | No team review occurred; final sign-offs are also absent | Do not create acceptance artifacts; list them as remaining work |
| M1.10 | OLD Sprint 1 draft | `evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md` | ADAPT | Structure/claim boundaries are useful; provenance and evidence states are stale | Rewrite from NEW evidence and keep report Draft |
| Closure | No OLD closure record | `evidence/M1_FINAL/07_R1/M1_closure_record.md` | SKIP | Timeline prerequisites are unmet | Do not create; keep closure `NOT_REACHED` |
| Package index | OLD/New status notes | `evidence/M1_FINAL/README.md` and area READMEs | UPDATE | Package index must reflect synchronized preparation without overstating acceptance | Update owner/status/path summaries only |

## Files to Bring

- `evidence/M1_FINAL/02_protocol/baseline_policy.md`
- `evidence/M1_FINAL/02_protocol/candidate_policy.md`
- `evidence/M1_FINAL/02_protocol/dataset_split_policy.md`
- `evidence/M1_FINAL/02_protocol/frozen_protocol.md`
- `evidence/M1_FINAL/02_protocol/metric_policy.md`
- `evidence/M1_FINAL/02_protocol/protocol_amendments.md`
- `evidence/M1_FINAL/02_protocol/run_policy.md`
- `evidence/M1_FINAL/02_protocol/seed_policy.md`
- `evidence/M1_FINAL/02_protocol/statistical_policy.md`
- `evidence/M1_FINAL/02_protocol/protocol_freeze_manifest.json`
- `evidence/M1_FINAL/02_protocol/sync_reconciliation.md`
- `evidence/M1_FINAL/06_G1/G1_checklist.md`
- `evidence/M1_FINAL/06_G1/G1_evidence_matrix.csv`
- `evidence/M1_FINAL/06_G1/G1_pre_review.md`
- `evidence/M1_FINAL/06_G1/G1_readiness_matrix.csv`
- `evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md`

## Files to Adapt

- G1 preparation and Pre-G1 artifacts: replace OLD path/snapshot claims with the NEW evidence state.
- Sprint 1 report: retain only source-faithful structure and claim boundaries; replace all OLD branch/hash/count/status claims.
- M1.5 adoption context: keep frozen source bytes immutable and add a separate reconciliation record.

## Existing Files to Update

- `evidence/M1_FINAL/README.md`
- `.gitattributes`
- `evidence/M1_FINAL/02_protocol/README.md`
- `evidence/M1_FINAL/06_G1/README.md`
- `evidence/M1_FINAL/07_R1/README.md`
- `TAN_PHAT_WEEKLY_SYNC_PLAN.md` after execution

## Files Explicitly Excluded

- OLD `configs/qarf_train.yaml`, `configs/qpaf_train.yaml`, learned-training scripts, Modal wrappers, model code, tests, datasets, score caches, checkpoints, logs, runs, and generated outputs: outside current-week synchronization and not strict dependencies for documentation import.
- OLD M1.7 Draft files: Thanh-owned external dependency; copying them would take ownership of another member's task.
- OLD G1 Pre-review candidates as an official blocker log: no G1 review occurred.
- `G1_final_decision.md` and `M1_closure_record.md`: no source artifact or valid gate evidence exists.
- Pending remote M1.1/M1.2 feature contents: separate unmerged work; inspect only to identify the M1.5 semantic conflict.
- User-owned `SYNC_TAN_PHAT_PROMPT.md`: preserve untracked and untouched.

## Dependency Notes

- Imported protocol Markdown remains linked to OLD-relative M1.7 paths. The reconciliation record must state that those dependencies are unresolved in NEW; broken dependency links must not be interpreted as adopted registry evidence.
- OLD manifest hashes identify OLD paths and mixed line endings. Exact-byte import is required to retain the historical package digest.
- Active adoption must use a successor protocol version or approved amendment; it must not rewrite the historical files.
- The pending NEW M1.2 core uses pairwise logistic loss; OLD M1.5 uses masked listwise loss. This blocks active adoption but not historical preservation.
- No package dependency, database change, API change, or runtime execution is required for this sync.

## Execution Order

1. Transfer and hash-verify the immutable OLD M1.5 package.
2. Add the NEW adoption/reconciliation record and update the protocol README.
3. Regenerate G1 checklist, evidence matrix, Pre-G1 report, and readiness matrix from NEW evidence.
4. Adapt the Sprint 1 Progress Report as a current draft.
5. Update package/area READMEs and this plan with final statuses.
6. Validate JSON/CSV/Markdown links, imported hashes/package digest, tests, `git diff --check`, Git status, and every changed path against a Tấn Phát task.

## Planned Verification

- Recompute all imported protocol SHA-256 values and canonical package digest.
- Parse the manifest JSON and both G1 CSVs; require unique IDs and expected columns.
- Check relative Markdown links and distinguish expected unresolved external-dependency links.
- Run `python -m unittest discover -s tests -v`.
- Run `python -m compileall -q src scripts tests`.
- Run `git diff --check`, inspect `git status`, and review the complete diff/name list.
- Scan changed files for credential-like material and generated payloads.

## Final Status

Completed on branch `sync/tanphat` as an uncommitted, unpushed working-tree synchronization.

### Task Outcomes

| Timeline Task | Final Status | Synchronized / Adapted / Updated | Verification | Remaining Issues / Dependencies |
| ------------- | ------------ | -------------------------------- | ------------ | ------------------------------- |
| M1.5 Protocol Freeze – Draft | `PARTIAL` | Imported the nine-policy historical package; added NEW reconciliation | Historical hashes, package digest, bytes and Git clean-filter identity match | Active NEW protocol draft/adoption still requires real split/data, M1.7 binding and independent review |
| M1.5 Final Freeze | `PARTIAL` | Imported the OLD manifest; updated protocol README and targeted Git attributes | 9/9 protocol and 14/14 OLD source hashes match; execution remains closed | No adopted NEW-relative successor manifest or final independent sign-off exists |
| G1 Checklist Preparation | `DONE` | Adapted `G1_checklist.md` and `G1_evidence_matrix.csv` | 36 × 13 CSV parses with unique IDs; current links resolve | Refresh after upstream evidence changes |
| G1 Pre-review | `DONE` | Adapted `G1_pre_review.md` and `G1_readiness_matrix.csv` | 14 × 14 CSV parses with unique IDs; First Review and Final G1 phases are separated | Outcome is legitimately `BLOCKED_FOR_G1_FIRST_REVIEW`; refresh on one reviewable snapshot |
| M1.10 Draft Report | `DONE` | Created the current Sprint 1 draft and updated R1 README | Draft/NOT_RUN/NOT_REACHED boundaries and links verified | It is not Final R1 |
| Protocol / Governance Fix | `BLOCKED` | No historical protocol byte was altered and no amendment was fabricated | Official blocker log confirmed absent | Requires G1 First Review and an official protocol/governance blocker before a fix or amendment is valid |
| M1.10 Progress Report | `PARTIAL` | Updated the draft with current evidence, risks, external owners and next work | Claim boundaries and gate sequence independently reviewed | Official blocker-resolution status cannot be added before G1 v1/recheck |
| M1.9 Final G1 | `BLOCKED` | Updated G1 README; did not create official blocker/decision files | Acceptance artifacts absent; gate phases and dependencies verified | Needs First Review, fixes, recheck, Technical Sign-off and QA Sign-off |
| M1.10 Final Report | `BLOCKED` | Preserved the current file as Draft rather than relabeling it Final | Final-G1 and closure fields remain `NOT_REACHED` | Must wait for Final G1 |
| Close M1 — whole-team gate context | `BLOCKED` | No closure record created | Closure artifact confirmed absent | Requires Final G1 and Final R1; not a Tấn Phát-only task |

### Synchronized and Adapted Files

- Brought byte-identically: the nine OLD protocol Markdown files and `protocol_freeze_manifest.json` listed under **Files to Bring**.
- Added for NEW reconciliation: `evidence/M1_FINAL/02_protocol/sync_reconciliation.md`.
- Adapted for NEW: the four G1 preparation files and `evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md`.
- Updated indexes/status notes: `evidence/M1_FINAL/README.md` and the READMEs in `02_protocol`, `06_G1`, and `07_R1`.
- Preserved without modification: user-owned untracked `SYNC_TAN_PHAT_PROMPT.md`.
- Excluded as planned: implementation/config/data/results, Thanh-owned M1.7 Draft, official G1 acceptance artifacts, and an M1 closure record.

### Verification Results

- Imported protocol: 9/9 protocol hashes match the manifest and OLD sources; 14/14 OLD source-evidence hashes match; canonical package digest and source/destination bytes match; targeted `-text` rules keep Git clean-filter bytes identical; `execution_authorized=false`.
- G1 CSVs: 36 rows × 13 columns and 14 rows × 14 columns; both parse successfully and have unique IDs.
- Current Markdown: 10 relative links checked, zero missing. Four preserved OLD-relative M1.7 links remain unresolved by design and are disclosed in the reconciliation record.
- Acceptance boundaries: all three unsupported acceptance artifacts are absent; all four required historical/blocked/not-run/not-reached status markers are present.
- Safety: zero credential-like assignments and zero files at or above 1 MB in the synchronized set.
- Repository checks: `python -m unittest discover -s tests -v` passed 14 tests with one host-symlink skip; `python -m compileall -q src scripts tests` passed; `git diff --check` passed for the tracked diff; current authored Markdown has zero trailing-whitespace lines.
- Immutable-import warning: the nine historical Markdown policies retain 586 CRLF lines and 17 literal trailing-space/hard-break lines, with one overlap, because editing them would invalidate the manifest. The targeted `.gitattributes` rules prevent Git normalization. Under the current Git settings, a staged-style whitespace check reports 602 manifest-bound warnings; these are disclosed provenance exceptions, not authored-sync whitespace.
- Gate-order checks: First Review criteria exclude final sign-offs, Final G1 retains both sign-offs, and the readiness matrix has no review self-dependency.
- Independent final review: zero Critical, Important, or Minor findings after the sequencing/status corrections.
- Tooling limitation: the optional `python -m build` frontend is not installed (`No module named build`); `pyproject.toml` has no lint/type-check configuration. No package or dependency file changed.
- Git scope: no staged files, commits, pushes, source-code changes, dependency changes, schema changes, or runtime execution were introduced.

### Remaining Issues and Next Gate

The external dependencies in this plan remain open. The next valid Tấn Phát action is to coordinate the M1.5 successor/adoption decision after the real split and M1.7 registry are available, then refresh Pre-G1 when Khương's M1.4/M1.6/M1.8 evidence and Thanh's M1.7/independent audit are reviewable on one selected snapshot. The team can then conduct G1 First Review and create the official blocker log/decision. After blocker fixes and G1 Recheck, Technical and QA Sign-offs gate Final G1; Final G1 and Final R1 must precede M1 closure.
