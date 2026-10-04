# QPAF — Query-Page Adaptive Fusion for Visual Document Retrieval

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Tests](https://img.shields.io/badge/tests-140%20passed%2C%201%20skipped-success.svg)](#full-automated-test-suite-execution)
[![Gate G1](https://img.shields.io/badge/Gate%20G1-CONDITIONAL__PASS-green.svg)](docs/M1.10_GATE_CLOSURE_REPORT.md)
[![Milestone](https://img.shields.io/badge/Milestone-M1.1--M1.10%20CLOSED-brightgreen.svg)](docs/M1_ACCEPTANCE_SUMMARY_AND_RUNBOOK.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Official research repository developed by **Group 01** for multimodal Visual Document Retrieval (VDR). This codebase contains the theoretical formalization, core architectures, verification suites, experiment registries, and reproducible data pipeline for **QPAF** (*Query-Page Adaptive Fusion*) and its comparative baseline **QARF** (*Query-Adaptive Retrieval Fusion*).

---

## Table of Contents

- [1. Executive Summary & Research Motivation](#1-executive-summary--research-motivation)
- [2. System Architecture & Methodological Core](#2-system-architecture--methodological-core)
  - [Tri-Modal Retrieval Channels](#tri-modal-retrieval-channels)
  - [QARF vs. QPAF Comparison](#qarf-vs-qpaf-comparison)
  - [The 13-Dimensional Feature Vector (`qpaf13_v1`)](#the-13-dimensional-feature-vector-qpaf13_v1)
  - [Gating Network & Pairwise Optimization](#gating-network--pairwise-optimization)
  - [Evaluation Benchmarks & Dataset Roles](#evaluation-benchmarks--dataset-roles)
- [3. Sprint 1 Progress Report & Milestone Acceptance (M1.1 – M1.10)](#3-sprint-1-progress-report--milestone-acceptance-m11--m110)
  - [Milestone Acceptance Table](#milestone-acceptance-table)
  - [Detailed Milestone Summaries](#detailed-milestone-summaries)
- [4. Complete Terminal Command Runbook](#4-complete-terminal-command-runbook)
  - [Prerequisites & Environment Configuration](#prerequisites--environment-configuration)
  - [Automated Dataset Reproduction (Hugging Face LFS)](#automated-dataset-reproduction-hugging-face-lfs)
  - [Corpus Auditing & Deterministic Split Generation (M1.3)](#corpus-auditing--deterministic-split-generation-m13)
  - [Read-Only Split Verification (M1.3)](#read-only-split-verification-m13)
  - [Visual Collision, Alias & Leakage Audit (M1.6)](#visual-collision-alias--leakage-audit-m16)
  - [Repository Integrity & Byte-Level Manifest Verification (M1.4)](#repository-integrity--byte-level-manifest-verification-m14)
  - [Gating Network Optimization & Gradient Verification (M1.2)](#gating-network-optimization--gradient-verification-m12)
  - [OCR Fallback Policy & Run ID Auditing (M1.8)](#ocr-fallback-policy--run-id-auditing-m18)
  - [Modal Multimodal Pipeline & Software Fixture (M1.1)](#modal-multimodal-pipeline--software-fixture-m11)
  - [Full Automated Test Suite Execution (140 Tests)](#full-automated-test-suite-execution-140-tests)
  - [Granular Unit Tests by Milestone](#granular-unit-tests-by-milestone)
  - [Gitflow Workflow & Contribution](#gitflow-workflow--contribution)
- [5. Repository Directory Layout](#5-repository-directory-layout)
- [6. Data Hygiene & Reproducibility Policy](#6-data-hygiene--reproducibility-policy)

---

## 1. Executive Summary & Research Motivation

Visually rich documents (e.g., scanned PDF reports, financial statements, slide decks, scientific papers, infographics) contain information distributed across both textual prose and visual layouts (diagrams, tables, typography, headers). Traditional single-channel information retrieval systems often fail:
- **Lexical retrievers (BM25)** excel at exact keyword matches and identifiers but break on visual elements, tables, and synonymic variations.
- **Dense text embeddings (e.g., BGE-M3)** capture semantic nuance in running text but lose spatial relationships and structural formatting.
- **Vision-language late-interaction retrievers (e.g., ColPali)** capture multi-modal visual page layouts and graphics but may underperform on dense, unstructured text queries or exact serial numbers.

**QPAF (Query-Page Adaptive Fusion)** solves this bottleneck by dynamically computing fusion weights conditioned on **both** query characteristics and page visual/textual features. Rather than applying a single global weight or query-level fixed weights across the entire candidate pool, QPAF dynamically adapts the channel weights for every candidate page pair $(q, p)$, maximizing retrieval performance.

---

## 2. System Architecture & Methodological Core

### Tri-Modal Retrieval Channels

The retrieval pipeline integrates three complementary channels:
1. **Lexical Channel ($s_{\text{bm25}}$):** Anserini/BM25 indexing native and OCR-extracted text tokens.
2. **Dense Semantic Text Channel ($s_{\text{dense}}$):** BGE-M3 dense bi-encoder text representations.
3. **Multimodal Visual Channel ($s_{\text{visual}}$):** ColPali visual document retriever operating directly on rasterized 150 DPI page images.

Each channel outputs a candidate score $s_c(q, p) \in \mathbb{R}$. Scores are standardized using min-max scaling with quantile clipping across the shared candidate pool.

### QARF vs. QPAF Comparison

| Architectural Property | QARF (*Query-Adaptive Retrieval Fusion*) | QPAF (*Query-Page Adaptive Fusion*) |
| :--- | :--- | :--- |
| **Gating Input** | Query features only: $\mathbf{x}_q \in \mathbb{R}^{d_q}$ | Joint query-page features: $\mathbf{x}_{q, p} \in \mathbb{R}^{13}$ |
| **Weight Granularity** | Per-query: $\mathbf{w}_q \in \Delta^2$ | Per-query-page pair: $\mathbf{w}_{q, p} \in \Delta^2$ |
| **Page-Level Adaptation** | Uniform across all candidate pages for query $q$ | Dynamically shifts based on page visual complexity, text density, and channel divergence |
| **Fusion Scoring** | $S(q, p) = \sum_{c} w_{q, c} \cdot s_c(q, p)$ | $S(q, p) = \sum_{c} w_{q, p, c} \cdot s_c(q, p)$ |
| **Parametric Budget** | Equivalent lightweight MLP | Equivalent lightweight MLP |

### The 13-Dimensional Feature Vector (`qpaf13_v1`)

The gating network ingests a normalized 13-dimensional feature vector $\mathbf{x}_{q, p} \in \mathbb{R}^{13}$ engineered to capture query difficulty, page layout characteristics, and cross-channel consensus:

| Index | Feature Name | Category | Formulation / Description | Normalization & Edge Handling |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `query_length` | Query | Character length: $\operatorname{len}(q)$ | Min-max scaled, clipped at $[0, 500]$ |
| **1** | `query_word_count` | Query | Token count: $\operatorname{count}(\text{tokens}(q))$ | Scaled, clipped at $[0, 100]$ |
| **2** | `query_char_entropy` | Query | Shannon entropy: $-\sum p_i \log_2(p_i)$ over characters | Bounded $[0.0, 8.0]$, normalized to $[0, 1]$ |
| **3** | `query_digit_ratio` | Query | Proportion of digits: $\frac{\operatorname{count}(\text{digits})}{\operatorname{len}(q)}$ | Naturally bounded $[0.0, 1.0]$; $0$ on empty string |
| **4** | `query_punct_ratio` | Query | Proportion of punctuation marks: $\frac{\operatorname{count}(\text{punct})}{\operatorname{len}(q)}$ | Naturally bounded $[0.0, 1.0]$; $0$ on empty string |
| **5** | `query_question_word` | Query | Interrogative intent indicator (who, what, when, where, why, how, is, are, can, etc.) | Binary $\{0.0, 1.0\}$ |
| **6** | `page_ocr_char_count`| Page | Total character count of OCR/native page text | Log-scaled $\log(1 + C)$, clipped at $[0, 10]$ |
| **7** | `page_ocr_word_count`| Page | Total word count of OCR/native page text | Log-scaled $\log(1 + W)$, clipped at $[0, 10]$ |
| **8** | `page_aspect_ratio` | Page | Aspect ratio: $\frac{\text{width}}{\text{height}}$ | Bounded $[0.2, 5.0]$, normalized |
| **9** | `page_pixel_area` | Page | Normalized canvas area: $\frac{\text{width} \times \text{height}}{10^6}$ | Scaled, clipped at $[0.0, 10.0]$ |
| **10**| `jaccard_overlap` | Interaction | Word token Jaccard: $\frac{\vert T_q \cap T_p \vert}{\vert T_q \cup T_p \vert}$ | Naturally bounded $[0.0, 1.0]$; $0$ on empty union |
| **11**| `score_variance` | Interaction | Variance across channel scores: $\operatorname{Var}([s_{\text{bm25}}, s_{\text{dense}}, s_{\text{visual}}])$ | Clipped at $[0.0, 1.0]$ |
| **12**| `score_margin` | Interaction | Margin between top score and second score: $s_{(1)} - s_{(2)}$ | Clipped at $[0.0, 1.0]$ |

### Gating Network & Pairwise Optimization

- **Architecture:** Multi-Layer Perceptron (MLP) with Layer Normalization and GELU activation, projecting $\mathbb{R}^{13} \to \mathbb{R}^3$.
- **Simplex Mapping:** Softmax activation ensures non-negative channel weights summing strictly to 1:
  $$\mathbf{w}_{q, p} = \operatorname{Softmax}(\operatorname{MLP}(\mathbf{x}_{q, p})) \in \Delta^2, \quad \sum_{c \in \{\text{bm25}, \text{dense}, \text{visual}\}} w_{q, p, c} = 1$$
- **Loss Function:** Margin Pairwise Ranking Loss with margin $\gamma = 0.1$:
  $$\mathcal{L}(q, p^+, p^-) = \max\left(0, \gamma - \left(S(q, p^+) - S(q, p^-)\right)\right)$$
- **Frozen Retriever Policy:** Base retriever weights (BM25, BGE-M3, ColPali) remain **strictly frozen** during training. Gradients flow exclusively to the gating network, avoiding representation drift or cross-channel corruption.

### Evaluation Benchmarks & Dataset Roles

| Dataset | Research Role | Evaluation Metric & Granularity | Corpus Size / Splits |
| :--- | :--- | :--- | :--- |
| **ViDoSeek** | Primary discovery corpus | nDCG@10, Recall@10 (Page-level) | 292 PDFs / 5,385 pages / 1,142 queries (Splits: 799 train / 171 val / 172 test) |
| **ViMDoc** | In-domain confirmation corpus | nDCG@10, MRR (Document-level max-pooling across pages) | Confirmation phase under HEAVEN protocol |
| **ViDoRe V3** | Out-of-domain generalization benchmark | nDCG@10 (Page-level) | Sealed evaluation suite |

---

## 3. Sprint 1 Progress Report & Milestone Acceptance (M1.1 – M1.10)

Sprint 1 (Milestones M1.1 through M1.10) was successfully completed, audited, and formally closed at Gate G1 on **September 29, 2026** with decision `CONDITIONAL_PASS / PROCEED_TO_M2_DATA_PREP`.

### Milestone Acceptance Table

| Milestone | Lead Owner | Objective & Scope | Verified Evidence & Artifacts | Acceptance Status |
| :--- | :--- | :--- | :--- | :---: |
| **M1.1** | Le Thanh | Historical Oracle survey (W7/W66), 5-stage multimodal pipeline, exact simplex binary solver | - Oracle classification report: [`results/m1.1/README.md`](results/m1.1/README.md)<br>- Exact simplex solver: `src/qpaf/m11/oracle.py`<br>- Software pipeline fixture: [`configs/m1.1/software_fixture.toml`](configs/m1.1/software_fixture.toml) | **ACCEPTED**<br>*(Feasibility scope; labeled `reproduction-unverified`)* |
| **M1.2** | Tan Phat | 13-feature schema (`qpaf13_v1`), Gating MLP architecture, pairwise ranking loss, gradient verification | - 13-feature extractor & Gating MLP: `src/qpaf/m12/gate.py`<br>- Finite-difference gradient & SGD optimization tests: [`tests/test_m12_*.py`](tests/)<br>- Software verification receipt: `scripts/verify_m12.py` | **ACCEPTED**<br>*(Core software verified)* |
| **M1.3** | Tran Dinh Khuong | Real ViDoSeek corpus preparation, 292 PDFs / 5,385 pages inspection, deterministic 70/15/15 split generation | - Payload: `vidoseek.json` & `vidoseek_pdf_document.zip` (758 MB)<br>- Audit report on 292 PDFs / 5,385 pages: [`evidence/revisions/m1.3-001/audit_report.json`](evidence/revisions/m1.3-001/audit_report.json)<br>- Frozen deterministic splits: [`evidence/revisions/m1.3-001/splits/`](evidence/revisions/m1.3-001/splits/) | **ACCEPTED**<br>*(Real corpus verified)* |
| **M1.4** | Tran Dinh Khuong | Repository inventory audit, exclusion of `.tmp` artifacts, byte-level SHA-256 manifest verification | - Inventory snapshot (631 files, 295 data assets, 28 source files): [`evidence/revisions/m1.4-004/audit_metadata.json`](evidence/revisions/m1.4-004/audit_metadata.json)<br>- Verified hash manifest: [`evidence/revisions/m1.4-004/hash_manifest.csv`](evidence/revisions/m1.4-004/hash_manifest.csv)<br>- Zero hash collisions across 631 files | **ACCEPTED**<br>*(Snapshot verified)* |
| **M1.5** | Tan Phat *(Reviewed by Thanh)* | Successor Protocol Contract, dataset role formalization, immutable governance event log | - Protocol contract: [`evidence/revisions/m1.5-002/scoped_contract.md`](evidence/revisions/m1.5-002/scoped_contract.md)<br>- Source package manifest: [`evidence/revisions/m1.5-002/package_manifest.json`](evidence/revisions/m1.5-002/package_manifest.json)<br>- Append-only audit log: [`evidence/revisions/m1.5-002/governance_events.jsonl`](evidence/revisions/m1.5-002/governance_events.jsonl) | **ACCEPTED**<br>*(Protocol frozen)* |
| **M1.6** | Tran Dinh Khuong | Collision, alias, and leakage audit on 5,385 real PDF pages; qrels verification and document-sharing boundaries | - Collision report: [`evidence/revisions/m1.6-002/collision_report.md`](evidence/revisions/m1.6-002/collision_report.md)<br>- Results: **0 cross-split leakage**, **0 orphan queries** (1,142/1,142 queries valid), 5 internal duplicate pairs, 205 documents shared across query splits<br>- Page & alias manifests: `page_manifest.csv`, `alias_manifest.csv` | **ACCEPTED**<br>*(Zero leakage verified)* |
| **M1.7** | Le Thanh | Experiment Registry, standardized run naming conventions, traceability matrix, issue tracking log | - Experiment Registry: [`evidence/M1_FINAL/04_experiment_registry/experiment_registry.csv`](evidence/M1_FINAL/04_experiment_registry/experiment_registry.csv)<br>- Traceability Matrix: [`traceability_matrix.csv`](evidence/M1_FINAL/04_experiment_registry/traceability_matrix.csv)<br>- Issue Log (10 open issues tracked): [`issue_log.csv`](evidence/M1_FINAL/04_experiment_registry/issue_log.csv) | **ACCEPTED**<br>*(Traceability verified)* |
| **M1.8** | Tran Dinh Khuong | OCR fallback routing mechanism, text quality controls, timeout policies, runtime GPU execution boundary guards | - Native text $\to$ OCR fallback router: `src/qpaf/m11/dataset.py`<br>- Namespace metadata management: `src/qpaf/m18/namespace.py`<br>- Execution boundary guard: `src/qpaf/m13/boundary.py`<br>- All 140 unit tests passing | **ACCEPTED**<br>*(Runtime guards active)* |
| **M1.9 (G1)** | Full Team | Gate G1 Closure Board, resolution of 6 technical blockers, technical and QA sign-offs, formal G1 decision | - Blocker resolution log: [`evidence/M1_FINAL/06_G1/G1_blocker_log.md`](evidence/M1_FINAL/06_G1/G1_blocker_log.md)<br>- First Review Record: [`evidence/M1_FINAL/06_G1/G1_first_review_record.md`](evidence/M1_FINAL/06_G1/G1_first_review_record.md)<br>- Technical Sign-off: [`evidence/M1_FINAL/06_G1/technical_signoff.md`](evidence/M1_FINAL/06_G1/technical_signoff.md)<br>- QA Sign-off: [`evidence/M1_FINAL/06_G1/qa_signoff.md`](evidence/M1_FINAL/06_G1/qa_signoff.md)<br>- G1 Decision: [`evidence/M1_FINAL/06_G1/G1_final_decision.md`](evidence/M1_FINAL/06_G1/G1_final_decision.md) | **PASSED**<br>*(Conditional Pass)* |
| **M1.10 (R1)** | Tan Phat | Sprint 1 Final Progress Report and formal Milestone 1 Closure Record | - Sprint 1 Progress Report: [`evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md`](evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md)<br>- Milestone 1 Closure Record: [`evidence/M1_FINAL/07_R1/M1_closure_record.md`](evidence/M1_FINAL/07_R1/M1_closure_record.md) | **COMPLETED**<br>*(Milestone 1 Closed)* |

---

### Detailed Milestone Summaries

- **M1.1 (Oracle Upper Bound & Pipeline Infrastructure):** Formatted and categorized historical Oracle exploration runs (W7 fixed-profile 1,142 queries, W66 24 exploratory queries). Formulated the exact per-page simplex solver finding theoretical optimal fusion weights. Constructed a reproducible 5-stage multimodal pipeline architecture (`prepare` $\to$ `bm25` $\to$ `dense` $\to$ `visual` $\to$ `oracle`).
- **M1.2 (Methodological Core & Gradient Verification):** Implemented the 13-dimensional feature extractor, QARF query-level gating, QPAF query-page adaptive gating, softmax fusion scoring, and margin ranking loss. Tested finite-difference analytical gradients against autograd and demonstrated 40-step SGD optimization on synthetic training batches.
- **M1.3 (Real ViDoSeek Corpus & Deterministic Splits):** Acquired the official 758 MB ViDoSeek archive from Hugging Face LFS. Validated all 292 PDFs and counted 5,385 rendered pages. Generated deterministic, stratified 70/15/15 query splits (`train_ids.txt`: 799, `val_ids.txt`: 171, `test_ids.txt`: 172). Established read-only split verification routines.
- **M1.4 (Repository Inventory & Byte Integrity):** Implemented an automated auditing engine. Created revision `m1.4-004` cataloging all 631 repository files (295 data assets, 28 source modules), purging ephemeral `.tmp` artifacts. Every file is tracked with its SHA-256 digest in `hash_manifest.csv`.
- **M1.5 (Successor Protocol Contract):** Authored `scoped_contract.md`, establishing non-negotiable evaluation protocols: qrels isolation (never used during inference or feature engineering), candidate pool standardization, tie-breaking criteria, and immutable governance event logging.
- **M1.6 (Visual Page Collision & Leakage Audit):** Rendered 5,385 real PDF pages at 72 DPI RGB and computed MD5/SHA-256 payload digests. Audited all 1,142 queries: confirmed **0 cross-split leakage** and **0 orphan queries**. Discovered 5 identical page pairs within documents and documented that 205 documents are shared across query splits according to author distribution.
- **M1.7 (Experiment Registry & Traceability):** Instituted a strict run-naming taxonomy (`<dataset>-<model>-<split>-<run-id>`), structured CSV experiment ledger, requirement-to-test traceability matrix, and issue resolution log.
- **M1.8 (OCR Fallback & Runtime Safety Guards):** Implemented automatic routing from native PDF text extraction to PyMuPDF/OCR fallback when character counts fall below minimum density thresholds or show encoding corruption. Integrated execution boundary guards preventing accidental GPU invocation before Gate G1 sign-off.
- **M1.9 (Gate G1 Closure Board):** Convened all three contributors to resolve 6 technical blockers (including test hash mismatches, unverified reproduction flags, and split validation). Secured unanimous Technical Sign-off and QA Sign-off.
- **M1.10 (Sprint 1 Review & Closure):** Compiled the comprehensive Sprint 1 Progress Report and issued the formal Milestone 1 Closure Record.

---

## 4. Complete Terminal Command Runbook

All commands are designed to be run from the root directory in **PowerShell**:
```powershell
C:\Users\lanph\OneDrive\Desktop\Artificial_Intelligent_Project
```

### Prerequisites & Environment Configuration

Configure standard UTF-8 encoding in PowerShell to prevent character decode errors on Windows:
```powershell
$env:PYTHONUTF8 = '1'
```

Activate the Python 3.11 virtual environment:
```powershell
.venv\Scripts\Activate.ps1
```

Install repository dependencies in editable mode:
```powershell
.venv/Scripts/python.exe -m pip install -e ".[verification,method]"
```

---

### Automated Dataset Reproduction (Hugging Face LFS)

Download `vidoseek.json` (metadata annotations) and `vidoseek_pdf_document.zip` (758 MB), verify the SHA-256 digest against official Hugging Face LFS records, and automatically extract all 292 PDFs (5,385 pages) into `data/raw/vidoseek-e91a92b/pdfs/pdf`:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/download_primary_corpus.py `
  --manifest data/manifests/vidoseek-e91a92b-location.json `
  --extract --force
```

---

### Corpus Auditing & Deterministic Split Generation (M1.3)

Inspect all 292 PDFs, verify positive target pages in `vidoseek.json`, open each PDF to verify 5,385 real pages, and generate deterministic 70/15/15 splits (799 train / 171 val / 172 test):

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_primary_corpus.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-zip data/raw/vidoseek-e91a92b/vidoseek_pdf_document.zip `
  --output evidence/revisions/m1.3-001/audit_report.json `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --generate-splits
```

---

### Read-Only Split Verification (M1.3)

Perform non-destructive split verification against raw annotations and the real PDF archive:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_primary_corpus.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-zip data/raw/vidoseek-e91a92b/vidoseek_pdf_document.zip `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --verify-splits --dry-run
```

---

### M2.1 Data-Split Role Freeze

After reproducing ViDoSeek and verifying the accepted M1.3 splits, create a new
immutable M2.1 evidence revision. The command verifies the pinned raw payload hashes,
split hashes, counts, complete union, and zero query overlap without rewriting M1.3:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/freeze_m21_data_splits.py `
  --output-dir evidence/revisions/m2.1-new-revision
```

The selected project revision is [`evidence/revisions/m2.1-002/`](evidence/revisions/m2.1-002/).
The CLI refuses to overwrite an existing revision; use a new revision directory for a
fresh run. Raw corpus payloads remain local under `data/raw/` and are not committed.

---

### Visual Collision, Alias & Leakage Audit (M1.6)

Rasterize all 5,385 real PDF pages at 72 DPI, compute SHA-256 pixel hashes, detect duplicates/aliases, and verify split isolation and qrels integrity:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_collisions.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-dir data/raw/vidoseek-e91a92b/pdfs/pdf `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --output-dir evidence/revisions/m1.6-002
```

*(Fast fixture dry-run on 5 synthetic documents / 20 pages:)*
```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_collisions.py --fixture --output-dir temp_fixture_audit
```

---

### Repository Integrity & Byte-Level Manifest Verification (M1.4)

Verify the cryptographic SHA-256 digest of all 631 tracked files in snapshot `m1.4-004`:

```powershell
# Verify existing snapshot:
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_repository.py --verify evidence/revisions/m1.4-004/hash_manifest.csv

# Generate a new inventory snapshot:
.venv/Scripts/python.exe scripts/audit_repository.py --output evidence/revisions/m1.4-new-snapshot
```

---

### Gating Network Optimization & Gradient Verification (M1.2)

Execute finite-difference gradient checks, autograd backward passes, and 40-step SGD optimization on synthetic training batches:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/verify_m12.py
```

---

### OCR Fallback Policy & Run ID Auditing (M1.8)

Test clean text extraction, mojibake/corrupted string fallback, minimum density thresholds, and M1.7 run-id naming compliance:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_ocr_policy.py
```

---

### Modal Multimodal Pipeline & Software Fixture (M1.1)

Run the end-to-end 5-stage multimodal retrieval fixture and compute per-query metrics:

```powershell
# Execute the 5-stage pipeline on software fixtures:
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/run_m11_modal.py --config configs/m1.1/software_fixture.toml

# Evaluate per-query metrics on generated outputs:
.venv/Scripts/python.exe scripts/evaluate_m11.py --run-dir results/m1.1/software_fixture/runs/software-fixture/oracle/latest
```

---

### Full Automated Test Suite Execution (140 Tests)

Run all 140 unit and integration tests across M1.1 through M1.8:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

*(Concise run without verbose test listing:)*
```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m unittest discover -s tests
```

*Expected Result: `Ran 140 tests ... OK (skipped=1)` (1 Windows symlink privilege test skipped).*

---

### Granular Unit Tests by Milestone

Execute tests for specific project modules during targeted development:

```powershell
# M1.1 Pipeline & Artifacts:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m11_artifacts.py

# M1.2 Gating Network, Fusion, Loss & Optimization:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m12_fusion.py tests/test_m12_gating.py tests/test_m12_loss.py tests/test_m12_training.py

# M1.3 Real Corpus & Deterministic Splits:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m13_splits.py tests/test_m13_corpus.py tests/test_m13_cli.py tests/test_m13_vidoseek.py

# M1.4 Repository Audit Engine:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_audit.py

# M1.6 Collision, Alias & Split Leakage:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m16_collision.py tests/test_m16_real_audit.py

# M1.7 Experiment Registry & Metadata Integrity:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m17_registry.py

# M1.8 OCR Fallback & Runtime Safety Boundaries:
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest tests/test_m18_ocr.py tests/test_m18_runtime.py
```

---

### Gitflow Workflow & Contribution

```powershell
# 1. Fetch updates and ensure develop branch is active:
git fetch origin
git switch develop
git pull --ff-only origin develop

# 2. Create a feature branch:
git switch -c feature/<milestone>-<task-name>

# 3. Stage verified changes (never stage data/raw/ or large checkpoints):
git status
git add <files>
git commit -m "feat(<scope>): descriptive commit message"

# 4. Push to origin and open a Pull Request:
git push -u origin feature/<milestone>-<task-name>
```

---

## 5. Repository Directory Layout

```text
qpaf-visual-document-retrieval/
├── configs/                          # Experiment & pipeline configuration files
│   ├── m1.1/                         # Modal pipeline & software fixture TOMLs
│   └── m1.2/                         # Methodological core & gating configs
├── data/                             # Dataset management
│   ├── manifests/                    # Versioned location manifests & SHA-256 hashes
│   │   └── vidoseek-e91a92b-location.json
│   └── raw/                          # Raw corpus payload (excluded via .gitignore)
├── docs/                             # Project documentation, guides & audit reports
│   ├── M1_ACCEPTANCE_SUMMARY_AND_RUNBOOK.md   # Complete M1 acceptance & runbook
│   ├── m1.1-m1.8-readiness-audit-2026-09-28.md # Milestone readiness audit
│   ├── m1.2-method-core.md           # 13-feature mathematical specification
│   ├── M1.9_FINAL_ASSESSMENT.md      # Gate G1 review board assessment
│   └── M1.10_GATE_CLOSURE_REPORT.md  # Official Gate G1 closure report
├── evidence/                         # Immutable audit snapshots & evidence records
│   ├── M1_FINAL/                     # Final Sprint 1 sign-offs, registries & reviews
│   └── revisions/                    # Revision folders (m1.3-001, m1.4-004, m1.5-002, m1.6-002)
├── results/                          # Evaluation outputs & experiment artifacts
│   ├── m1.1/                         # Historical Oracle studies & fixture runs
│   └── m1.2/                         # Gating optimization verification receipts
├── scripts/                          # Executable utility and CLI scripts
│   ├── audit_collisions.py           # Collision, alias & leakage auditor (M1.6)
│   ├── audit_primary_corpus.py       # Corpus verification & split generator (M1.3)
│   ├── audit_repository.py           # Repository integrity & snapshot engine (M1.4)
│   ├── download_primary_corpus.py    # Deterministic Hugging Face LFS downloader
│   ├── evaluate_m11.py               # Evaluation engine for M1.1 runs
│   ├── run_m11_modal.py              # 5-stage multimodal pipeline launcher
│   └── verify_m12.py                 # Methodological core & gradient checker (M1.2)
├── src/qpaf/                         # Core Python package
│   ├── m11/                          # Pipeline runner, dataset loaders & Oracle solver
│   ├── m12/                          # 13-feature extractor, Gating MLP & pairwise loss
│   ├── m13/                          # Split manager & execution boundary guards
│   ├── m16/                          # Collision, alias & page hashing tools
│   ├── m17/                          # Registry tracking & schema models
│   └── m18/                          # OCR fallback routing & namespace handlers
└── tests/                            # Complete unit & integration test suite (140 tests)
```

---

## 6. Data Hygiene & Reproducibility Policy

To maintain clean repository hygiene, fast clone operations, and adhere to GitHub file size limits (<100MB):
- **Raw Payloads are Excluded:** The raw data directory `data/raw/` (including `vidoseek_pdf_document.zip` [758 MB] and the 292 unzipped PDFs) is strictly ignored via `.gitignore` (line 30).
- **Deterministic Re-creation:** Anyone cloning this repository can recreate the exact, byte-for-byte identical `data/` structure using the single command in [Automated Dataset Reproduction](#automated-dataset-reproduction-hugging-face-lfs).
- **Immutable Evidence Files:** Historical evidence files in `evidence/M1_FINAL/` are cryptographically verified by `test_m17_registry.py`. Any corrections or updates must be added as sidecar documents or inside new revision folders under `evidence/revisions/`.
- **Runtime Boundary Guards:** GPU model training is gated behind Milestone M2 data preparation. The runtime execution guard in `src/qpaf/m13/boundary.py` enforces protocol boundaries until Gate G1 prerequisites are met.

---

> **Maintained by Group 01**  
> *Lê Thanh — Bùi Trần Tấn Phát — Trần Đình Khương*  
> Project Repository: [https://github.com/khuonglaptri3/qpaf-visual-document-retrieval](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval)
