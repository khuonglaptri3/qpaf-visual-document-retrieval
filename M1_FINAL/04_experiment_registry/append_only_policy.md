# Append-Only Experiment Registry Policy

**Task:** M1.7 Experiment Registry — Draft  
**Owner:** Thanh  
**Schema version:** `0.1-draft`  
**Prepared:** 2026-09-25  
**Freeze condition:** This policy becomes final only after reconciliation with M1.5 and the M1.4/M1.6 evidence inventories.

## 1. Policy objective

`experiment_registry.csv` is an append-only event ledger. It must make every planned, authorized, attempted, completed, failed, blocked, killed, corrected, and superseded experiment traceable without erasing prior state.

The registry records evidence; it does not grant execution authority and does not override `Tasks.md`, protocol guards, or human approval requirements.

## 2. Event model

Each CSV row is one immutable event:

```text
registry_event_id -> experiment_id -> evidence/config/data/code/output links
```

An experiment may have multiple events. The latest valid event gives its current registry state, while all earlier events remain auditable.

Allowed `event_type` values are:

* `REGISTERED`
* `AUTHORIZED`
* `STARTED`
* `COMPLETED`
* `FAILED`
* `BLOCKED`
* `KILLED`
* `ANNOTATED`
* `CORRECTED`
* `SUPERSEDED`

## 3. Append-only rules

1. Never edit or delete an existing event row after it has been reviewed or committed.
2. Never reuse an `experiment_id`, `registry_event_id`, output directory, checkpoint path, or manifest path for a different attempt.
3. Record an attempt even when it fails before producing a scientific output, consumes a create-once authorization, or is blocked after start.
4. Record status changes by appending a new event with the same `experiment_id` and the next event sequence.
5. Correct metadata by appending a `CORRECTED` event whose `supersedes_event_id` points to the incorrect event. Preserve the original value and explain the correction in `notes`.
6. Replace an experiment only through a new experiment ID and a `SUPERSEDED` event. A replacement does not retroactively turn the earlier attempt into PASS.
7. Do not overwrite score caches, manifests, checkpoints, predictions, logs, or results referenced by a registry event.
8. Store paths relative to the repository root when the artifact is in the repository. External or remote artifacts require an immutable identifier plus a recorded hash.

## 4. Missing and not-applicable values

Use controlled values instead of guessing:

| Value | Use |
| ----- | --- |
| `NA` | The field does not apply to this experiment class. |
| `PENDING` | The field is expected but cannot exist yet because the experiment is planned, authorized, or running. |
| `UNKNOWN` | The field should exist for historical evidence but has not been recovered. This requires an issue-log entry. |
| `NOT_RECORDED` | Evidence proves the activity occurred but also proves that the field was not captured at execution time. This requires an issue-log entry. |

Empty cells are not allowed in a reviewed registry event. `UNKNOWN` and `NOT_RECORDED` must not be converted to plausible values without evidence.

## 5. Minimum registration requirements

Before execution, append a `REGISTERED` event containing at least:

* experiment and event IDs;
* responsible owner and task ID;
* experiment/evidence classification;
* method, dataset role, protocol and config paths;
* seed or explicit `NA`;
* intended command/backend;
* planned claim scope.

Before an authorized bounded execution, append or reference evidence for:

* exact approval scope;
* source commit and dirty state;
* protocol/config/data hashes;
* attempt count or create-once status;
* output/manifest destinations;
* stop and no-retry conditions where applicable.

For a completed learned or remote run, the closing event must record the fields required by the repository governance rules: split, dataset/model revisions, candidate and config hashes, source commit, dirty diff, hardware, start/end time, command, seed, status, primary metric, peak memory, run identifier, image/function information when applicable, and immutable output/manifest hashes.

## 6. Status and evidence changes

* `PASS` requires artifact-level verification, not merely a process exit code or a source artifact saying `complete`.
* `submitted` or `running` remains `STARTED`, not `PASS`.
* A blocked dependency creates a `BLOCKED` event; it does not justify omitting the experiment.
* A gate or protocol decision is registered as `governance` and must not silently relabel an underlying scientific task.
* Changes after protocol freeze require a versioned amendment recorded before execution under the changed protocol.

## 7. Schema versioning

During `0.1-draft`, the schema may be corrected before any reviewed data row is frozen. Once M1.7 is frozen:

1. The header and meaning of existing columns are immutable.
2. A breaking schema change creates a new versioned registry file and a migration note; the old file remains unchanged.
3. New optional columns require an explicit schema amendment and default mapping for historical rows.
4. No schema change may weaken traceability or erase an evidence boundary.

## 8. Review and freeze checks

Before accepting a registry version:

1. Parse the CSV successfully with a standards-compliant CSV reader.
2. Verify global uniqueness of `registry_event_id`.
3. Verify each `experiment_id` obeys `experiment_naming_rules.md`.
4. Verify event sequences increase without duplicates for each experiment.
5. Verify every value in `experiment_class`, `evidence_class`, `registry_status`, and `event_type` belongs to its controlled vocabulary.
6. Verify every completed/PASS row links to existing or hash-addressed evidence.
7. Verify no earlier row was deleted or changed relative to the previously frozen registry hash.
8. Record the registry file hash, schema version, reviewer, and freeze time in the QA sign-off.

## 9. Draft completion boundary

This draft completes only the non-dependent M1.7 design work. It does not:

* declare M1.5 frozen;
* claim the M1.4/M1.6 inventories are complete;
* populate or validate historical experiment rows;
* perform the independent evidence audit;
* authorize or execute an experiment;
* freeze M1.7 or sign G1.

