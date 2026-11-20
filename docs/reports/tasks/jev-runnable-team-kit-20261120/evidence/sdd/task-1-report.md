# Task 1 implementation report

2026-11-20. Work followed the existing authorization for the runnable Jev team kit and the [task brief](task-1-brief.md), [spec](../../superpowers/spec.md) and [plan](../../superpowers/plan.md). The implementation worktree started at `e5060b4aa422690117b3552ca85524aea01c71da`. Core code and tests were committed as `fc00899a15a6ea9e59a31260ab97d565c787d71d`. The controller owns independent review and integration.

Read the installed Superpowers 7.0.1 `using-superpowers/SKILL.md` and `using-superpowers/references/codex-tools.md`, then applied `test-driven-development/SKILL.md` with `test-driven-development/writing-good-tests.md`. Applied `verification-before-completion/SKILL.md` before reporting success and committing. The install root is `C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/`.

## Workflows

- Run `python scripts/run_jev.py doctor` and `python scripts/run_jev.py demo --out DIR` using Python 3.11 or later. The demo writes synthetic pairs, judgments, lexical scores, baseline and per-query metric reports, and a paired comparison.
- Run `prepare --raw-scores FILE --dataset NAME --queries FILE --page-text FILE --out DIR` for explicit `base_score` rows. For BM25, dense and visual channels, pass `--weights BM25 DENSE VISUAL` with nonnegative values summing to one. Preparation normalizes explicit channels per query, selects top-K and serializes in page-ID order while preserving aligned scores.
- Run `prepare --f9-bundle DIR --dataset vidoseek|vimdoc --page-text FILE --weights BM25 DENSE VISUAL --out DIR` for native retriever bundles. This reads only the selected split IDs, query texts, OCR and projected retriever columns. ViDoSeek uses the bundle's `splits/test_ids.txt`. ViMDoc uses the repository's confirmation IDs and retains document IDs. Use `--query-ids FILE` to override the selected query IDs. The native Parquet path uses optional PyArrow.
- Run `prepare --f9-pairs FILE --out DIR` or `prepare --f9-cache DIR --out DIR` to preserve the original pair bytes. Supply `--splits FILE --partition train|validation|test` together to select one validated partition in raw or import mode. For an F9 import, add `--import-scores CACHE` to validate the original pair hash, project the ordered score vector and bind it to the output pair bytes.
- Run `evaluate --pairs FILE --scores FILE --qrels FILE --out METRICS.json --csv METRICS.csv` to evaluate a score cache. Use `--baseline` with explicit aligned `base_scores`, or `--lambda FLOAT` with a score cache to request a per-query min-max blend. Use `--units FILE` for a page-to-document sidecar when the legacy pairs omit it. Tied scores use ascending unit IDs. JSON identifies the ranking scope as the provided pool. In ViMDoc the historical F9 tail may contain more unique documents than this shortlist.
- Run `compare --left LEFT.json --right RIGHT.json --out CMP.json --csv CMP.csv` for right-minus-left paired deltas, percentile intervals and wins/ties/losses. Optional `--groups FILE` samples whole groups and weights sampled queries equally. Defaults are seed 20260820 and 10,000 replicates.

The score writer validates finite values and exact coverage before atomically replacing a final cache. Callers that score a previously loaded snapshot can pass `expected_pairs_sha256` to reject input replacement during scoring. The prepared output manifest hashes inputs and reports empty OCR pages. Focused tests exercised data validation, preservation of original pair bytes, qrels outside the pool, document max pooling, split isolation, and CLI execution from another directory with site packages disabled. Native ViMDoc preparation was verified with a tiny Parquet fixture whose sealed-qrels placeholder contained invalid JSON.

## Verification evidence

### RED before implementation

- `python -m unittest tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` exited 1. `FAILED (failures=4, errors=2)` showed the missing `scripts/run_jev.py` and the missing `qpaf.jev` package. Initial implementation brought all 21 tests to green, including the separate native Parquet test which first failed on the missing script.
- `python -m unittest tests.test_jev_cli.CliTest.test_partition_rewrites_paired_scores_and_keeps_only_its_queries -v` exited 1 with `unrecognized arguments: --import-scores ... --splits ... --partition test`.
- `python -m unittest tests.test_jev_contracts.ContractsTest.test_writer_rejects_pair_changes_since_scoring tests.test_jev_evaluation.EvaluationTest.test_tied_units_follow_unit_id_even_when_page_order_differs -v` exited 1 with the absent writer argument and observed MRR 0.5 instead of 1 for tied document scores.
- `python -m unittest tests.test_jev_cli.CliTest.test_imported_f9_bytes_allow_existing_cache_evaluation -v` exited 1 with `KeyError: 'ranking_scope'` before the protocol field was added.

