# First QPAF oracle comparison: prepared execution review

Execution update (2026-09-07): the user approved this prepared scope and Codex launched the one permitted CPU attempt. See [the run status and logs](QPAF_EXPLORATORY12_RUN_STATUS.md). The review below is the pre-execution snapshot; its pending/closed statements describe that historical stage.

Prepared 2026-09-07. **Implementation and read-only verification complete; protocol adoption and live execution pending. No retrieval improvement result exists yet.**

The next result-bearing milestone is the oracle headroom study: compare Global, query-adaptive QARF, and page-adaptive QPAF using real ViDoSeek relevance labels. This is Phase 1 in `Tasks.md`; the stakeholder tracker calls its corresponding section Phase 2. The earlier completed calibration measured CPU runtime with synthetic relevance only.

The existing 12-query proposal is now supported by a separate, closed runner. Preparing this review does not adopt the proposal, change the original task graph, or authorize a live run.

## Prepared files and verified evidence

- [Separate runner](../../../src/oracle_study/vidoseek_exploratory12.py): uses the existing two-pass W7 checkpoint engine and unchanged QARF/QPAF search primitives.
- [Closed execution configuration](../../../configs/vidoseek_w7_exploratory12_v1.json): pins all oracle-package Python source files, both parent protocols, the original proposal, Git base, Python/package versions, query count, resource limits, and output path. Both approval flags are false; actor, approver, text, and date are unset.
- [Pilot tests](../../../tests/test_vidoseek_exploratory12.py): exact comparison against the monolithic oracle on a synthetic subset, complete-query requirements, source/protocol drift, draft/actor refusal, no retry, and incomplete-output handling.
- [Original proposal](vidoseek_w7_exploratory12_proposal.json): preserved unchanged as the historical design snapshot. Its old `not_implemented` field describes the proposal's creation, not current implementation readiness.
- [Full test output](../../../runs/exploratory12_preparation_20260907/pytest.txt): `169 passed in 22.82s` before final formatting. [Final focused tests](../../../runs/exploratory12_preparation_20260907/final_focused_tests.txt): `46 passed in 8.70s` after formatting and source-pin refresh. Ruff lint/format checks also pass. [Final read-only preflight](../../../runs/exploratory12_preparation_20260907/final_preflight.json): PASS.

Read-only preflight reverified the pinned 6,149,670-row score bundle, 1,142-query candidate audit, 5,385 pages per query, coverage 1.0, existing engineering evidence, and the frozen sample IDs. It read query-ID columns for selection verification and did not load relevance values or execute the oracle. Semantic integrity continues to inherit the previously verified, hash-pinned integrity review. The calibration marker/manifest byte hashes and their cross-link also match the saved review.

Base Git commit: `99823b96c9afd52e11e7ddb001f5b74bf0a1e314`. Existing user changes remain present. The prepared runner and config are uncommitted. Execution requires this exact base and the source-byte hashes in the config. It saves all pinned source bytes, the resolved config, and the tracked diff for reproducibility; the Git commit alone does not describe this prepared implementation. Any source or environment change requires new review and updated pins before execution.

## Proposed run and its meaning

| Item | Fixed scope |
| --- | --- |
| Dataset | Existing ViDoSeek P1-02R normalized scores; no extraction |
| Query selection | Original 12 IDs; seed 20260820; audit indices 147, 396, 510, 682, 792, 797, 848, 880, 881, 940, 1023, 1081 |
| Candidate pool | All 5,385 pages for each selected query; 64,620 pairs |
| Global profile | One W7 profile selected across these 12 queries before any QPAF query search |
| QARF / QPAF | Existing query-local search / existing two-sweep coordinate ascent |
| Statistics | All per-query metrics; mean gains; 10,000-resample query-bootstrap 95% intervals; win/tie/loss; per-query computation and checkpoint timings |
| Resources | One local CPU worker; four numerical-library thread limits set to one; no GPU |
| Time limit | 21,600 seconds from entering the run function; includes source checks, snapshot creation, child startup, input preflight, oracle work, and result finalization; interpreter imports occur before that timer |
| Attempts | One; zero automatic retries; any existing output directory blocks another attempt |
| Proposed actor | Codex, only if explicitly approved; a human invocation is also supported with matching authorization |

