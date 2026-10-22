# M3.6: user-authorized 5 GiB resource rerun

This revision records a new system measurement at the user's request. It does
not amend the original 4 GiB results or their BLOCKED technical review. The user
asked to increase CPU RAM to 5 GB, finish the task if the evidence supports it,
and provide an English pull request describing the work, results, source, and
next owners. In the preceding discussion, 5 GB meant **5 GiB = 5,120 MiB**.

## Change and invariant contract

- One new Modal A10 invocation, two sequential isolated method processes,
  CPU request/limit 2 cores, RAM request/limit `(5120, 5120)` MiB.
- Same frozen QARF/QPAF checkpoints, input hashes, query order, 20 warm-ups,
  1,122 distinct measured queries, three passes, FP64 eager batch size 1,
  Python 3.13.7, Torch 2.11.0+cu126 and immutable base OCI image.
- Existing gates remain median online fusion <=10 ms/query, peak learned
  fusion CUDA allocation <1.50 GiB, and validation parity <=1e-7.
- No labels, training, model/candidate changes, test quality evaluation,
  remaining seeds, confirmation runs, or G2 decision.
- New source commit, allowlisted bundle, authorization with an external SHA256
  pin, image binding before invocation, and create-once result namespace.
- One invocation, no automatic retries, existing 900 s watchdog, operational
  budget target USD 0.50. This is not a provider-enforced dollar cap.

## Additional source review before execution

The original fusion literature synthesis remains in revision m3.6-002. This
supplement investigates resource accounting using primary documentation:

1. [Modal resources](https://modal.com/docs/guide/resources): memory is in MiB;
   a tuple specifies request and hard limit. A completed job alone does not
   establish the measured memory peak.
2. [Linux getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html):
   Linux `ru_maxrss` is a process high-water mark in KiB, not a setting or
   container-wide accounting counter. Convert with 1,024 bytes/KiB.
3. [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html):
   `memory.current` is current charged usage; `memory.peak` records the peak;
   `memory.max` is the limit; `memory.events` reports OOM events. Locate the
   process's memory cgroup through `/proc/self/cgroup` and mount roots from
   `/proc/self/mountinfo`. Do not substitute current usage for a missing peak.
4. [Linux proc filesystem](https://www.kernel.org/doc/html/v6.14/filesystems/proc.html):
   `/proc/self/status` exposes RSS/high-water counters; `smaps_rollup` summarizes
   current mapping accounting. These remain process interfaces.
5. [gVisor resource model](https://gvisor.dev/docs/architecture_guide/resources/):
   sandbox process accounting may be approximate. This is a hypothesis until
   the actual deployment evidence identifies its backend and accounting.

These sources were reviewed during this session before the new invocation.
The prior additional deep-research request was queued as
`01a16479-6381-72ac-abb1-d34de7c0c970`; its completion/output is not available to
this resumed tool session, so no completion claim is made for that request.

## Diagnostic design and interpretation fixed before execution

Read `/proc` and cgroup files before/after imports, payload loading, CUDA
initialization, checkpoint load, validation parity, warm-up, and each pass.
Read the parent container process before and after both workers. All reads
occur outside timed per-query intervals. Preserve raw counters, units, process
IDs, kernel identity, controller paths, missing-file errors, and assessment.
Do not reset cgroup counters, allocate artificial pressure, alter models,
change precision, or reduce the workload to obtain a desired result.

Report process high-water and container peak independently. A process value
below 5 GiB alone cannot verify the whole container's peak. In-container cgroup
verification requires an observable peak, matching 5 GiB limit, and OOM event
evidence without OOM. A cgroup interface is reported as such and is not an
independent physical-host measurement. Missing controller/peak evidence remains
UNAVAILABLE. Exceeding the configured limit or unexplained inconsistent
accounting remains a technical issue; no automatic acceptance follows from
increasing the resource configuration. Human owner acceptance and G2 remain
separate decisions.
