# M3.6 memory-evidence criterion revision — 2026-10-23

**Decision owner:** Tấn Phát — Research Lead / Protocol Owner. The
[M3.6 handoff](../m3.6-004/technical_review.json) assigns "Resolve any proposed
measurement-policy exception explicitly" to this role.
**Status:** `APPROVED_BY_RESEARCH_LEAD`
**Scope:** how blocker `M3_6_CPU_RSS_ACCOUNTING_001` can be closed. This
revision changes no latency, CUDA, parity, workload, model, seed, threshold or
G2 rule.

## Old rule

The [m3.6-004 pre-execution memory review](../m3.6-004/pre_execution_memory_review.md)
(SHA-256 `5aa05a327ec8a591efcb6fa77edf7dc7aa3c36476e4210d186d7c9a71f2ad838`)
said: "In-container cgroup verification requires an observable peak, matching
5 GiB limit, and OOM event evidence without OOM." gVisor does not expose
`VmHWM`, `memory.max_usage_in_bytes` or `memory.oom_control`, and Modal exports
only one-minute averages and sample percentiles. So no observable peak exists,
and the issue stayed open
([issue update](../m3.6-004/telemetry_issue_update.json)).

Modal's documentation says GPU containers run only on the gVisor runtime. The
VM runtime, which has a full kernel with peak counters, does not support GPUs.
So an exact peak for this GPU workload cannot be measured on Modal.

## New rule

Container memory evidence for M3.6 is a **Modal-enforced upper bound**,
not a peak. It is valid only if both of the following hold:

1. **Enforcement is demonstrated** in the same function shape that A02/A03 used
   (A10, `cpu=(2, 2)`, hard limit `memory=(4096, 4096)` MiB, same base image
   and pinned packages, single-use container, no retries configured). Two
   controls run in fresh containers:
   - *below*: touch 2,048 MiB. It must complete;
   - *above*: touch 4,608 MiB. It must fail with an out-of-memory attribution:
     the word `OOM` / `OOMKilled`, `out of memory`, `memory limit` or
     `exit code 137` in its error or in a provider exit reason.

   The provider export must show exactly one successful and one failed input.
   Every container beyond the below control's must have errored, so any Modal
   retry can only be a failed above-limit attempt. Retries are counted and
   reported. If the below control fails, the above control is not run.

   `scripts/m36_memory_probe.py` `classify_controls` must return
   `ENFORCEMENT_DEMONSTRATED`. If the above control completes on any attempt,
   including a provider retry, the result is `ENFORCEMENT_NOT_DEMONSTRATED`. An
   unattributed failure is `INCONCLUSIVE`. Either outcome leaves the blocker
   open.
2. **Each bounded run completed under its hard limit with no failed call.**
   - A02 under 4,096 MiB: `_SUCCESS.json` SHA-256
     `12504f08cafdb2d43fe2d9454cf89795c2626438751e0cf413aeec59db4abb59`;
     provider export [`provider_stats_a02.json`](provider_stats_a02.json):
     1 success, 0 failed inputs, 1 container, 0 container errors.
   - A03 under 5,120 MiB: `_SUCCESS.json` SHA-256
     `e8895fd997e2ce26437566a7ed3097220a5c7d153d6b7cef3d709bacdc3e3c7f`;
     [`provider_stats_5gib.json`](../m3.6-004/provider_stats_5gib.json): same
     counts.

If both hold, the claim is: *by Modal's own accounting, A02's container stayed
below 4,096 MiB and A03's below 5,120 MiB.* The exact peak stays
`UNAVAILABLE`. gVisor process RSS (4.87–4.89 GiB) is reported as an in-sandbox
accounting figure, not container usage.

## Status, cost and controls

- **Post hoc.** This rule was written on 2026-10-23, after the 4 GiB and 5 GiB
  runs and their unresolved accounting were observed. It is not a
  pre-registered criterion.
- **Cost:** two new A10 invocations in one app, each a few seconds of
  allocation plus image start. Operational budget target USD 0.50. The probe
  touches no labels, model, checkpoint or workload data.
- **Workspace:** the controls run in the Research Lead's Modal workspace
  `buiphat251399`; A02/A03 ran in `tranthanhzt123321`. Hard-limit enforcement
  is a Modal platform behaviour, but the difference is disclosed for QA.
- **Fail-closed:** a 900 s whole-app watchdog and a create-once namespace.
  Results are never rerun to reach `ENFORCEMENT_DEMONSTRATED`.
- **Unchanged:** the m3.6-004 integrity, latency, CUDA and parity verdicts and
  all raw results. Khương's owner acceptance and Thanh's QA acceptance remain
  separate and required.

## Approval

Tấn Phát (Research Lead), in the working session on 2026-10-23T02:58:43Z,
recorded verbatim by Claude at their request:

> I approved as Tấn Phát, confirm for m3.6-005 and approved probe run plan.
> Finally, I confirm the m3.7 criteria (frozen threshold-seed20260820)

Khương's owner acceptance and Thanh's QA acceptance of the probe result remain
separate and required.
