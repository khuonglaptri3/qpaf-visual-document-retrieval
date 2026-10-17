# Test and Evidence Classification

**Task:** M1.7 Experiment Registry — Draft  
**Owner:** Thanh  
**Schema version:** `0.1-draft`  
**Prepared:** 2026-09-25  
**Freeze condition:** Reconcile this taxonomy with the M1.5 Frozen Protocol before declaring it final.

## 1. Classification model

Every registry event must preserve three separate concepts:

* `experiment_class`: what activity was performed;
* `evidence_class`: what kind of evidence the activity may support;
* `registry_status`: the normalized lifecycle state.

The original wording from the source artifact must also be copied without reinterpretation to `source_status`.

## 2. Experiment classes

| `experiment_class` | ID code | Use | Default evidence class | Claim boundary |
| ------------------ | ------- | --- | ---------------------- | -------------- |
| `governance` | `gov` | Protocol, approval, gate, closure, or registry record with no computation | `governance_record` | Records a decision or rule only; it is not measured performance. |
| `unit_test` | `unit` | One isolated code contract | `non_scientific` | Supports only the tested software contract. |
| `integration_test` | `integration` | Interaction between components or artifact contracts | `engineering_evidence` | Does not establish retrieval quality or model improvement. |
| `smoke_test` | `smoke` | Small bounded execution proving that a path starts and completes | `engineering_evidence` | Cannot be reported as a full experiment result. |
| `engineering_probe` | `eng-probe` | Runtime, memory, environment, or feasibility probe | `engineering_evidence` | Non-scientific unless a frozen protocol explicitly states otherwise. |
| `calibration` | `calibration` | Bounded parameter/resource calibration before a separately authorized full run | `engineering_evidence` | Calibration estimates are not full-run measurements. |
| `data_audit` | `data-audit` | Dataset, split, qrels, coverage, collision, hash, or leakage audit | `engineering_evidence` | Supports data readiness only. It is not a method-quality result. |
| `score_extraction` | `extraction` | Produce frozen retriever scores/caches | `engineering_evidence` | A valid score bundle is an input artifact, not evidence that a fusion method wins. |
| `oracle_upper_bound` | `oracle` | Global/QARF/CARF/QPAF oracle selection using permitted labels | `scientific_upper_bound` | Must be labeled upper bound and kept separate from deployable learned results. |
| `learned_training` | `train` | Optimizer-bearing training or checkpoint creation | `scientific_result` | Training evidence alone is not a test-set claim. |
| `learned_evaluation` | `eval` | Frozen-checkpoint evaluation on an allowed split | `scientific_result` | Claim scope depends on split, seed count, protocol, and statistical gate. |
| `ablation` | `ablation` | One-factor controlled change from a frozen parent config | `scientific_result` | The changed factor and parent config must be explicit. |
| `external_evaluation` | `external` | Evaluation on a sealed external dataset | `scientific_result` | No tuning or selection may use external results. |
| `system_test` | `system` | End-to-end application or reproducibility validation | `system_evidence` | Supports system behavior, not a new retrieval-quality claim unless separately classified. |

If an activity appears to fit two classes, choose the narrowest class describing what actually executed. Register separate events or experiments when one command creates materially different evidence types.

## 3. Evidence classes

Allowed `evidence_class` values are:

| Value | Meaning |
| ----- | ------- |
| `governance_record` | Human or project decision, approval, protocol, amendment, or gate record. |
| `non_scientific` | Software-only evidence with no scientific or performance claim. |
| `engineering_evidence` | Data, environment, runtime, integrity, or execution-readiness evidence. |
| `scientific_upper_bound` | Oracle analysis that uses labels within the frozen protocol and is not deployable. |
| `scientific_result` | Measured learned/baseline/ablation/external result under a valid frozen protocol. |
| `system_evidence` | End-to-end application, packaging, reload, or reproduction evidence. |

Classification must never be promoted merely because an artifact reports `PASS`.

## 4. Registry statuses

Allowed `registry_status` values are:

| Value | Meaning |
| ----- | ------- |
| `PLANNED` | Defined but not authorized or started. |
| `AUTHORIZED` | Explicitly approved within a bounded scope but not started. |
| `STARTED` | Execution began or a create-once attempt was consumed. |
| `PASS` | The class-specific completion and verification criteria passed. |
| `FAIL` | Execution or verification completed with a failed criterion. |
| `BLOCKED` | A dependency, input, approval, or environment prevents completion. |
| `KILLED` | A preregistered stop condition permanently ended the path. |
| `NOT_RUN` | Intentionally not executed, with the reason recorded. |
| `SUPERSEDED` | A later version replaces this record without deleting it. |

`source_status` preserves exact native values such as `complete`, `In Progress`, or a protocol-specific status. Mapping to `registry_status` must be justified by the referenced evidence; uncertainty maps to `BLOCKED`, not an optimistic state.

## 5. Required classification safeguards

* A unit, integration, or smoke test cannot be reclassified as a scientific result.
* A performance probe or calibration cannot be used as a full-corpus runtime claim.
* Score extraction and coverage PASS do not imply oracle, learned, or deployable method PASS.
* Oracle output must use `scientific_upper_bound` and remain separate from learned/deployable rows.
* A single-seed learned result must retain its seed and limited claim scope; it cannot establish a general improvement claim by itself.
* Failed, blocked, killed, consumed, and not-run attempts must still be registered.
* `result_claim_scope` must state the exact boundary, for example `engineering_only`, `candidate_pool_only`, `oracle_upper_bound`, `single_seed_preliminary`, `confirmation`, or `external_sealed`.

## 6. Draft acceptance checks

Before M1.7 freeze:

1. Every registry row has one allowed experiment class, evidence class, and normalized status.
2. `source_status` remains verbatim and is not silently replaced by the normalized status.
3. Every `PASS` row has a manifest or other referenced verification evidence.
4. Every scientific result declares dataset role, split, seed, protocol hash, config hash, source commit, and output hashes.
5. Every upper-bound, calibration, smoke, and probe record has an explicit restricted claim scope.

