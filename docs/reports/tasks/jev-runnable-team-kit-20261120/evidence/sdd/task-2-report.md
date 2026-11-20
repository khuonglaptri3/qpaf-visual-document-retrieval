# Task 2 implementation report

2026-11-20. Task 2 resumed on `implementation/jev-team-kit-20261120` at `c56acf284724fe2dac97c6bb5447adadbf3b690d` under the existing authorization. The work followed the [task brief](task-2-brief.md), [spec](../../superpowers/spec.md), and [plan](../../superpowers/plan.md). The adapters, trainer, worker, pins, and initial tests were recovered from the preceding implementer's working changes after its usage limit. Original RED logs were unavailable at resumption. The results below come from fresh commands.

Read the installed Superpowers 7.0.1 `using-superpowers/SKILL.md` and `using-superpowers/references/codex-tools.md`. Applied `systematic-debugging/SKILL.md`, `test-driven-development/SKILL.md` with `test-driven-development/writing-good-tests.md`, and `verification-before-completion/SKILL.md` to the reproduced failures and final checks. The installed root is `C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/`. Read Modal skill 1.5.5 at `.agents/skills/modal/SKILL.md` in the main workspace and followed its offline SDK and job boundaries for this task. The pinned API and runtime material is recorded in the [model integration notes](../model-integration-notes.md).

## Delivered behavior

- `score` accepts BGE classifier logits, Qwen yes/no log-odds with its reranker prompt, and Kev Noul probabilities from official `Checkpoint`, admission, and readout APIs. It supports a local checkpoint with its base and head. Score chunks bind model, code, environment, precision, cap, batch geometry, and original pair bytes. The final cache preserves pair order and validates input bytes before publication.
- `export-train` creates boolean Noul JSONL for assigned train query/page judgments and puts export hashes and record counts in an adjacent manifest. Unjudged negatives are opt-in. Document-level and leaky group inputs are rejected.
- `train` prints the exact official command by default. Explicit `--execute` checks the export hash, snapshots input bytes, and runs the pinned trainer. Base and Kev initialization use the same configured backbone, with controlled learning rates, seed, adapter/head settings, and budget. The completed checkpoint contains run provenance and an adapter/head/config digest set.
- Linux and Modal launch `python -m kev.train`. On Windows an absolute script path loads the official modules in the child process. `kev.train` receives actual peak working set from psutil. The `kev.suite` import receives a POSIX lock interface that raises if invoked, with a Linux instruction. That lock is for suite orchestration, outside local JSONL training. Official suite digest functions remain available to warm-start provenance. Model and training dependencies load on demand.
- `scripts/modal_jev_rerank.py` validates score/train options and plans the job offline, selects the matching requirement set, and binds the worker to the named Volume. A top-level `--execute` is required for submission. The controller constructed the image/function locally with SDK 1.5.5. [SDK smoke](../modal-sdk-api-smoke.json)

## Fresh regression results

The runtime commands below use the external Python 3.13.7 at `C:/Users/lanph/AppData/Local/codex-jev-cpu-runtime-20261120/Scripts/python.exe`, with Torch 2.8.0+cpu, Transformers 5.17.0, PEFT 0.21.0, Accelerate 1.15.0, NumPy 2.5.3, and Kev source `5e22da2be8ecb2f38790d81d87bb55b0be61a6e2`. Model tests set `JEV_MODEL_TESTS=1`, `HF_HUB_OFFLINE=1`, and `TRANSFORMERS_OFFLINE=1`. Named full runs also set `OMP_NUM_THREADS=1`. Fixtures use randomly initialized local HF models and synthetic labels. All generated weights stayed in temporary directories.

- The direct named test `python -m unittest tests.test_jev_backends.ActualRuntimeTest.test_real_baseline_forwards_and_trained_checkpoint_reload -v`, with the runtime flag off, initially failed to import the discovery-only fixture module. The same command exited 0 after selecting the fixture import based on package context, with one deliberate skip. The full opt-in command imports the named modules and executes the test.
- `python -m unittest discover -s tests -p test_jev_backends.py -k real_baseline_forwards_and_trained_checkpoint_reload -v` exited 1 after 139.996 seconds. Actual BGE and Qwen logits matched independent Torch forwards. The official Windows trainer failed before optimization because `kev.train → kev.full_ft → kev.suite` imports POSIX-only `fcntl` unconditionally. Inspection located the single lock in `kev.suite.file_lock` and established that the local `--data` run does not call it.
- `python -u -m unittest tests.test_jev_backends tests.test_jev_training tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` exited 1 after 144.034 seconds with 38 passing tests and one failure. The child-scoped suite binding let the official trainer perform one optimizer step and save the checkpoint. Reload reached the real Kev model, where the precision guard compared its string `float32` with the Torch dtype. Verified the representation in the pinned `DecisionModel.dtype` property and changed the guard to compare canonical names.

