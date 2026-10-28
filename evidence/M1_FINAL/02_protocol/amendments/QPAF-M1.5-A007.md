# QPAF-M1.5-A007 — ViMDoc page identity v2: keep both `.jpg` and `.png` assets

> **Protocol:** `QPAF-M1.5-v1` (scoped successor `m1.5-002`)
> **Date:** 2026-10-28
> **Requester and approver:** Tấn Phát (Research Lead)
> **Affected contract:** `configs/vimdoc_ocr_page_identity_v1.json` (page identity), for ViMDoc under A005
> **New contract:** `configs/vimdoc_ocr_page_identity_v2.json`, SHA-256 `6f293415e6f789471ee09c8e73833d61c5eb10e7843fd03fe3b8f7a0b7b74d39`
> **Status:** `APPROVED_RESEARCH_LEAD`; independent review `WAIVED_BY_A006`
> **Registry classification:** `governance` / `governance_record`

## 1. Evidence

The C1 live audit is recorded in
[`evidence/revisions/a005-s1-c1`](../../../revisions/a005-s1-c1/README.md). It ran on
the frozen archive (`de569c8d…2c71`). Of the 70,080 page stems, 6,267 stems each have a
`.jpg` and a `.png` asset, and every pair has different bytes. v1 requires `BLOCK` and
forbids preferring an extension.

The C1 asset inventory (SHA-256 `fabee762…b1ad`) still lists all 76,347 assets with their
hashes. Grouped by stem, those assets give the expected 1,247 documents. The 6,267 pairs
sit in 132 documents.

## 2. Old and new values

**Old (v1):**
- Page ID: the filename without its extension.
- Same page ID with different content: `BLOCK`.

**New (v2):**
- Page ID: the asset filename **with** its extension. Every asset is its own page.
- Document ID and page number: from the stem, as in v1.
- Two assets that share a stem: both pages are kept in the same document, each lists the
  other as `stem_sibling_page_ids`, and no extension is preferred.
- Expected counts: 76,347 pages, 70,080 stems, 6,267 two-asset stems, 1,247 documents.

The OCR engine, options, text rules and document-level evaluation are unchanged.

## 3. Why

- **HEAVEN does the same.** HEAVEN (`retrieval/heaven/utils.py` at `3eea5ca`) maps pages to
  documents by the final `_` segment and does not deduplicate pages; `check_dict` only
  warns. ViMDoc's reference evaluation therefore treats each file as a page.
- **Evaluation stays correct.** It is document-level with the max fused page score, and both
  assets of a stem always belong to the same document. Keeping both cannot move relevance
  between documents.
- **Rejected: prefer `.png`.** It contradicts v1's no-preference rule and HEAVEN.
- **Rejected: pixel-compare then collapse.** It needs an extra decode run, and any pair that
  still differs would block again.

## 4. Impact

- **Compute.** OCR and image encoding cover 76,347 instead of 70,080 pages, about 9% more.
- **Candidates.** Two near-identical pages of one document can both enter a candidate
  union. HEAVEN has the same effect, and it is reported, not filtered.
- **Labels.** None are used. The derivation reads only the hash-pinned C1 inventory.
- **ViDoSeek** results and records are unaffected.

## 5. Derived pages

[`scripts/derive_vimdoc_identity_v2.py`](../../../../scripts/derive_vimdoc_identity_v2.py)
(SHA-256 `3c95ed86…f724`, tests in `tests/test_vimdoc_identity_v2.py`) produced
`canonical_pages.jsonl`:

| | |
| --- | --- |
| Rows | 76,347 |
| Bytes | 24,023,205 |
| SHA-256 | `9dc277153f9137c8c668d70a3f66dfd208e129e5907eede7b47dbac1f2250b84` |
| Location | Modal volume `qpaf-artifacts` at `audits/vimdoc/vimdoc_identity_v2/canonical_pages.jsonl`; round-trip hash checked |

## 6. Approval

The Research Lead chose **"Giữ cả hai (Recommended)"** in Claude's structured question in
the working session (recorded by Claude at 2026-10-28T15:18:40Z). The options offered were
"Giữ cả hai", "So pixel rồi gộp" and "Ưu tiên .png", each with the trade-offs above.
