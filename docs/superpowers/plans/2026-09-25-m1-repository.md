# M1 Repository Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The user already authorized the described repository and restart.

**Goal:** Establish the research repo and generate an honest, reproducible M1.4 starting-state package for Khương.

**Architecture:** A small Python CLI inventories local assets and hashes their bytes. Evidence is an immutable snapshot tied to a Git revision. M1.6 and M1.8 preparation stays explicitly blocked/draft until real inputs exist.

**Tech Stack:** Python standard library >=3.11, unittest, Git, GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-09-25-m1-repository-design.md`.

## Global Constraints

- Preserve both supplied files and use the timeline's seven evidence directories.
- Work on `feature/m1-repository-audit`, integrate into `develop`, retain `main` as bootstrap.
- Record actual timestamps; planned work date is 23/09/2026.
- No new runtime dependencies; no invented corpus, experiment or sign-off.
- Private GitHub repository `khuonglaptri3/qpaf-visual-document-retrieval`.

## Review Focus

- File contents may change or become unreadable while scanning: record errors rather than a valid hash.
- Empty data/config/run directories must produce gaps rather than an acceptance claim.
- An output namespace may already exist: refuse to overwrite it.
- Linked paths or a crafted manifest may escape the root: reject/skip them.
- Windows newlines must not invalidate hashes after Git checkout: preserve supplied inputs and normalize new text.

## Task 1: Repository bootstrap and Gitflow

Files: `.gitignore`, `.gitattributes`, `README.md`, `CONTRIBUTING.md`, design and plan.
Consumes: the two source planning files. Produces: the initial `main` commit and feature branch.

- [x] Configure repository-local author from the verified GitHub identity.
- [x] Commit the bootstrap on `main`.
- [x] Run `git switch -c develop`, then `git switch -c feature/m1-repository-audit`.
- [x] Check `git branch` and `git status --short`; expect the three branches and a clean feature checkout.

## Task 2: Auditable M1.4 inventory utility

Files: `scripts/audit_repository.py`, `src/qpaf/audit.py`, `src/qpaf/__init__.py`, `tests/test_audit.py`, `pyproject.toml`.
Consumes: an existing directory via `--root`. Produces: create-once inventory CSVs, Git snapshot, gap log, metadata and hash verification CLI.

- [x] Write CLI tests with temporary files before implementation. Use literal SHA-256 for bytes `abc`: `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`.
- [x] Run `python -m unittest discover -s tests -v`; expect failures because the CLI is not implemented.
- [x] Implement the interface and safeguards in the spec. Inventory columns are `path`, `category`, `size_bytes`, `sha256`, `status`, `note`; specialised inventories retain those columns.
- [x] Run the same complete suite; require no failures before committing.

## Task 3: Handover preparation and real snapshot

Files: directory READMEs, `docs/khuong-m1-checklist.md`, `evidence/M1_FINAL/`, updated README and a PR template.
Consumes: the verified CLI and timeline. Produces: actual M1.4 evidence, M1.6 input templates, M1.8 draft policies and explicit dependencies.

- [x] Add dated task tracking, ownership notes and corpus/alias/duplicate CSV schemas.
- [x] Write OCR routing/calibration/failure and artifact namespace policies without invented numerical thresholds.
- [x] Commit implementation and preparation before taking the audit snapshot.
- [ ] Run `python scripts/audit_repository.py --root . --output evidence/M1_FINAL/01_repository_audit`; expect a generated snapshot with PARTIAL status and missing-asset gaps.
- [ ] Run `python scripts/audit_repository.py --root . --verify evidence/M1_FINAL/01_repository_audit/hash_manifest.csv`; expect valid hashes.
- [ ] Review the real CSVs and gap log, then commit evidence. Record pending dataset/source/protocol inputs.

## Task 4: Review, integrate and publish

Consumes: committed feature and evidence. Produces: verified `develop` and GitHub repository.

- [ ] Review the full diff and run the complete suite and actual manifest verification.
- [ ] Merge the feature into `develop` with `--no-ff` after checks pass.
- [ ] Create the private repository and push `main` and `develop`; set `develop` as default.
- [ ] Verify remote branch SHAs and visibility; report the URL and remaining M1 dependencies.
