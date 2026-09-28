# M1.5 NEW-repository adoption readiness — 28/09/2026

**Owner:** Tấn Phát, Research Lead / Protocol Owner
**Status:** `PREPARED_BLOCKED_NOT_ADOPTED`
**Source snapshot:** `origin/develop` at `2e74b97e1836213f07510a4075c3b53389bd04c5`
**Independent review:** `PENDING`
**Result-bearing execution:** `CLOSED`

## Reconciled identities

- The nine historical `QPAF-M1.5-v1` Markdown files again match
  [the OLD freeze manifest](protocol_freeze_manifest.json) byte-for-byte. Its
  package digest remains `692e98b790939f25f95e2c04ab9f3c661561b18cae5548870d49491d4fdf6c16`.
- The A001/A002 entries approved on 28/09 are preserved in
  [the post-import amendment ledger](amendments_after_import.md), copied from
  commit `0924c27` (SHA-256
  `6a7a0f6328e467c698771115affa58cac32b95ea889da1a91691661e4049dc49`).
  They were previously written over the hash-addressed historical ledger. The
  historical ledger is restored from import commit `c82dd5a`; no amendment
  evidence is discarded.
- [The NEW-relative candidate manifest](protocol_adoption_candidate.json) binds
  the exact repository files that support the A001 pairwise-loss and A002
  ViDoSeek/split decisions. These are software and configuration references,
  **not** a learned run or an adopted training contract.

## Decisions and remaining evidence

| Area | Recorded decision or evidence | Remaining gate |
| --- | --- | --- |
| A001 loss | Research Lead approved pairwise logistic loss; `configs/m1.2/core.toml` and `src/qpaf/m12/losses.py` are hash-bound references | Choose and review the actual learned-training config/version; Thanh independently reviews the successor package |
| A002 dataset role | Research Lead approved ViDoSeek as active primary and kept ViMDoc for future confirmation; the dataset revision is pinned in `configs/m1.1/vidoseek.toml` | Khương supplies actual source, annotation and qrel hashes, plus exact train/val/test ID manifests, counts, hashes and overlap/coverage review |
| M1.6 | `m1.6-001` has populated output and a generated report | Khương supplies a new revision with matching payload hashes, resolvable source PDFs and a reviewed full-corpus scope |
| M1.8 | `m1.8-001` payload hashes verify; numerical thresholds remain provisional | Tấn Phát and Khương record whether provisional policy suffices for First Review or calibration must precede it |
| M1.7 | Thanh's post-merge Draft audit and issue log exist | Thanh binds the exact successor, independently reviews the selected package and issues Final only when dependencies close |

The OLD ViMDoc model, candidate depth, split sizes and seeds do not silently
become ViDoSeek training settings. The M1.1 Oracle configuration and M1.2
synthetic method-core verification also do not constitute learned evaluation.
The candidate manifest leaves missing identities `null` rather than inventing
values. It cannot be called a freeze or used for an invocation.

Thanh's append-only Draft registry, trace and issue rows still cite
`protocol_amendments.md` as it appeared in commit `0924c27`. Those historical
rows must remain unchanged. Before M1.7 Final, Thanh must append a correction
that points to `amendments_after_import.md` and the selected successor hash;
the current candidate is not a substitute for that independent action.

## Completion sequence

1. Khương provides the exact data/split artifacts and a reviewable M1.4/M1.6
   revision. Tấn Phát resolves the remaining model, candidate, seed and M1.8
   scope decisions in a versioned successor rather than editing the OLD freeze.
2. Bind the exact paths and SHA-256 values into a NEW-repository manifest on one
   selected tracked commit; resolve any amendment procedural gaps.
3. Thanh independently checks that byte-identical package, records the M1.7
   binding and signs only the review actually performed.
4. Refresh Pre-G1 from the reviewed evidence. Whole-team G1 First Review and
   any execution authorization remain separate later decisions.
