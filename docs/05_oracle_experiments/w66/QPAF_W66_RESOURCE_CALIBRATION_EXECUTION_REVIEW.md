# W66 synthetic resource calibration: preparation and execution review

**APPROVED FOR ONE CODEX INVOCATION; NOT YET STARTED.** The full exploratory-24 W66 invocation remains a resource NO-GO under the current evidence. This separate engineering calibration measures one synthetic full-page W66 search and the missing runtime/resource controls. It is not a W66 retrieval result, a formal P1-03 run, training, or permission to execute the 24-query study.

Approval recorded at `2026-09-09T08:23:12.8745123Z`. The user's exact text was: "Ok I approved, you can do whatever it need to proceed w66 but precisely". This approval is bound only to protocol `vidoseek_w66_resource_calibration_v1`, actor `codex`, one local CPU invocation, a 21,600-second total cap, one worker/thread, Arrow CPU/I/O pools fixed at one, the 2-GiB process-tree private-byte limit, 100-MiB output limit, admission thresholds, and zero retries. It does not authorize the full 24-query W66 run.

## Frozen calibration contract

| Item | Prepared contract |
| --- | --- |
| Selection | Audit index 1129, query `05e2dbaf2d299e33a0e7bf92a434214c84381bf1_5`; selected only because it had the slowest W7 query timer |
| Input materialization | The frozen 24-query subset, 129,240 rows, every original column except `relevance` |
| Synthetic label | Sort the selected query's 5,385 page IDs ascending; relevance 1 at zero-based index 2692 and 0 elsewhere |
| Search | One W66 Global profile pass and one unchanged QARF/QPAF query search, maximum two sweeps |
| Bootstrap | Existing mean and ratio bootstrap functions on fixed 24-element synthetic inputs, 10,000 resamples, seed 20260820 |
| CPU | Local CPU, one worker, one numeric-library thread, Arrow CPU/I/O pools each fixed and checked at 1 |
| Cost cap | Proposed 21,600 seconds; this is not a completion guarantee |
| Memory | Combined parent/worker private bytes at most 2 GiB; abort below 2 GiB host-free memory |
| Admission | At least 4 GiB free physical memory, 5 GiB free disk, and absent output namespace |
| Output | At most 100 MiB in `runs/vidoseek_w66_resource_calibration_v1/` |
| Attempts | Exactly one Codex invocation approved; zero retries; the attempt is consumed when `_ATTEMPTED.json` is created |

The worker reads the Parquet table with an explicit column projection that excludes `relevance`, adds only the deterministic synthetic label after validation, and stores synthetic metrics only inside hash-sealed calibration checkpoints. The engineering result reports timing, memory, thread-pool, checkpoint, and sweep-path evidence; it must not interpret synthetic metrics as retrieval quality.

The parent process samples parent-plus-worker private bytes, working sets, CPU times, free memory, disk, and output bytes once per second. It terminates the worker on timeout or a resource breach. The worker independently watches the parent's PID and creation time. Windows sleep inhibition is active only for the attempt and is cleared afterward. Stage logs and telemetry are flushed to disk.

The calibration creates a distinct run plan, one Global checkpoint, one Global-selection checkpoint, and one query checkpoint. It then reopens all three and requires byte/content identity without rerunning the search. These checkpoints are explicitly ineligible for the scientific W66 run.

## Commands and approval boundary

The read-only command is:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe scripts\calibrate_vidoseek_w66_resources.py preflight
```

The following command is authorized exactly once under the approval recorded above:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
C:\Python313\python.exe scripts\calibrate_vidoseek_w66_resources.py run --actor codex
```

The authorization is valid only from a clean direct-child commit that changes this review, the calibration config, and the focused test that separates the live approved state from a deep-copied closed refusal fixture. If admission, provenance, source, environment, or thread guards fail before `_ATTEMPTED.json` is created, the run must not start. After that marker exists, completion or failure consumes the sole invocation and no automatic retry is allowed.

Completion would still be engineering evidence only. The full 24-query W66 timeout remains unset until the calibration output is independently reviewed; a failure consumes the one attempt and requires a new recovery/resource decision.