### GREEN and self-review

- `python -m unittest tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` under Python 3.14.6 exited 0. `Ran 24 tests in 7.711s` and `OK`.
- `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -q` under Python 3.14.6 exited 0. `Ran 24 tests in 3.937s` and `OK (skipped=1)`. Python 3.11 with the same isolation flags also exited 0. `Ran 24 tests in 2.749s` and `OK (skipped=1)`. Both skips were the optional PyArrow integration.
- `python -I -S scripts/run_jev.py prepare --help` and `python -I -S scripts/run_jev.py evaluate --help` displayed the required input and output flags without site packages.
- Inspected the original F9 loader and ranking paths for source schema, page order and unit tie behavior. The standalone evaluator reports metrics for supplied candidates, and its blend uses explicit weights over the provided pool. The legacy F9 screen/stack remains the path for historical full rankings.
- `git diff --cached --check` passed for the explicit Task 1 paths, and `git ls-files --eol` recorded LF in the index and worktree. The task covers the CPU toolkit. Full private data preparation, GPU inference and training remain integration work. Task 1 used no full model runs, weights or cloud jobs.

### Full project suite

`python -m unittest discover -s tests -v` exited 1. `Ran 635 tests in 141.657s` and `FAILED (failures=14, errors=72, skipped=44)`. The full run started before the final two focused regression tests. Its Jev tests passed. The following older tests accounted for all reported failures and errors in the current environment.

### ModuleNotFoundError: No module named 'torch'

- `test_a005_authorize`
- `test_a005_model`
- `test_a005_probe`
- `test_a005_refine`
- `test_a005_refine_eval`
- `test_a005_stage2`
- `test_a005_stage3`
- `test_a005_stage4`
- `test_a005_stage5`
- `test_a005_stage6`
- `test_a005_trainer`
- `test_a005_vimdoc`
- `test_dse_safetensors_verification`
- `test_f9`
- `test_features`
- `test_gradients`
- `test_lab`
- `test_lab_heldout`
- `test_lab_rerank`
- `test_losses`
- `test_m36_integrity.IntegrityTests.test_cpu_zero_cuda_allocation_cannot_pass_the_gpu_gate`
- `test_m36_integrity.IntegrityTests.test_nonfinite_checkpoint_state_is_rejected`
- `test_m44_evaluation.AttemptTests.test_success_and_failure_markers`
- `test_m46_losses`
- `test_m46_probe`
- `test_m46_trainer`
- `test_m52_cache_parity.CacheParityTests.test_create_verify_is_read_only_and_rejects_receipt_or_input_tampering`
- `test_m52_cache_parity.CacheParityTests.test_method_and_historical_drift_are_detected`
- `test_m52_cache_parity.CacheParityTests.test_records_have_no_label_fields_and_match_frozen_batch_path`
- `test_m52_cache_parity.CacheParityTests.test_seed_changes_training_shuffle_but_not_validation`
- `test_m56_ablations`
- `test_models`
- `test_score_extractor`
- `test_vidoseek_coverage_audit`
- `test_vidoseek_p1_02r`
- `test_vidoseek_p1_02r_full`

### ModuleNotFoundError: No module named 'pypdfium2'

