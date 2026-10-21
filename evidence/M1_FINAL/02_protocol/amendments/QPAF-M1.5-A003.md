# QPAF-M1.5-A003 — Top-document candidate expansion

> **Protocol:** `QPAF-M1.5-v1` (scoped successor `m1.5-002`)
> **Date:** 2026-10-21
> **Requester:** Tấn Phát (Research Lead)
> **Affected file:** `evidence/M1_FINAL/02_protocol/candidate_policy.md` §2
> **Effective policy ID:** `qpaf_m28_top_document_expansion_v1`
> **Status:** `APPROVED_RESEARCH_LEAD / INDEPENDENT_REVIEW_PENDING`
> **Registry classification:** `governance` / `governance_record`

This file is the create-once record for amendment A003. It is a separate file
because the two existing ledgers are hash-bound. `protocol_amendments.md`
(`6faa118a…`) is bound by `protocol_freeze_manifest.json`, and
`amendments_after_import.md` (`6a7a0f63…`) is bound by
`protocol_adoption_candidate.json` and `m1.5-002/source_hashes.csv`. Neither
ledger is edited. A003 follows A001 and A002 in the same ID sequence.

## 1. Identity before implementation

Recorded before any expansion code or run exists, on `origin/develop`
`7d4f9282ecc4593cc050a748e0055bf06f5fa255`.

| File | SHA-256 |
| --- | --- |
| `evidence/M1_FINAL/02_protocol/candidate_policy.md` | `4a85a2e17cd8adfcc5f301d5393e9e6762221383d3601e0407642bad915d0562` |
| `configs/m2.8/cache.json` | `049b00c2456146f6d39da3b184722b5f6f6e9f97b5c44a52ac86be92d97400c7` |
| `configs/m2.5/freeze.json` (`rrf_k = 60`) | `317b4333968ae4250e0e9bc71846d37f47e5f958872c8cf27949a0c0d8c3579c` |
| `evidence/revisions/m2.8-001/candidate_freeze.json` (baseline `C0`) | `4ff420008b9ccaa3a4d3afc565c43e2c974b3f95dd39a22a742b47297aead06e` |
| `docs/superpowers/reports/2026-10-21-m28-uncovered-query-followup.md` (proposal) | `04266cad2cddfb1d4e1569eb73b40d77302d7d93faeadbb2c05464545dd963d8` |

## 2. Old and new values

**Old (`candidate_policy.md` §2):** for each query, take the top 200 pages per
channel by raw score (descending, ties by ascending page ID), union by page ID,
and output in ascending page-ID order. At most 600 pages per query.

**New (`qpaf_m28_top_document_expansion_v1`):** for each query:

1. Build `C0` exactly as the old rule (top-200 per channel, union). `C0` is
   never reduced.
2. For each channel, rank **all** corpus pages by raw score (descending, ties by
   ascending page ID), rank 1 first.
3. `RRF(q, p) = Σ_c 1 / (60 + rank_c(q, p))` over the three channels. The sum is
   taken in channel order bm25, dense, visual in float64.
4. Each PDF scores the maximum `RRF` over its pages. Select exactly **one** PDF:
   the highest score, ties by ascending document ID. No second PDF is
   considered, even if the selected PDF is already fully inside `C0`.
5. Add that PDF's pages not in `C0`, in order of `RRF` descending (ties by
   ascending page ID), up to `600 − |C0|` pages.
6. Output the union in ascending page-ID order. Keep all three raw scores from
   the full matrices and recompute per-query min-max normalization on the new
   union (constant-range epsilon `1e-15`).

Each added page is logged with its PDF, priority and reason
`top_document_expansion`.

| Parameter | Value |
| --- | --- |
| Per-channel depth for `C0` | 200 |
| RRF constant | 60 (same as `configs/m2.5/freeze.json`) |
| Expansion documents per query | 1 |
| Per-query cap | 600 pages |
| Page → document mapping | Canonical M2.6 page ID `{document_stem}_page_{NNNN}` |

