# M2.8 — A003 expanded candidate cache, coverage gate passed

**COVERAGE PASS / CANDIDATES FROZEN AND REPLAYED / INDEPENDENT REVIEW PENDING**.

Run `RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01` applies amendment
[`QPAF-M1.5-A003`](../../M1_FINAL/02_protocol/amendments/QPAF-M1.5-A003.md)
(`qpaf_m28_top_document_expansion_v1`) to the unchanged M2.8-001 score
matrices. It does no GPU work, no re-encoding and no training.
[M2.8-001](../m2.8-001/README.md) and its `BLOCKED_COVERAGE` result are
preserved.

| Measure | M2.8-001 baseline | M2.8-002 (A003) |
| --- | ---: | ---: |
| Candidate rows | 549,689 | 551,764 |
| Pages added | — | 2,075 over 530 queries |
| Candidates per query (min / mean / max) | — | 388 / 483.2 / 579 |
| Macro candidate recall | 0.999124343257443 | 1.0 |
| Uncovered queries (train / validation / test) | 1 / 0 / 0 | 0 / 0 / 0 |

The rebuilt baseline `C0` matched the M2.8-001 freeze on counts, query/page
IDs, all three score-array hashes and the candidate-key hash
([baseline replay](baseline_replay.json)). The previously uncovered train query
`04450a0f59f81025574451222aa26322ae7ede42_2` selected its own PDF without labels.
Its union grew from 448 to 455 pages, and the positive page 7 was added first
by RRF (see the [expansion log](candidate_expansion_log.csv)).

Order of label access:

1. The three source matrices were verified against the Git-tracked M2.8-001
   portable manifest.
2. Candidates were frozen and replayed from the full arrays.
3. Development qrels were opened, and train/validation coverage passed
   ([development report](development_report.json)).
4. Test qrels were then opened, for coverage of the frozen set only.

No test ranking metric was computed. The M2.4 loader built 799 train and 171
validation records from the new cache, and the M2.5 row audit passed
([handover](handover.json)).

- [Freeze manifest](candidate_freeze.json), [replay](candidate_verification.json),
  [coverage](coverage_report.json), [development coverage](development_coverage.json).
- [Label-free summary](expansion_summary.json), [config](resolved_config.json),
  [source identity](source.json), [bundle byte manifest](bundle_hashes.json).
- [Method note](../../../docs/03_method/m2.8-candidate-expansion.md).

Reproduce: download the three `scores.npy` files of M2.8-001 into its `remote/`
folders. Their hashes are fixed by `portable_manifest.json`. Then run
`python scripts/run_m28_expansion.py --verify <run folder>`, which is
read-only. The six Parquet files stay in the local run folder and are excluded
from Git; `bundle_hashes.json` binds them.

This revision is create-once. A003 was approved by the Research Lead and is
post hoc. The independent amendment review and the named D1 review are both
still `PENDING`. This record makes no retrieval-quality or learned-QPAF claim.