- `test_m11_artifacts`
- `test_m11_pipeline`
- `test_m13_cli`
- `test_m13_corpus`
- `test_m13_splits`
- `test_m13_vidoseek`
- `test_m16_real_audit.RealAuditTests.test_real_pdf_cli_uses_m13_splits_and_measures_shared_documents`
- `test_m18_runtime`
- `test_m21_data_splits`
- `test_m22_smoke`
- `test_m23_calibration`
- `test_m23_policy`
- `test_m26_full_ocr.FullOCRTests.test_artifact_path_escape_is_rejected`
- `test_m26_full_ocr.FullOCRTests.test_atomic_extraction_resumes_after_interrupted_temporary_write`
- `test_m26_full_ocr.FullOCRTests.test_corrupt_pdf_yields_terminal_failure_and_keeps_both_text_files`
- `test_m26_full_ocr.FullOCRTests.test_csv_environment_and_resources_are_checked_semantically`
- `test_m26_full_ocr.FullOCRTests.test_failure_with_successful_ocr_still_verifies_its_raw_text_hash`
- `test_m26_full_ocr.FullOCRTests.test_hard_termination_collects_committed_records_without_final_manifest`
- `test_m26_full_ocr.FullOCRTests.test_hash_tampering_is_rejected`
- `test_m26_full_ocr.FullOCRTests.test_interrupted_page_recovery_preserves_existing_native_text_and_image`
- `test_m26_full_ocr.FullOCRTests.test_missing_duplicate_and_wrong_document_pages_are_rejected`
- `test_m26_full_ocr.FullOCRTests.test_mixed_policy_is_rejected`
- `test_m26_full_ocr.FullOCRTests.test_no_text_page_keeps_visual_and_is_not_a_failure`
- `test_m26_full_ocr.FullOCRTests.test_partial_failed_image_is_preserved_without_claiming_valid_visual_input`
- `test_m26_full_ocr.FullOCRTests.test_partial_utf8_native_is_retained_as_failed_raw_evidence`
- `test_m26_full_ocr.FullOCRTests.test_real_files_verify_and_raw_file_hash_differs_from_stripped_text`
- `test_m26_full_ocr.FullOCRTests.test_rehashed_fabricated_failure_text_is_rejected`
- `test_m26_full_ocr.FullOCRTests.test_rehashed_wrong_final_text_fails_policy_replay`
- `test_m26_full_ocr.FullOCRTests.test_render_failure_is_retained_and_counts_against_all_scheduled_pages`
- `test_m26_full_ocr.FullOCRTests.test_schedule_validates_actual_counts_ids_hash_and_document_sequences`
- `test_m26_full_ocr.FullOCRTests.test_success_missing_raw_artifact_is_rejected`
- `test_m26_full_ocr.FullOCRTests.test_worker_killed_before_pages_exist_exports_zero_terminal_partial_receipt`

### qpaf.m27.matched.ParityError: torch is required for initialization and data-order parity

- `test_m210_readiness.AuditTests.test_m27_structural_config_is_still_frozen`
- `test_m27_binding.BindingTests.test_binding_verifies_hashes_handover_and_real_row_batch_order`

### importlib.metadata.PackageNotFoundError: No package metadata was found for torch

- `test_m52_cache_parity.CacheParityTests.test_wrong_numerical_runtime_is_rejected_before_payload_loading`

### ModuleNotFoundError: No module named 'modal'

- `test_modal_contract`

### AssertionError: "handover" does not match "torch is required for initialization and data-order parity"

- `test_m27_binding.BindingTests.test_blocked_or_mismatched_handover_is_rejected`

### AssertionError: "qrels_test_sealed" does not match "torch is required for initialization and data-order parity"

- `test_m27_binding.BindingTests.test_changed_bound_file_fails_closed`

### AssertionError: M3.1 sealed pilot inputs are not implemented

- `test_m31_seal.SealTests.test_blocked_d1_cannot_seal`
- `test_m31_seal.SealTests.test_cannot_replace_an_existing_seal`
- `test_m31_seal.SealTests.test_changed_source_payload_is_rejected_before_success`
- `test_m31_seal.SealTests.test_different_candidates_are_rejected`
- `test_m31_seal.SealTests.test_insufficient_development_coverage_cannot_pass_from_metadata_alone`
- `test_m31_seal.SealTests.test_label_column_in_score_cache_is_rejected`
- `test_m31_seal.SealTests.test_mismatched_runtime_requirements_cannot_seal`
- `test_m31_seal.SealTests.test_modified_sealed_payload_is_rejected_on_replay`
- `test_m31_seal.SealTests.test_parity_detects_row_order_and_labels_independently`
- `test_m31_seal.SealTests.test_rewritten_local_manifest_cannot_replace_the_external_pin`
- `test_m31_seal.SealTests.test_seals_and_replays_inputs_without_opening_test_labels`
- `test_m31_seal.SealTests.test_source_code_drift_is_rejected_on_replay`

## File hashes at the core commit

```text
f089ff5c158c9b868046114575147ee7d2e39d71cdd3788ae3ffc9d5babf6fb1  src/qpaf/jev/__init__.py
0a04d64a7c379a0f91fcdd4582675ff1add54eb22bc8658ad0626aaa30b547df  src/qpaf/jev/contracts.py
a4b7153f924037fa32220c2253638d1a087aaa08fd472397b7d3ffb378625d02  src/qpaf/jev/data.py
b34378d02a9cafe496a260a9b8016afcba02ac6593add19ef85e269fe96a45d6  src/qpaf/jev/evaluation.py
7ce3265a1c6aec69441aa0641f4e558d53ce10b42452c0f226ad46b1ff4a210a  src/qpaf/jev/cli.py
8440b02fbcbdd52b40504c6170c68e42049fe2137eba60127827e819d273819f  scripts/run_jev.py
c9ea10aa0bcce5f3eaefb8ac94f66272c5c938214392f4a84c2940ac30b9f995  tests/test_jev_contracts.py
f25da71bf5a4e097c0da413e5a36a574cae2521c5cf57841d4384b5ab3e3c1ef  tests/test_jev_evaluation.py
a43162cc4430e901e4f5c780ec2bcf14f22ca0137d2b25712f71a5231c84cf27  tests/test_jev_cli.py
```


