# M4.2 — Baseline inputs and train-only settings

Owner: Khương. Request: research primary internet sources, implement the work
following PR #33, verify it, and report before proceeding further.
Base: develop `5bbb2de`, which merged PR #33. No human acceptance is asserted.

## Authority and scope

The workbook's Milestones row 49 assigns M4.2 to Khương. The M4.1 seal fixes
ViMDoc revision, 1,600 train / 400 validation / 8,904 confirmation IDs, document
evaluation, and confirmation access remaining closed. The M1.5 baseline and
candidate policies define seven deployable rows, shared candidates, min-max,
RRF k=60, and train-only fitting. M2.5 supplies the existing 66-point simplex
grid and deterministic tie rule; its page evaluator cannot be used for ViMDoc.

Implement a separate, standard-library document baseline reference and a
replayable freeze package. No historical evidence/configuration is rewritten.
No remote extraction, learned training, validation selection, or confirmation
evaluation is part of this preparation invocation.

## Approaches and decision

1. Reuse the M2.5 evaluator unchanged: rejected because its unit is page.
2. Replace M2.5 globally: rejected because it changes historical ViDoSeek runs.
3. Preserve its roster/grid and implement the M4.1 document contract separately:
   selected as an implementation decision grounded in the existing protocols.

The 66-point grid is explicitly inherited engineering policy, not a parameter
claimed to be established by the RRF paper. Its ViMDoc adoption and real fitted
weights remain unaccepted until an authorized, reviewed real-input run.

## Required behavior

- Exactly BM25, BGE-M3, ColQwen2.5, uniform CombSUM, RRF k60,
  train-fitted static, and learned QARF. Learned QARF is a required downstream
  checkpoint input; it is not fabricated by this package.
- All score-only rows have query_id, page_id, bm25_score, dense_score,
  visual_score, finite numbers, unique sorted page IDs and at most 600 rows/query.
- Min-max per query/channel on the common union; range <=1e-15 becomes zero.
  No population scaler or label-dependent normalization is fitted.
- RRF ranks all rescored union pages per raw channel, score descending and
  page ID ascending; ranks start at 1; k=60 is fixed, not fitted.
- Fuse pages first; remove the last underscore segment for document ID;
  aggregate with max, tie by document ID. Binary nDCG@10 uses ALL relevant
  documents for IDCG, including positives missing from candidates.
- Static fit requires EXACT train query IDs and exact matching separate
  document qrels; reject extra/missing/duplicate IDs and label-bearing score
  columns. Grid step 0.1, 66 points, train mean document nDCG@10, lexicographic
  tie within 1e-12 relative to the global best.
- Freeze verifier checks M4.1 split bytes, policies and confirmed G2; binds
  source/config/test/research files by SHA-256; refuses overwrite or drift.
- Technical fixture PASS never implies real inputs ready, fitted weights,
  baseline selection, accepted M4.2, or permission to open confirmation.

## Known input gaps

`artifacts/score_input_probe_vimdoc.json` is historical, not a new live probe.
It records score_extraction_started=false and no score files. M4.1 expressly
requires verified candidates/cache, document qrels and ViMDoc checkpoints.
This package must record missing real input hashes as null and readiness as
BLOCKED, rather than substitute ViDoSeek or manufacture baseline metrics.

## Verification

Hand-computed scoring/document/IDCG fixtures, exact train-only rejection tests,
66-point deterministic fitting, real M4.1 ID/hash replay, corrupted artifact
rejection, read-only verification and create-once CLI checks. Run focused tests
and the repository suite; report baseline/environment failures separately.
Research decisions and source URLs are recorded in the revision README.
