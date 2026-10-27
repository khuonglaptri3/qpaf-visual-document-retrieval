# Engineering review — 2026-10-27

Fresh-context read-only reviewer: `/root/m55_gpu_review`, model `gpt-6-astra`, high.
Skill: Superpowers 7.0.1 `requesting-code-review` (SKILL.md and code-reviewer.md read).
Range: starting PR commit `1bdb491ec3b74f578c31dda5ba796d1d375ac586` to the
continuation working tree, including new GPU scripts/tests and canonical planning.
This is AI engineering review, not independent human acceptance.

No Critical findings. Reviewer reproduced nine passing GPU contract tests,
checked both frozen checkpoint/reference hashes and 171-ID/82,255-candidate
finite reference coverage, and confirmed one remote call and separate method
processes. The review itself made no remote calls or repository changes.

## Findings and disposition

1. Important: summary accepted candidate_count=0 or CUDA duration=999999ms with
   gate wall=.1ms. New test failed first; fix requires integer candidate counts
   1..600 consistent across passes and CUDA duration <= gate wall +.001ms clock
   tolerance. Recorded in gpu-review-regression-red/green.txt.
2. Important: authorization accepted missing/conflicting runtime/base image,
   startup timeout and worker timeout declarations. New drift cases failed first;
   fix requires the exact values in the spec. Recorded in gpu-runtime-auth-red/green.txt.
3. Reviewer Minor, regraded Important for spec coverage: missing event p50/p95
   over all 1,026 observations. The spec promises these descriptive statistics;
   added hand-derived 3.5/6.0 expectations, observed RED, then added the output.
4. Minor deferred: worker reference loop relies on preparation/hash binding rather
   than independently rejecting every malformed reference field/NaN/duplicate ID.
   Exact current reference files were independently checked finite, uniquely
   covered and hash-matched before execution. No historical source change is needed.
   A future hardening change can add worker-level validation; it is not claimed here.

No re-review is inferred. Parent verifies the material fixes using their observed
RED-to-GREEN tests and the full suite, as required by executing-plans.

## Behaviors reviewer declined to judge and parent rulings

- Actual Modal hardware, timings, billing and termination: require actual run,
  provider/runtime receipts and offline recomputation; review alone proves none.
- Human acceptance/counting approval: the owner delegated validation protocol
  details; disclose 171 distinct IDs/1,026 events. Human acceptance remains pending.
- Final artifact/index consistency: parent will verify layout, local links,
  manifests and historical hashes after results/report finalization.