## Review fix round 1

Reviewed [Task 1 findings](task-1-review.md) against `516b7879c57d2cce899a1c8f415fe789ff8fe595`. Applied the installed Superpowers 7.0.1 review reception, systematic debugging, TDD and verification skills. The fix commit is `7cd81b0f13baaa4a94eaef589d4b933e38cdf214`.

- Split selection resolves the complete requested cohort before reading raw rows. In native mode, an explicit partition supplies IDs from the split manifest. An explicit `--query-ids` file can narrow that partition and must contain only IDs assigned to it. Imported pools reject missing required query IDs before any output.
- ViMDoc evaluation requires a complete page-to-document mapping. Old F9 pair bytes and existing score-cache hashes remain usable with `evaluate --units FILE`.
- Both report formats include ranking scope, label unit and synthetic status. Comparison rejects explicit incompatibilities. Legacy comparisons with unspecified scope or label unit report `unknown`. An unspecified synthetic status is JSON `null` and CSV `unknown` unless a compared report establishes synthetic status.
- Preparation diagnostics name missing split and score files and show the corresponding prepare flags.

### RED and GREEN

The same targeted command ran before and after the fix.

```powershell
python -m unittest -v tests.test_jev_cli.CliTest.test_demo_writes_cache_and_evaluation_marked_as_synthetic tests.test_jev_cli.CliTest.test_imported_f9_bytes_allow_existing_cache_evaluation tests.test_jev_cli.CliTest.test_partition_requires_the_complete_expected_import_cohort tests.test_jev_cli.CliTest.test_native_partition_uses_manifest_ids_instead_of_held_out_defaults tests.test_jev_cli.CliTest.test_missing_import_sidecars_name_the_path_and_next_command tests.test_jev_evaluation.EvaluationTest.test_known_vimdoc_requires_page_to_document_mapping tests.test_jev_evaluation.EvaluationTest.test_comparison_preserves_matching_protocol_fields tests.test_jev_evaluation.EvaluationTest.test_comparison_rejects_explicit_protocol_mismatches tests.test_jev_evaluation.EvaluationTest.test_missing_legacy_protocol_fields_remain_unknown
```

Before implementation, exit 1 and `Ran 9 tests in 3.505s`, `FAILED (failures=7, errors=3)`. The import silently accepted an incomplete test cohort, native validation selected the held-out page `b` and failed on its OCR, the ViMDoc path accepted missing document units, the score/split errors omitted `Next command: prepare`, comparison accepted contradictory synthetic status, and three protocol assertions raised `KeyError: 'ranking_scope'`.

After implementation, exit 0 and `Ran 9 tests in 4.278s`, `OK`. The partition plus contracts run also passed all 13 tests, and the direct evaluation plus CLI tests for ViMDoc units passed both tests.

`python -m unittest tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` exited 0 with `Ran 31 tests in 7.286s`, `OK`. Python 3.11 with `-I -S -m unittest discover -s tests -p 'test_jev*.py' -q` exited 0 with `Ran 31 tests in 3.091s`, `OK (skipped=2)`. Both skips required optional PyArrow. The controller scoped this review round to the focused suite. The earlier full-suite evidence remains above. `git diff --check` passed and all six changed files were LF.

### Hashes of files changed by the fix

```text
f2f0f7f7e62ee41e3ed48ec75453c1fb43fbec293e91e41c5a7efbf91dd30993  src/qpaf/jev/contracts.py
9e1d5b6d5843ae1734f787e81e454983002d4a71ce03421fef8c871c167572b1  src/qpaf/jev/data.py
b839fcd3edfacb1605072b2d418da5683fb657dc654ff17f3dfe27b2b4e154ef  src/qpaf/jev/evaluation.py
b43c04e42e5f8215bb0fe67d174793293b88a53708321cc6456a768ac595d8fc  src/qpaf/jev/cli.py
b1b8db9181fde832ce1a618255c2f7095d2e1d3cc0c4e0766385bde2992f1019  tests/test_jev_evaluation.py
22ad0e420ba0c3737fe3c8473d01b5142b03e9a397e38ae6ddd8abddb53c82e1  tests/test_jev_cli.py
```
