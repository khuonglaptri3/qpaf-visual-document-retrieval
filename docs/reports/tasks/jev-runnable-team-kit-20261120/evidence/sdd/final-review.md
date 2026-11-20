# Whole-branch review, 2026-11-20

Reviewer: `jev_team_kit_final_review`, isolated gpt-6.2-astra/high. Range `842176c..705d9ca`. Applied Superpowers 7.0.1 requesting-code-review and SDD final-review instructions. Read-only review; temporary probes did not change checkout files/index/refs.

**Ready for owner-branch integration: With fixes.** No Critical findings.

## Important findings (verbatim substance)

1. `src/qpaf/jev/data.py:249` and `:258` allow a prepared bundle's partition to be overwritten during reimport. Reviewer prepared a test bundle, supplied a conflicting split file, reimported it as train, and successfully exported its labeled page to training JSONL; all three commands exited 0. Reject a requested partition conflicting with the source bundle's explicit partition before publishing any output. Retain same-partition subsetting and legacy bundles without a partition.
2. `src/qpaf/jev/cli.py:335` writes the shared demo into an existing directory. `demo --out DIR` exited 0 and replaced a pre-existing qrels.json sentinel; the same code writes pairs, scores and reports. Reserve a new directory as owner demos do, or stage and publish exclusively. Verify an existing sentinel survives.
3. `src/qpaf/jev/cli.py:187` publishes preparation outputs individually into a reusable directory. Reviewer imported a score cache then prepared the same pairs there without --import-scores. New manifest omitted the cache, but old scores.json remained and passed doctor. Publish a coherent directory per run: reject an occupied destination before writing, or stage and replace the complete artifact set with defined retries.
4. `src/qpaf/jev/owners.py:70` forwards arbitrary training_args from Khương's editable config into train. Adding --execute turns the offline demo into a real trainer invocation in a configured environment; later --data/--out arguments can override fixture paths. Use typed permitted demo settings; construct CPU dry-run arguments/fixture paths in the wrapper. Test edited config without invoking a trainer.
5. `src/qpaf/jev/cli.py:174` hashes raw preparation inputs after consuming them. A controlled replacement probe selected page a while recording the hash of a file whose winner was b. Comparison inputs have the same read-then-reopen issue at :310, identified by source inspection rather than a second original mutation probe. Hash the consumed bytes. For streaming/Parquet inputs, use stable snapshots or detect changes across reads and fail before publication.
6. `evidence/finalize_artifacts.py:98` accepts absent/incomplete common hash manifests. Substituting a missing manifest or {"files":[]} yielded passed:true and exit0; current manifest had all91 expected entries. Require a manifest in verification mode; compare exact unique path set with delivered_files() before bytes/digests. Cover missing, empty and omitted-entry cases before relying on the clean-clone gate.

## Minor

- Retain documented ten-effective-step upstream scheduler limit and matched-budget workaround (common README.md:174); supplied CPU smoke used one step.
- Expected negative-path diagnostics remain in passing logs; capture cleanup would improve signal (task-3-green.log:9).

## Strengths

Exact pair-byte/finite/length score validation; runtime/checkpoint/input-bound chunk resumes; document pooling and outside-pool positives; clear separation of 64-test/PyArrow/tiny-CPU evidence from full-size quality and cloud execution.

## Declined to judge

- Full-size BGE/Qwen/Kev, real warm-start optimization, GPU memory and hosted Modal need weights/compute outside this review; supplied CPU/preview evidence is narrower.
- Private-data retrieval quality and exact historical full-ranking replay need their data/protocol; synthetic shortlist results cannot establish them.
- Historical 635-test suite has named disclosed failures; not rerun or attributed to this branch.
- Pinned upstream snapshots are dependency evidence; editing Kev itself is outside authored scope.
- Final merges/clones/remote refs/main preservation are controller-owned checks after the gate.
