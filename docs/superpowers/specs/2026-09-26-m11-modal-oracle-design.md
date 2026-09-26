# M1.1 reproducible Oracle on Modal

The user requests a new implementation to finish M1.1 after a feasibility-only
Oracle experiment, using one of the project's three datasets. Execution is on
Modal.com. Dataset/model IDs, revisions, resources, paths and experimental
parameters must be configurable, not embedded in Python logic.

## Scope and decisions

Use the original ViDoSeek distribution for a new study, preserving the previous
Word report and its reported numbers. Default to all queries and the full PDF
corpus. An optional query subset is selected by a seeded hash of IDs before
reading relevance labels; it is never described as the historical Exploratory-24.
ViMDoc and ViDoRe V3 adapters, learned fusion, training and a RAG answering app are
outside M1.1. The interfaces should allow these later without copying Oracle code.

The pipeline has five restartable stages: prepare, BM25, dense, visual and Oracle.
Each stage writes to a new immutable directory beneath a Modal Volume. Reuse only
completed stages whose config and input hashes match. A failed stage retains its
logs and cannot be silently treated as a completed cache. Stage receipts include
all output hashes; input readers verify them. Separate stage attempts make retry
explicit rather than overwriting evidence.

## Inputs and data policy

The preset pins the official dataset revision and both model checkpoints (including
the visual adapter's base model). Native PDF text with configurable Tesseract
fallback supplies BM25/dense text; rendered page images supply ColQwen2. All PDF
pages remain in the corpus, including pages with empty extracted text. Extraction
errors fail with a log by default. Native text/OCR source and empty-page counts
are recorded. Page IDs preserve the source filename stem and **one-based** page
number. Duplicate IDs, missing documents, invalid page labels and duplicate query
IDs are errors. Reference answers and source/query-type labels never enter scorers.

The original JSON has an `examples` list. Its observed count is 1,142; that count
is evidence from revision inspection, not an assertion hardcoded in the adapter.

## Scoring and Oracle definition

Cache complete query-by-page scores independently for BM25, frozen BGE-M3 and
frozen ColQwen2. Persist query and page ordering with every cache. Build the union
of each channel's top-K without labels. All channels provide scores for every
member of the union; missing or nonfinite scores are errors. Normalize each
channel by min-max on that candidate pool, with constant columns mapped to zero.
Tie order is ascending page ID throughout. nDCG's IDCG uses **all** relevant pages,
including relevant pages absent from the candidate pool.

Weight sets are data in TOML: seven explicit W7 profiles and a denominator-10
simplex grid W66. Global chooses one profile maximizing mean nDCG across the study;
QARF chooses one per query. For binary labels, exact unconstrained QPAF chooses
the maximum feasible fused score for relevant pages and minimum for nonrelevant
pages. This is a label-using upper bound, not inference or a learned model. Reject
graded qrels for this solver. Prove its objective on a tiny exhaustive fixture.

Both provided weight sets include all simplex vertices, so this binary QPAF
optimum is identical for W7 and W66 when inputs are identical. The old report's
different QPAF values therefore cannot be claimed reproduced by this definition;
its algorithm/config are unavailable. Record this in the comparison report rather
than adjusting scores to match it. W66 need not dominate W7 for QARF: W66 lacks the
exact one-third profile. Oracle ordering is QPAF >= QARF per query and mean QARF >=
mean Global (Global is itself one allowed choice for every QARF query).

Compute mean per-query nDCG@10, candidate recall, paired query bootstrap percentile
CI95, and wins/ties/losses with configured resampling seed/count/tolerance. Single
query intervals are degenerate and explicitly reported. No tuning on ViDoRe V3.

## Modal and reproducibility

A normal Python launcher reads and validates TOML/CLI overrides **before** creating
the Modal App and functions. CPU stages do not reserve a GPU. Model stages reserve
the configured GPU. Dataset, embeddings, score cache and run evidence persist on
the configured Volume. HF credentials, if needed, arrive through named Modal
Secrets; neither config nor provenance contains token values. Local dry-run and
cached-score evaluation work without Modal credentials or GPU dependencies.

Every stage records UTC times, resolved config, invocation, source file hashes,
base Git commit/dirty state, Python/platform/package versions, input/output hashes,
and failure status. Fetching run evidence is separate from downloading large
payloads. A JSON status distinguishes pipeline execution from independent QA.

Research dependencies are pinned in a dedicated requirements file; the existing
stdlib audit tool remains installable on its own. The user authenticates with
Modal locally; this workspace currently has no Modal SDK or `.modal.toml`.

## Deliverables and acceptance

Deliver source modules, config preset, Modal launcher, local evaluator, installation
instructions, meaningful unit/integration tests, and actual local verification
logs. A successful real run additionally supplies query_ids.csv,
per_query_metrics.csv, summary.json, review.md, provenance.json, hashes.csv,
resolved_config.json, and run.log. Complete M1.1 requires the real Modal run and
another group member's review; local fixture results must not be presented as
ViDoSeek research evidence.

## Sources inspected

- https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek
- https://github.com/Alibaba-NLP/ViDoRAG/blob/main/scripts/pdf2images.py
- https://huggingface.co/vidore/colqwen2-v1.0
- https://modal.com/docs/guide/volumes
- https://modal.com/docs/reference/modal.App
