# Experiment Naming Rules

**Task:** M1.7 Experiment Registry — Draft  
**Owner:** Thanh  
**Schema version:** `0.1-draft`  
**Prepared:** 2026-09-25  
**Freeze condition:** M1.5 Frozen Protocol and the M1.4/M1.6 inventories must be available and reconciled.

## 1. Purpose and scope

These rules assign a unique, immutable identifier to every execution attempt that can create research, engineering, audit, or governance evidence. They apply to local and remote work, including failed, blocked, killed, and not-run records.

An identifier records identity only. It does not imply approval, completion, correctness, or permission to retry.

## 2. Experiment ID

Use this structure:

```text
exp-<task>-<dataset>-<method>-<class>-s<seed>-d<date>-r<attempt>
```

Token rules:

| Token | Rule |
| ----- | ---- |
| `task` | Lowercase task ID without punctuation other than hyphens, for example `p1-02r-o1`. |
| `dataset` | Stable lowercase dataset slug, `multi` for multiple datasets, or `na` when no dataset is involved. |
| `method` | Stable lowercase method/component slug such as `bm25`, `qarf`, `qpaf`, `three-channel`, or `governance`. |
| `class` | ID code defined in `test_classification.md`. |
| `seed` | Integer seed, `na` when randomness is not applicable, or `unknown` only for historical evidence whose required seed cannot be recovered. |
| `date` | Verified execution start date in UTC as `YYYYMMDD`; use `unknown` only for historical evidence when the date cannot be recovered. |
| `attempt` | Two-digit attempt ordinal starting at `01`. Incrementing it records an already authorized new attempt; it never grants retry authority. |

Example showing syntax only, not a registered project result:

```text
exp-px-01-example-dataset-example-method-smoke-s20260820-d20260925-r01
```

The experiment ID must match:

```regex
^exp-[a-z0-9]+(?:-[a-z0-9]+)*-s(?:[0-9]+|na|unknown)-d(?:[0-9]{8}|unknown)-r[0-9]{2}$
```

## 3. Registry event ID

The registry is an event ledger. Each appended event uses:

```text
<experiment_id>-e<event-sequence>
```

where `event-sequence` is a three-digit number beginning at `001` for that experiment. For example:

```text
exp-px-01-example-dataset-example-method-smoke-s20260820-d20260925-r01-e001
```

One experiment may therefore have multiple immutable events such as registration, authorization, start, completion, failure, correction, or supersession.

## 4. Slug normalization

All ID tokens must:

* use lowercase ASCII letters, digits, and single hyphens only;
* transliterate Vietnamese names rather than storing accents in the ID;
* collapse whitespace, underscores, slashes, and repeated hyphens to one hyphen;
* remove leading and trailing hyphens;
* use stable dataset and method names already present in config or protocol when available.

Human-readable names remain in registry fields; they must not be encoded by inventing a new slug on every run.

## 5. Immutability and collision rules

* Assign the experiment ID before the execution begins whenever the run is planned.
* Never reuse an ID, output directory, checkpoint path, or run directory.
* A failed or consumed attempt keeps its ID permanently.
* A separately authorized retry receives the next attempt ordinal and a new ID.
* A metadata correction creates a new registry event; it does not rename the experiment.
* If two historical records map to the same proposed ID, keep the earliest verified attempt ordinal and assign later records the next ordinal. Record the evidence used to establish order in `notes`.
* `UNKNOWN` metadata must remain visible and generate an issue; it must not be guessed merely to make the ID look complete.

## 6. Fields forbidden in an ID

Do not place mutable or result-bearing values in the ID, including:

* status or gate decision;
* metric values;
* hardware/GPU;
* branch name or commit hash;
* output path;
* labels such as `best`, `final`, `new`, or `latest`.

Those values belong in explicit registry fields and may change only through appended events.

## 7. Draft acceptance checks

Before M1.7 freeze:

1. Validate every proposed experiment ID against the regex.
2. Verify that `experiment_id` values are unique per execution attempt.
3. Verify that every `registry_event_id` is globally unique.
4. Confirm that every class code resolves to exactly one row in `test_classification.md`.
5. Confirm that historical `unknown` tokens have corresponding issues rather than inferred values.