## 3. Inputs the rule may and may not read

**Allowed:** the three full M2.8 score matrices, the ordered page IDs and the
page → document mapping.

**Forbidden:** qrels, relevance, reference answers, `query_type`,
`source_type`, split membership, coverage results, and the **content of query
IDs**. ViDoSeek query IDs embed the stem of their source PDF (`<stem>_<n>`), so
reading them would leak the gold document. The rule treats a query only as a row
index.

## 4. Why the change is needed and why no-change is invalid

M2.8-001 (`BLOCKED_COVERAGE`) leaves train query
`04450a0f59f81025574451222aa26322ae7ede42_2` uncovered. Its positive page ranks
271/273/769 in BM25/dense/visual, outside every top-200 list, while all three
channels rank pages of the correct PDF first. The frozen gate requires zero
uncovered queries, and `candidate_policy.md` §4 forbids dropping the query or
injecting the positive. Keeping the policy leaves D1 `BLOCKED` permanently,
and with it M3 and G2.

Raising the per-channel depth does not work within the protocol: it changes
the cap semantics, because 3 × 200 already reaches 600. Waiving the gate
weakens a frozen acceptance criterion. A003 keeps the depth, the cap and the
gate. It only uses spare capacity under the existing cap.

## 5. Post-hoc status and controls

**This amendment is post hoc.** It was proposed on 2026-10-21 after a baseline
train failure had been observed. It is not a pre-registered hypothesis.
Controls:

- One fixed rule, defined above before implementation. No variants (other
  RRF k, more PDFs, other depths) will be tried or selected by coverage.
- The rule reads no labels (§3). It is identical for every query, split and
  method.
- Development first: coverage is reported for train/validation before test
  qrels are opened. Test qrels are used only to audit the coverage of the
  frozen candidate set. No test ranking metric is computed to choose a policy.
- §4 of the candidate policy says that failing coverage must not lead to a
  change of top-k after seeing labels. A003 does not change top-k. The policy
  itself was still motivated by a labelled failure, which is why it is
  recorded here as a post-hoc amendment with independent review, not as a
  silent correction.

## 6. Leakage, fairness, statistics and claim impact

- **Leakage:** none by construction. The rule is label-free and reads no query
  ID content. The builder has no label input. Qrels are opened only after the
  candidate freeze, as in M2.8.
- **Matched comparison:** QARF, QPAF and every M2.5 baseline must use the same
  expanded candidate set. Candidate keys and order are shared.
- **Statistics:** unchanged (paired 10,000-bootstrap CI, W/T/L, three seeds).
- **Ranking effect:** added pages can be distractors for every method. Higher
  coverage is not evidence of higher nDCG@10 or of a learned QPAF gain.
- **Claim boundary:** the expansion is a candidate-pool property. Results that
  use it must state the policy ID.

## 7. Affected runs

| Run / record | Effect |
| --- | --- |
| M2.8-001 (`RUN-QPAF-M2_8-CACHE-001-…`) | Preserved unchanged. Its score matrices are reused; no new GPU encoding is needed. |
| New candidate revision `m2.8-002` | Mandatory: new namespace, freeze, independent replay, coverage. |
| M2.7 matched manifest | A new revision must bind the accepted cache, candidate and qrels hashes. |
| M2.10 audit and M2.11 D1 | Must be repeated on `m2.8-002`. |
| M2.9 CARF not-run | Unaffected. |
| Learned runs | None exist; none invalidated. |

## 8. Approval

| Role | Name | State | Evidence |
| --- | --- | --- | --- |
| Research Lead | Tấn Phát | `APPROVED` | Working-session instruction, 2026-10-21: "please proceed for Option A until the M2 unblocked". Option A was presented as this exact rule, including the post-hoc and fairness caveats. |
| Independent reviewer | — | `PENDING` | Required by the amendment procedure step 6 before D1 can pass. |

An M1.7 `governance` / `governance_record` registry event for A003 is still to
be appended by the registry owner (Thanh). This record does not authorize any
learned training or evaluation.