The measured synthetic calibration was 752.7996488000001 seconds for one query. Multiplying by 12 gives approximately 2.51 hours, **a projection, not a runtime guarantee**. Real relevance can change the search work. The six-hour cap is a proposed budget, not a promise of completion; process termination may require a short cleanup interval after timeout.

This pilot answers whether page-specific oracle weighting shows headroom on the fixed exploratory sample. It cannot establish learned/deployable performance, represent the full 1,142-query W7 result, or pass/fail the formal discovery phase. All summaries replace the inherited full-discovery gate with `NOT_APPLICABLE_EXPLORATORY_SUBSET`. A weak subset does not terminate the research direction. ViDoRe labels remain outside this run.

## Exact commands

Read-only check, runnable now in Command Prompt from the repository root:

```bat
set "PYTHONPATH=src"
C:\Python313\python.exe -m oracle_study.vidoseek_exploratory12 preflight
```

Proposed live invocation **after approval is recorded**, from `C:\Users\HP\OneDrive\tlcn`:

```bat
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=src"
C:\Python313\python.exe -m oracle_study.vidoseek_exploratory12 run --actor codex
```

The live command currently refuses before input validation, label loading, attempt consumption, or output creation. Approval must explicitly adopt this subset protocol and authorize the actor to make one bounded invocation. Record the actual user text and timestamp, and open only the two fields in this pilot's authorization block. Preserve its reviewed scientific scope and source pins. Do not enable the historical full-W7 or calibration flags. For a human-approved invocation, both the recorded actor and command must use `human`.

Suggested decision text:

> Adopt the prepared 12-query ViDoSeek exploratory protocol and authorize Codex to execute it once locally on CPU, with one worker/thread, a six-hour cap, and no retry. Record the actual approval in the separate pilot config and review all outputs afterward. Keep full W7, W66, training, Modal/GPU, and the frozen P1-02 status unchanged.

This is proposed approval wording, not evidence of approval.

## Output and stop conditions

Output root: `runs/vidoseek_w7_exploratory12_v1/`. This directory does not exist at preparation completion.

The runner exclusively creates the directory and an immutable `_ATTEMPTED.json` before preflight or label access. It captures `resolved_config.json`, `source_snapshot/`, and `tracked_changes.patch`. The existing checkpoint engine binds its plan, Global reduction, shared Global selection, and each query result to exact identities and content hashes. Checkpoints are retained for audit; this pilot exposes no resume command.

A completed run must have `per_query.json`, `summary.json`, `timings.json`, `preflight.json`, and a final `run_manifest.json` with `status=COMPLETE`. The manifest records artifact hashes, environment, actor, source/config identity, and non-training boundaries. All 12 selected queries must be present. Review every artifact hash and query ID before reporting metrics.

Failure, interruption, timeout, missing queries, or output errors preserve evidence and write `_INCOMPLETE.json` where possible. No complete manifest is issued. A hard process or machine termination may leave only the attempt marker and partial files; absence of the complete manifest still means incomplete. Do not delete the directory, retry, substitute queries, or report a partial mean as the complete experiment.

## Remaining decision

`Tasks.md`, P1-02R-O1, states: "Every later execution step requires a separate explicit human-approved amendment." The saved calibration review also requires a decision because the 12-query sample changes both discovery membership and Global-selection scope. This is the reason live execution remains pending after the preparation work.

Frozen P1-02 remains BLOCKED. Full W7, W66/P1-03, and training remain closed. The original September 5 formal phase deadline has elapsed; any future formal phase decision also requires the schedule amendment specified in `Tasks.md`. The exploratory pilot does not silently extend that schedule or claim a formal phase decision.
