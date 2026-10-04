# M1.6 — Primary-Corpus Collision Audit

**Audit Status:** `REVIEW_REQUIRED_OVERLAP`
**Evidence kind:** `real_corpus_cpu_audit`
**Independent review:** PENDING. This report does not grant G1 acceptance.
**Owner:** Khương (Data & Technical Owner)
**Evaluator/Auditor:** QPAF Collision Audit Engine v1.0
**Timestamp (UTC):** `2026-09-28T16:54:12.833970+00:00`
**Target Dataset:** `Qiuchen-Wang/ViDoSeek` @ `e91a92ba5f38690696c7e66be5c5474b54c6e791`

---

## 1. Audit Scope & Inventory Summary

| Metric | Measured Value | Requirement / Target | Audit Evaluation |
| :--- | :--- | :--- | :--- |
| **Total Documents** | 292 | Multi-document corpus | Complete |
| **Total Pages Cataloged** | 5385 | All constituent PDF pages | 100% indexed |
| **Unique Content SHA-256** | 5380 | Content-based deduplication | Recorded |
| **Duplicate Content Groups** | 5 | Explicit duplicate tracking | Documented |
| **Cross-Split Leakage** | 0 | **0 (Zero Tolerance)** | **Review required: 0 pairwise collisions, 3813 shared content groups** |
| **Total Query References** | 1142 | ViDoSeek ground-truth qrels | Verified |
| **Orphan Queries (Missing Pages)** | 0 | 0 dangling queries | PASS |
| **Unreferenced Corpus Pages** | 4495 | Cataloged background corpus | Documented |

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
  - Duplicate groups identified: `5`.
  - Pairwise duplicates within the same split partition are tracked under `intra_split_duplicate` or `canonical_alias_assigned`.
- **Cross-Split Leakage Analysis:**
  - Found: `0` instances.
  - Result: `Review required: 0 pairwise collisions, 3813 shared content groups`.
- **Qrel & Ground-Truth Consistency:**
  - Missing positive targets: `0`; details in `qrel_validation.json`.
  - Dangling query count: `0`.

---

## 4. Acceptance & Gate G1 Readiness

The manifests support review of `G1-COL-01`, `G1-COL-02`, and `G1-COL-03`; they do not sign off those criteria.
Query partitions and document/content overlap are measured separately in `overlap_report.json`.
Shared documents: `205`. Shared content groups: `3813`.
Page fingerprints use `pdfium_rgb_72dpi_v1`; perceptual/semantic duplicates are not measured.
