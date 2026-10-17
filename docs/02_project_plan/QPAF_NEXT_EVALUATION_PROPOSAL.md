# Next evaluation after exploratory-12

**HISTORICAL DECISION PLAN; STEPS A AND B ARE COMPLETE.** Prepared 2026-09-07 from the completed exploratory-12 comparison and [query 797 case study](../05_oracle_experiments/exploratory12/QPAF_QUERY797_CASE_STUDY.md). The separately approved fixed-profile audit and exploratory-24 W7 study have since completed; no W66 or training execution is authorized.

Completion follow-up (2026-09-08): the separately approved step A audit completed and passed independent verification. The mean theoretical QPAF-over-QARF headroom is 0.091732, above the 0.03 review threshold; 216 of 1,142 queries retain positive headroom. Step B then completed on the frozen additional 24-query sample: measured QPAF-minus-QARF is 0.050011 with CI95 [0.008344, 0.101921] and top-5% gain share 0.666315. See [the fixed-profile result](../05_oracle_experiments/fixed_profile/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md) and [the exploratory-24 result](../05_oracle_experiments/exploratory24/QPAF_EXPLORATORY24_RESULTS.md).

## Recommended next decision

First measure how much nDCG@10 headroom remains after query-level fusion over the complete discovery set using a bounded, fixed-profile audit. Decide whether another expensive page-level search is worthwhile only after reviewing that audit. The 12-query result alone is too concentrated to justify training, and another small sample could again be dominated by ceiling queries.

This proposal is motivated by an observed result and is therefore post-hoc. It does not revise the frozen protocol or retroactively satisfy it. The current P1-02 and P1-03 dependencies remain BLOCKED, and the September 5 schedule needs an explicit update before a new formal decision protocol can operate.

## Proposed step A: fixed-profile discovery headroom audit

| Item | Proposed contract |
| --- | --- |
| Population | All 1,142 frozen ViDoSeek discovery queries, all 5,385 pages/query; 6,149,670 query-page pairs |
| Inputs | Existing hash-pinned P1-02R score bundle and discovery audit; no new extraction or normalization |
| Computation | Evaluate the seven existing W7 fixed profiles per query; select one shared Global profile over all discovery queries and one QARF oracle profile per query |
| Excluded computation | QPAF coordinate search, W66, feature training, retriever execution, Modal/GPU, ViDoRe label access |
| Proposed resources | One local CPU worker, one thread per library, 1,800-second hard cap, one invocation, zero automatic retries |
| Runtime evidence | Not measured for this audit. The cap is a proposed limit, not a completion estimate |
| Outputs | Per-query profile metrics, channel baselines, shared Global/QARF summaries, ceiling fractions, headroom bound, timing, input/source/config hashes, completion manifest |
| Failure | Preserve partial evidence and stop on timeout, hash/coverage/schema/tie-break mismatch, or metric inconsistency; no partial aggregate conclusion |

Process one query at a time. The preparation follow-up freezes the exact command, source/config hashes, new output directory, resource guards and output schema, and tests fixed-profile selection and preservation with fixtures. The new executable configuration remains closed pending explicit execution approval.

For query `q`, the maximum possible improvement over QARF is at most `1 - nDCG@10(QARF,q)`. Its discovery mean is an upper bound on any QPAF mean gain, even with perfect page-level ranking. This mathematical bound requires no QPAF search. It is a decision aid, not a measured QPAF result.

- If the mean bound is below 0.03, the existing material-gain threshold is unattainable on those inputs. Recommend reviewing or stopping the current direction before page-level compute; do not write a formal P1-03 decision from this audit.
- If the bound is at least 0.03, QPAF might still fail to attain it. Review the ceiling fraction, query distribution and resource plan before deciding on page-level evaluation.
- Any discovery-wide Global result belongs to this new scope. Do not mix it with the 12-query Global selected on the smaller scope.

## Proposed step B: prepared after the audit warranted further exploration

The bounded feasibility option completed as **24 additional queries**, sampled uniformly without replacement from the frozen 1,130-query remainder using `random.Random(20260820)`. The exact selection algorithm, IDs and query-list hash were frozen in `docs/05_oracle_experiments/exploratory24/vidoseek_w7_exploratory24_proposal.json` before any new page-level oracle outcome. The completed run and independent review are reported in `docs/05_oracle_experiments/exploratory24/QPAF_EXPLORATORY24_RESULTS.md`.

Preserve all pages, W7 profiles, normalization, metric definitions, tie-breaks and two-sweep search. Select Global over these same 24 queries and label that scope explicitly. Report the original 12 and new 24 separately; do not pool incompatible Global selections. Use the existing 10,000-resample query bootstrap, report every query, ceiling fractions, wins/ties/losses, and gain concentration. This remains exploratory and cannot pass Phase 1.

The run used one CPU worker/thread, one invocation, zero automatic retries, a separate output directory and durable checkpoints. It completed in 8,700.394 seconds under the 43,200-second ceiling. This measured subset runtime does not guarantee linear full-corpus or W66 cost.

Do not select only queries where the baselines failed and then claim discovery-wide improvement. A failure-focused set can be a separately declared diagnostic, with its own interpretation, but cannot replace a representative comparison. Do not alter the sample after observing outcomes.

## Decisions to bring to the lecturer

1. Accept the pilot as evidence of one explainable page-specific opportunity, with no claim of trained-model success.
2. Approve, revise, or reject the bounded fixed-profile audit scope and budget before implementation/execution review.
3. Decide whether the eventual objective is full-discovery confirmation or a resource-limited exploratory study. Approve a new schedule and explicit protocol/dependency amendment if a formal phase decision is intended.
4. Require a reviewed W7/W66 decision and label-free generalization evidence before learned-QPAF claims. Keep ViDoRe sealed for the planned external-validation role.

Suggested explanation: “Our 12-query pilot had eleven ceiling cases. The remaining query improved because two page-specific score choices moved the relevant page to first place. Before training, we should cheaply quantify how much headroom remains across discovery, then decide whether more page-level oracle computation is justified.”

## Current completed work

The recovery and independent result review are complete; its chart has been visually checked. The new case study reconstructs existing rankings and explains the sole gain. No prior report, score bundle, checkpoint, approval snapshot, scientific threshold or experiment result has been replaced.
