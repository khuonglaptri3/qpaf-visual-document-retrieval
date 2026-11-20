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

## Review fix round 1

2026-11-20. The [review](task-2-review.md) assessed `e108880f16bb2a2de57c9e8d3de23c39ae0eed1c`. The preceding source hashes describe that commit. This round's source and regression tests are in `50d27bc3d5b5b615b2e802fc51dc49f7eb513c96`. The review used Superpowers 7.0.1 `receiving-code-review/SKILL.md` with the previously loaded systematic debugging, test-driven development, and verification workflows. Execution stayed in the existing worktree and used the same external CPU environment.

- Local Kev score identity now reads the pinned official checkpoint metadata. The adapter or full checkpoint is hashed, and the actual local base path, tokenizer, and backbone files are hashed from `Meta.base`. A Hub backbone in a local checkpoint requires a full immutable commit in `Meta.base_revision`. The adapter verifies the metadata it loads and the scoring loop verifies the local hashes again after loading, before its first chunk can be written.
- Fully cached reuse checks the installed Kev source commit and probes the actual Torch build and device. The runtime fields cover CPU capability and thread count or selected CUDA device class, compute capability, memory and SM count, CUDA build, NVIDIA driver API version, cuDNN and precision settings. Physical accelerator UUIDs are outside the fingerprint so sequential allocations of the same device class can reuse compatible chunks.
- Cache configuration is published by renaming a complete nonempty staged directory on the same coherent filesystem. Two initializers targeting the same directory with different configurations produce one winner and one stale-configuration error. Previous chunk directories require a fresh `--chunks` directory under the new identity scheme. Modal workers on the same Volume share the writable `/data/.huggingface` cache. Use separate named Volumes for independent concurrent jobs. Run jobs strictly sequentially when reusing a shared Volume. [Modal Volume consistency](https://modal.com/docs/guide/volumes#filesystem-consistency)
- The offline Modal planner and workers share pure score and training setting validation. The planner rejects invalid options before importing the SDK, including when outer `--execute` is present. Staged file and directory checks run inside the worker.
- The run manifest records exported, trainer-admitted, and context-dropped rows separately from scheduled, actual, and unvisited record visits. The pinned trainer records post-filter `requested_records` as admitted rows multiplied by epochs. Its `records_seen` measures processed visits. Training uses a single JSONL source with replay and augmentation disabled. A failed write now removes the snapshot created by that invocation.

### Verification

- RED via `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -v` on the reviewed source exited 1. It ran 48 tests in 11.933 seconds with 10 failing assertions and three optional skips. The failures covered cached runtime and source changes, two competing successful cache writes, the actual local base mutation, an unpinned Hub base, model-load mutation, invalid score and train planner settings, missing admission provenance, and a partial snapshot left after an injected write failure.
- GREEN via `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -q` exited 0. It ran 48 tests in 14.505 seconds with 45 passes and three optional skips. The final isolated checks synchronized both test initializers at the rename boundary, exercised invalid Modal plans with and without outer `--execute`, and accepted a valid training plan whose staged files exist only on the Volume.
- `python -u -m unittest tests.test_jev_backends tests.test_jev_training tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` exited 0 with all 48 passing in 144.766 seconds. The run used the opt-in and offline environment values documented above. Real BGE and Qwen forwards passed. The official trainer reported one drop from three records at a 384-token state limit, admitted two, and performed one optimizer step with 78 forward tokens. The saved counts showed three exported rows, two admitted, one dropped for context, two scheduled visits, one actual visit, and one unvisited. The adapter and head reloaded through the real Kev API, verified the local base path in the score manifest, and returned `[0.4989367127418518, 0.49899986386299133, 0.4993443489074707, 0.4989033341407776]` with 369 scored input tokens.
- `python -I -S -m compileall -q src/qpaf/jev scripts/modal_jev_rerank.py tests/test_jev_backends.py tests/test_jev_training.py`, isolated help for the Modal worker and local score/train commands, and `git diff-tree --check HEAD^ HEAD` all exited 0.
- An isolated Torch 2.8.0+cpu probe constructed AdamW and `OneCycleLR(pct_start=0.1)` with total steps 1, 9, 10, and 11. Steps 1, 9, and 11 initialized. Exactly 10 effective optimizer steps raised `ZeroDivisionError: float division by zero` at scheduler initialization. The effective total is the available steps across epochs limited by a positive `--max-steps`. This includes an uncapped run that naturally totals ten. The pinned scheduler is unchanged. The tested end-to-end smoke uses one step.

CUDA profiling and live Modal execution remain unverified. The legacy suite was not rerun in this fix round.

### Fix-round source SHA-256

```text
79a0a3db1f977328cab279e309a9ffa9067b58ad77153ba033b2c055d0bb7f69  scripts/modal_jev_rerank.py
8bb32b36082490b5d909bd8959a063322d194f2e081bec6c7a33b2da237f6a7c  src/qpaf/jev/backends.py
1e0eea92f9bad295694effbf3a69d15cb25aa46df672f59e987dab7ab59d52a1  src/qpaf/jev/training.py
528d635b65e96fd6588d96b909e57e6f65a7f81de78b54ded0e7b784d13247c2  tests/test_jev_backends.py
124f5ba3d36eba60527bf1b5ae3aaea068e00be377505c78e40de779fb49261c  tests/test_jev_training.py
```

## Review fix round 2

2026-11-20. Addressed the two open findings and Volume wording in the [scoped review](task-2-fix1-review.md) of `d8df0554e260a7eaac1c442f1d889d50ce627ec7`. The source and tests are in `50147cc1af1be638d76de8ece8bdb28a1d90a65a`. This round used the same Superpowers 7.0.1 review, test-driven development, and verification workflows.

- Local model hashing follows the pinned Transformers default selection between root safetensors and PyTorch weight files or indexes. A selected index contributes every referenced shard, including files under `.cache` and through directory symlinks. Repeated parameter references and resolved aliases share a file digest. The existing post-load identity check uses the same dependency coverage.
- The shared training validator accepts the Torch seed range `[-9223372036854775808, 18446744073709551615]`. Both entry points check the range before execution, including outer Modal `--execute`. The pinned trainer, its dependency versions, and the ten-effective-step scheduler limitation are as documented above.

### Verification

- Windows RED via `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -k shard_index -k torch_seed_range -v` exited 1. Three tests ran in 2.930 seconds, with five failing assertions and one symlink privilege skip. The hidden shard did not change the hash. Local dry-run accepted both invalid seeds, and the invalid Modal requests reached the SDK import. The same focused command exited 0 after the fixes in 4.650 seconds, with two passes and the one conditional skip. Both inclusive seed boundaries were preserved in the generated argv, and both adjacent out-of-range values were refused with exit 2.
- In the existing WSL Ubuntu Python 3.14.4 runtime, `python3 -I -S -m unittest discover -s tests -p test_jev_backends.py -k shard_index -v` exposed both shard omissions before the fix. The same command exited 0 after the fix with both cases passing in 0.006 seconds, including the nested directory symlink.
- `python -I -S -m unittest discover -s tests -p 'test_jev*.py' -q` exited 0 on Windows with 47 passes and four skips in 27.661 seconds. The corresponding `python3` command in WSL Ubuntu exited 0 with 48 passes and three optional runtime/data skips in 29.649 seconds.
- `python -u -m unittest tests.test_jev_backends tests.test_jev_training tests.test_jev_contracts tests.test_jev_evaluation tests.test_jev_cli -v` exited 0 with 50 passes and the Windows directory symlink skip in 245.033 seconds. The run used the same pinned CPU and offline flags. The fixture saved six real tiny Qwen shards and moved one indexed shard into `.cache`. Real BGE and sharded Qwen forwards passed. The official Kev trainer admitted two of three rows, executed one step with 78 forward tokens, and saved the adapter and head. Reload against the sharded base returned `[0.4989367127418518, 0.49899986386299133, 0.4993443489074707, 0.4989033341407776]` with 369 input tokens.
- `python -I -S -m compileall -q src/qpaf/jev scripts/modal_jev_rerank.py tests/test_jev_backends.py tests/test_jev_training.py`, isolated help for the local train and Modal worker commands, and `git diff-tree --check HEAD^ HEAD` all exited 0.

### Fix-round source SHA-256

```text
4319c7a19aa097fc454bf29f59be405b144e62979ffe4b93938d5063bb95f559  src/qpaf/jev/backends.py
4b403b4b1027fa41024f8ca250ba161f10039b5e47303fc2acb9e7140ba388af  src/qpaf/jev/training.py
58e2eabfa58824b44acca1a40dac56280fffd2c59774ad6616b4f65c92cddcb7  tests/test_jev_backends.py
7183c35670296cbccd87cf6189928a7e3968ddbf2ef5ac7f02bb84fe80ca9a4c  tests/test_jev_training.py
```
