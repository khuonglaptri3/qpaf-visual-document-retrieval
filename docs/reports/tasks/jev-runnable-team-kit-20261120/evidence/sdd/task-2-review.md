# Task 2 review

## Spec compliance

- ❌ Issues found. Resumable chunks can omit the actual Kev backbone and runtime identity from their fingerprint. Modal accepts locally detectable invalid jobs before submission. The training wrapper's saved provenance does not account for records filtered by the official trainer.
- ⚠️ Full-size checkpoint downloads and forward passes, CUDA, hosted Modal execution, and warm-start optimization remain unverified. Modal SDK 1.5.5 image and function construction was checked locally without submitting a job. The implementer's recorded 39-test opt-in run covers tiny offline CPU forwards, an official base-initialized optimizer step, and checkpoint reload.
- ⚠️ The source reports original RED logs unavailable after the handoff. The report records fresh failures and reruns for the Windows and reload bugs. It does not establish original RED provenance for every recovered change.

## Strengths

- `backends.py:54` and `:100` use real classifier logits, prompt-conditioned Qwen log-odds, and official Kev checkpoint and Noul readout APIs. The Kev adapter bounds the packed input and retains the unrounded probability. `test_jev_backends.py:85` checks actual tiny model forwards, official optimizer execution, and a scored adapter/head reload.
- `backends.py:192` and `:264` check chunk identities, digests, finite score counts, and exact pair bytes before publishing the ordered final cache. `test_jev_backends.py:50` covers partial failure, resume, stale settings, and an invalid score.
- `training.py:17` applies the shared split guard and exports boolean Noul labels from the assigned train pages. Document mapping is rejected before label lookup. `training.py:89` applies the same base and command controls with and without warm initialization, and disables replay and augmentation. `training.py:148` hashes the completed adapter, head, and configuration artifacts.
- `train_jev_reranker.py:10` confines the compatibility imports to the official child modules. It measures peak working set and explicitly rejects the POSIX lock call. `training.py:85` uses the unmodified official entry point on Linux. `modal_jev_rerank.py:55` keeps cloud execution behind the outer flag. The diff preserves standard-library-only imports for help, doctor, and demo.

## Issues

### Critical

None.

### Important

1. **Local Kev fingerprints can identify a different backbone from the one scored.** `src/qpaf/jev/backends.py:179` hashes an optional local path named by `adapter_config.json`. The pinned `kev/checkpoint.py:233` and `:293` load the tokenizer and backbone using `Meta.base` and `Meta.base_revision` from `head.pt`. A checkpoint whose references differ can keep its chunk fingerprint while the loaded local base changes. A local adapter can also refer to an unpinned Hub base whose moving revision never enters the fingerprint. Derive the score identity from the official metadata, hash the actual local dependencies or enforce an immutable Hub revision, and ensure the loaded local checkpoint still matches that identity before caching.
2. **Runtime changes can pass the resume check.** `src/qpaf/jev/backends.py:159` records package versions and `sys.platform`, and `:185` records the generic device string. Changing the worker GPU with `scripts/modal_jev_rerank.py:36` can keep the fingerprint on the same Volume. CUDA hardware and runtime can affect numerical scores and the recorded memory peak. A same-version Kev distribution at another commit can also pass an entirely cached run because `:103` verifies the source only during adapter load. Bind chunks to the actual runtime/device identity and validate the mandatory Kev source pin before reuse.
3. **Concurrent initializers can corrupt a shared chunk directory.** `src/qpaf/jev/backends.py:219` checks for a config and then publishes it using a replacing atomic write. Two processes with different settings can both observe an empty directory, overwrite each other's config, and publish chunks under the same names. Subsequent legitimate resumes can then reject their own directory as stale. Claim the fingerprint atomically before writing any chunks so competing configurations fail deterministically.
4. **Detectable invalid settings can reach a paid worker.** `scripts/modal_jev_rerank.py:42` parses the inner CLI but does not run the pure validation performed by `backends.py:187` and `training.py:72`. For example, score `--batch-size 0` and train `--lr nan` pass the offline check and can reach `job.remote` at `:67`. Share pure settings validation with the planner before submission. Keep checks that depend on staged files inside the worker.
5. **Training provenance misses records dropped for context length.** `src/qpaf/jev/training.py:130` stores the export count, then `:148` records checkpoint digests. The pinned trainer filters custom records before training at `kev/train.py:102`, reports drops only in stdout, and writes `requested_records` based on the post-filter set with `rejected_records: 0` at `:669`. The saved metadata for a long-page pilot therefore does not state the gap between exported and eligible records. Preserve the upstream admission/drop count alongside the export count and separate it from rows visited under the step budget.

### Minor

- `src/qpaf/jev/training.py:140` writes the deterministic snapshot before entering the cleanup scope. A write error after exclusive creation can leave a partial snapshot that blocks retries. Include the write in cleanup for the snapshot owned by this invocation.
- `src/qpaf/jev/training.py:95` passes through the optimizer budget. The unchanged, pinned upstream scheduler setup at `kev/train.py:588` has a ten-effective-step edge case: Torch 2.8.0 `OneCycleLR` with `pct_start=0.1` creates a zero-length first phase and divides by zero on initialization. This is a source-inspected dependency limitation. The reported one-step smoke does not cover it.

## Assessment

**Task quality:** Needs fixes.

**Review evidence:** Assessed `c56acf2..e108880` using the [review package](../review-reconstruction.md), [brief](task-2-brief.md), and [implementation report](task-2-report.md). Checked the pinned Kev checkpoint, encoder, training, and JSONL loader sources for the cited API contracts, plus the installed scheduler source for the budget edge case. Checked the unchanged core writer and split guard only for the contracts consumed by the diff. No test suite, model load, or cloud job was run by this reviewer.