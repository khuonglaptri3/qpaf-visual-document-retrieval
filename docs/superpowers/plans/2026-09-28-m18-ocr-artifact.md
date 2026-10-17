# M1.8 OCR Policy, Failure Thresholds & Artifact Namespace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the M1.8 OCR Quality & Routing Policy subsystem, Artifact Namespace manager, and publish the calibrated revision package at `evidence/revisions/m1.8-001/`.

**Architecture:** Build `src/qpaf/m18/` with `ocr_policy.py` (text quality metric calculation, routing decision between native text and OCR fallback) and `namespace.py` (run ID validation and create-once artifact layout enforcement). Provide a CLI script `scripts/audit_ocr_policy.py` and unit test suite `tests/test_m18_ocr.py`. Generate calibrated policy artifacts in `evidence/revisions/m1.8-001/` with tamper-evident SHA-256 manifest.

**Tech Stack:** Python 3.11, standard library (`pathlib`, `re`, `hashlib`, `json`, `csv`, `argparse`, `dataclasses`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-09-28-m18-ocr-artifact-design.md`.

## Global Constraints

- CPU-only execution; closed boundary (`execution_authorized = false`) maintained.
- Append-only governance: preserve historical baseline in `evidence/M1_FINAL/05_ocr_artifacts/` without modifying pinned hashes.
- Grounded honesty: numerical thresholds in `ocr_failure_threshold.md` must be explicitly marked as `PROVISIONAL — BENCHMARK HEURISTIC` awaiting M2.3 sample calibration; zero invented calibration data.
- 100% test pass rate across the full test suite.

## Review Focus

1. Native-text vs OCR Fallback routing accuracy based on length and printable character ratios.
2. Robust detection of corrupted/mojibake text (control characters, CID font failure).
3. Canonical Run ID parsing and regex validation matching Thanh's M1.7 naming specification.
4. Create-once directory safety: raise `FileExistsError` on existing run directory without overwriting.
5. Markdown formatting and schema completeness of `evidence/revisions/m1.8-001/` artifacts.

---

### Task 1: Core OCR Quality & Namespace Modules (`src/qpaf/m18/`)

**Files:**
- Create: `src/qpaf/m18/__init__.py`
- Create: `src/qpaf/m18/ocr_policy.py`
- Create: `src/qpaf/m18/namespace.py`
- Test: `tests/test_m18_ocr.py`

**Interfaces:**
- `ocr_policy.py`:
  - `QualityMetrics`: Dataclass holding `char_count: int`, `printable_ratio: float`, `estimated_confidence: float`.
  - `ExtractionDecision`: Dataclass holding `route: str` (`NATIVE_TEXT_QUALIFIED`, `OCR_FALLBACK_TRIGGERED`, `EXTRACTION_FAILED`), `metrics: QualityMetrics`, `reason: str`.
  - `evaluate_page_text(text: str, confidence: Optional[float] = None, min_chars: int = 50, min_printable_ratio: float = 0.85) -> ExtractionDecision`
- `namespace.py`:
  - `parse_canonical_run_id(run_id: str) -> Dict[str, Any]`
  - `format_canonical_run_id(experiment_id: str, timestamp_utc: datetime, attempt_num: int) -> str`
  - `create_run_namespace(base_dir: Path, experiment_id: str, run_id: str) -> Path` (raises `FileExistsError` if exists)

- [ ] **Step 1: Write failing unit tests in `tests/test_m18_ocr.py`**
- [ ] **Step 2: Run tests to verify failure (RED)**
- [ ] **Step 3: Implement minimal code in `src/qpaf/m18/` (GREEN)**
- [ ] **Step 4: Run tests to verify all tests pass**
- [ ] **Step 5: Commit changes to Git**

---

### Task 2: OCR Policy & Namespace CLI (`scripts/audit_ocr_policy.py`)

**Files:**
- Create: `scripts/audit_ocr_policy.py`
- Test: `tests/test_m18_ocr.py`

**Interfaces:**
- CLI arguments:
  - `--output-dir`: Output path for revision artifacts (defaults to `evidence/revisions/m1.8-001`).
  - `--probe`: Run simulated calibration probe across clean text, short text, mojibake text, and image scan mockups.
  - `--verify-namespace`: Validate an arbitrary run ID string.

- [ ] **Step 1: Add CLI integration tests in `tests/test_m18_ocr.py`**
- [ ] **Step 2: Run test to verify failure (RED)**
- [ ] **Step 3: Implement CLI logic in `scripts/audit_ocr_policy.py` (GREEN)**
- [ ] **Step 4: Run tests to verify CLI tests pass**
- [ ] **Step 5: Commit changes to Git**

---

### Task 3: Publish Calibrated Revision `evidence/revisions/m1.8-001/`

**Files:**
- Create: `evidence/revisions/m1.8-001/ocr_checklist.md`
- Create: `evidence/revisions/m1.8-001/ocr_failure_threshold.md`
- Create: `evidence/revisions/m1.8-001/artifact_namespace.md`
- Create: `evidence/revisions/m1.8-001/calibration_methodology.md`
- Create: `evidence/revisions/m1.8-001/hash_manifest.csv`

- [ ] **Step 1: Run `scripts/audit_ocr_policy.py` to generate the calibrated revision package**
- [ ] **Step 2: Generate `hash_manifest.csv` for `evidence/revisions/m1.8-001/`**
- [ ] **Step 3: Verify all file contents and check that baseline `evidence/M1_FINAL/05_ocr_artifacts/` is intact**
- [ ] **Step 4: Commit revision `m1.8-001` to Git**

---

### Task 4: Regression Testing & Documentation Update

**Files:**
- Modify: `docs/06_handover/khuong-m1-checklist.md`
- Modify: `docs/06_handover/m1.4-m1.5-m1.6-audit-report.md` (or append M1.8 overview)

- [ ] **Step 1: Update `docs/06_handover/khuong-m1-checklist.md` reflecting M1.8 completion**
- [ ] **Step 2: Run full regression test suite (`python3 -m unittest discover -s tests -v`)**
- [ ] **Step 3: Commit all documentation updates to Git**