## Final verification

- The same full opt-in command exited 0 in 133.078 seconds. All 39 Jev tests passed. BGE scored four pairs with 8 input tokens and matched the independent BERT classifier. Qwen scored four pairs with 1,204 tokens and its first score matched an independent next-token yes/no computation. The models and tokenizer were built locally.
- The official trainer processed two train-only Noul requests on Windows CPU with world size 1. It performed exactly one optimizer step with 78 forward tokens and saved `adapter_model.safetensors`, `adapter_config.json`, `head.pt`, `training_config.json`, `training_metrics.json`, and `jev-run.json`. In the preceding runtime run, the same trainer completed its step in 34.332 wall seconds, recorded 446,332,928 peak RSS bytes, and all four file digests in `jev-run.json` matched independent SHA-256 calculations. That preceding run isolated the reload error described above.
- The final run loaded the saved adapter and pointer head using official `Checkpoint` and returned unrounded true probabilities `[0.4989367127418518, 0.49899986386299133, 0.4988594949245453, 0.4989033341407776]`, in pair order, using 316 input tokens. The runtime test creates its data in a temporary directory and executes the CLI from there.
- `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -q` exited 0 in 9.215 seconds with 36 passes and three skips for the optional runtime and PyArrow fixtures. The earlier no-opt-in discovery command, with site packages enabled, passed 38 tests and skipped the opt-in model test.
- `python -I -S -m compileall -q src/qpaf/jev scripts/run_jev.py scripts/train_jev_reranker.py scripts/modal_jev_rerank.py tests/test_jev_backends.py tests/test_jev_training.py` exited 0. Isolated `--help` succeeded for `run_jev.py score`, `export-train`, and `train`, plus both worker scripts.
- `python -I -S scripts/modal_jev_rerank.py --volume jev-test train --data inputs/train.jsonl --out runs/kev --init base` printed a `jev-kev.txt` plan with the trainer's execution flag inside the worker argv. The isolated BGE score plan selected `jev-baselines.txt`. Both worker plans used `/data` and relative paths. The test suite also verified Kev score planning with site packages disabled.
- The staged whitespace check passed and Git identified LF endings for the Task 2 source, config, requirements, and test files. The legacy full-suite run remains documented with its named failures and dependency errors in the [Task 1 report](task-1-report.md). It was run once at the controller's direction.

The runtime evidence covers synthetic CPU forward passes and a base-initialized optimizer step. Full-size checkpoints, private data, warm-start training, CUDA, and hosted Modal execution remain unverified. Modal verification covered local planning and SDK function construction.

## Source SHA-256

```text
e2cdd36c09fbb1319e4d71d13fffeba73c0b75e31053342854c2012a6f0ae45b  configs/jev/models.json
2c81b45af82cd1d27777826813f293d4ad3d32dc0245fe95b24bc20fef6b64d1  requirements/jev-baselines.txt
ee1870be5b52516516a883db4d7a4157df9cb0749479f88721be13b8ccd0e84b  requirements/jev-kev.txt
288db98721cfb4be79ff6bbe63e9860ca58adc8e56439049af76da3d426b0085  scripts/modal_jev_rerank.py
5fee4893b3624dbbb938475ee3bb7dbdf280b8c4530d053eac2b2171c3e5134e  scripts/train_jev_reranker.py
1acbf226480156940a189b64dd3f51977d880616f2188997dd881e917b610561  src/qpaf/jev/backends.py
b98aca7aabfe86ddd70a7f5ecf87cf75fa741a40a98297b7497b4b15edf45047  src/qpaf/jev/cli.py
878800d20daaaf4f1296a4bb745e444896ee99b238452ac6dea618f3600f49d7  src/qpaf/jev/training.py
27f4577c2f8618f7d5e9891f9b565911dec7bac74f091b49b69206c6d7027d95  tests/test_jev_backends.py
54ceb76cb69f3dbe432775491f6e6bff1277021a41226f6e6280919a0b013e01  tests/test_jev_training.py
```
