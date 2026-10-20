# M2.8 - Verified real GPU cache, coverage blocked

**GPU COMPLETE / CACHE VERIFIED / BLOCKED_COVERAGE**.

Real A10 run: 1,142 queries, 5,385 pages, 18,449,010 scalar scores,
549,689 frozen candidates. Macro candidate recall is 0.999124343257443,
but one train query is uncovered; the zero-uncovered milestone gate fails.
Validation and test candidate coverage are both 1.0. No learned training was run.

- [Measured report](report_snapshot.md), [handover](handover.json), [coverage](coverage_report.json).
- [Train failure diagnosis](uncovered_diagnosis.json), [fresh independent review](artifact_review.json).
- [Read-only verification](closure_verification.json), [cloud readback](cloud_closure_verification.json).
- [GPU summary](summary.json), [environment](environment.json), [resources](resources.json).
- [Source identity](source.json), [exact archive audit](source_snapshot_verification.json).
- [Candidate freeze](candidate_freeze.json), [byte manifest of original bundle](bundle_hashes.json).
- [Software checks](software_checks.json), [code review](code_review.json), [HTML deletion inventory](ocr_review_html_removal.json).
- [Revision byte manifest](hashes.json), [complete saved-file index](../../../results/m2.8/README.md).

Run: `RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01`.
Remote Volume: `qpaf-m28-score-cache`, `/runs/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/`.

This revision is create-once. Handover relative data paths refer to the original
run's `bundle/`, not this metadata snapshot. Full arrays, Parquet and embeddings
remain local and on Modal; the original source ZIP remains in the run and cloud.
This code/artifact review is not named human M2.10/D1 signoff. Any policy change
requires a documented amendment and a new run/revision; keep this failure intact.
