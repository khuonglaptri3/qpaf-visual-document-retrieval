# M1.6 — Primary-Corpus Collision Audit

**Audit Status:** `PASS_AUDIT`
**Owner:** Khương (Data & Technical Owner)
**Evaluator/Auditor:** QPAF Collision Audit Engine v1.0
**Timestamp (UTC):** `2026-09-28T09:05:26.816683+00:00`
**Target Dataset:** `Qiuchen-Wang/ViDoSeek` @ `e91a92ba5f38690696c7e66be5c5474b54c6e791`

---

## 1. Audit Scope & Inventory Summary

| Metric | Measured Value | Requirement / Target | Audit Evaluation |
| :--- | :--- | :--- | :--- |
| **Total Documents** | 5 | Multi-document corpus | Complete |
| **Total Pages Cataloged** | 20 | All constituent PDF pages | 100% indexed |
| **Unique Content SHA-256** | 19 | Content-based deduplication | Recorded |
| **Duplicate Content Groups** | 1 | Explicit duplicate tracking | Documented |
| **Cross-Split Leakage** | 0 | **0 (Zero Tolerance)** | **Zero cross-split leakage confirmed** |
| **Total Query References** | 6 | ViDoSeek ground-truth qrels | Verified |
| **Orphan Queries (Missing Pages)** | 0 | 0 dangling queries | PASS |
| **Unreferenced Corpus Pages** | 15 | Cataloged background corpus | Documented |

---

## 2. Methodology & Invariant Guarantees

1. **Dual Hashing Separation:**
   - `file_sha256`: SHA-256 of the source PDF / asset file container.
   - `content_sha256`: SHA-256 of the canonical normalized page text / pixel content.
2. **Canonical Page ID Normalization:**
   - Format: `{document_id}_page_{page_number:04d}` (1-indexed, zero-padded to 4 digits).
   - All legacy aliases (such as `_p1`, `_1`, `.pdf_page_1`) are cataloged in `alias_manifest.csv` and resolved traceably.
3. **Split Partition Disjointness:**
   - Invariant checked: `intersection(train, val, test) == empty`.
   - Content hash collision checked across splits. Any collision spanning distinct partitions is flagged with `split_leakage = true` and `resolution = split_leakage_blocker`.

---

## 3. Findings & Resolution

- **Content Duplicate Analysis:**
  - Duplicate groups identified: `1`.
  - Pairwise duplicates within the same split partition are tracked under `intra_split_duplicate` or `canonical_alias_assigned`.
- **Cross-Split Leakage Analysis:**
  - Found: `0` instances.
  - Result: `Zero cross-split leakage confirmed`.
- **Qrel & Ground-Truth Consistency:**
  - All query target references map to valid canonical page IDs in `page_manifest.csv`.
  - Dangling query count: `0`.

---

## 4. Acceptance & Gate G1 Readiness

The generated manifests (`page_manifest.csv`, `alias_manifest.csv`, `duplicate_report.csv`) satisfy Gate G1 criteria `G1-COL-01`, `G1-COL-02`, and `G1-COL-03`.
