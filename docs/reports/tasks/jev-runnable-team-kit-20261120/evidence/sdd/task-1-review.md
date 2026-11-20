# Task 1 review

## Spec compliance

- ❌ Issues found. Explicit partition selection can omit queries assigned to that partition. Byte-exact ViMDoc pairs can be evaluated at the wrong label unit without a diagnostic. CSV evaluation and both comparison formats drop the shortlist scope.
- ⚠️ The diff supports a read-only, label-free native F9 bridge. The actual private bundle contents and model execution remain unverified in this review. TDD sequencing, reported suite outcomes, bundle layout, and file hashes cannot be independently established from the diff alone.

## Strengths

- `src/qpaf/jev/contracts.py:79`, `:151`, and `:167` enforce a complete finite non-boolean score vector, check the pair snapshot digest, and atomically replace a cache only after validation. `src/qpaf/jev/cli.py:149` and `:159` preserve original score order during split projection and bind the result to the new bytes.
- `src/qpaf/jev/data.py:185` and `:203` select candidates with explicit scores and serialize page order with the corresponding baseline scores. `src/qpaf/jev/evaluation.py:55` and `:85` account for out-of-pool gold, max-pool mapped pages, and break ties by unit ID. `tests/test_jev_evaluation.py:25` and `:72` exercise the rankings and query/group resampling.
- `src/qpaf/jev/data.py:109` imports the optional Parquet dependency only on that path and projects retriever columns. `tests/test_jev_cli.py:21` runs the actual CPU entry point from another cwd with site packages disabled. The reviewed diff adds no imports or changes to the legacy modules associated with the reported full-suite failures.

## Issues

### Critical

None.

### Important

1. `src/qpaf/jev/data.py:234` and `:237` intersect the bundle with the requested split and only reject an empty intersection. With `q1` and `q2` both assigned to test and only `q1` present, preparation succeeds and evaluation gives a one-query mean even when the qrels contain both IDs (`src/qpaf/jev/evaluation.py:41` and `:85`). In native mode, `src/qpaf/jev/cli.py:129` applies the default held-out IDs from `src/qpaf/jev/data.py:23` and `:27` before applying a requested partition. Resolve the expected cohort from the partition and any explicit query-ID selection early enough to validate coverage and reject missing selected queries. Use an explicit selection or the correct source IDs for native development partitions.
2. `src/qpaf/jev/cli.py:237` and `src/qpaf/jev/evaluation.py:84` silently fall back to page IDs for legacy ViMDoc pairs. The original writer omits a unit map (`scripts/run_f9.py:84`), and the original ViMDoc evaluator uses document judgments (`scripts/lab_heldout.py:241`). With document qrels, the fallback can yield all-zero metrics on a perfect score vector. Require a complete page-to-document mapping for known ViMDoc evaluation, with an actionable diagnostic for supplying the existing `--units` sidecar. Byte-exact imports can still preserve the original pairs.
3. `src/qpaf/jev/cli.py:199` drops `ranking_scope` from evaluation CSV. `src/qpaf/jev/evaluation.py:178` drops the scope after accepting matching inputs, and `src/qpaf/jev/cli.py:206` omits it from comparison CSV. This leaves standalone reports that can be mistaken for full F9 evaluation, especially with the extra unique documents in the ViMDoc tail. Carry the shortlist scope through all result formats.

### Minor

1. `src/qpaf/jev/cli.py:111` and `:148` bypass the preparation input checker for explicitly provided score and split sidecars. A missing sidecar yields a filesystem exception with the path, without the next-command guidance the preparation brief requests.

## Assessment

**Task quality:** Needs fixes.

**Review evidence:** Reviewed the supplied diff from `e5060b4aa422690117b3552ca85524aea01c71da` to `516b7879c57d2cce899a1c8f415fe789ff8fe595` using Superpowers 7.0.1's `subagent-driven-development/task-reviewer-prompt.md`. Checked the original F9 pair writer, label-free loader and ViMDoc metric entry point for cohort defaults and label units. One in-memory Python probe with `-B -I -S` confirmed that a two-query requested test split can return just one query and that adding the correct ViMDoc unit map changed the same score vector from all-zero to all-one metrics. The test suite was not rerun.
