# Documentation Folder Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Place every document and proposal in a topic folder, leaving only README.md and catalog.json at the docs root.

**Architecture:** Move the 30 remaining root documents into the six existing topic groups and oracle subgroups. Rewrite current links and runtime document references; retain historical result snapshots and publish current preparation manifests separately.

**Tech Stack:** Git, Python pathlib/hashlib/json, Markdown, pytest.

**Spec:** User request on 2026-10-04: files shown at the docs root must belong to folders; remove duplicates of already organized documents.

## Global Constraints

- Do not change the user's root milestone workbook or image.png.
- Delete a duplicate only after confirming identical content and a surviving canonical file.
- Preserve historical files under evidence/, results/, runs/ and artifacts/.
- Preserve execution authorization, query selection, numerical settings and scientific results.
- Update only pins affected by this migration; do not silently repair preexisting drift.

## Review Focus

- Relative Markdown links must resolve from the document's new directory.
- Source-snapshot paths in historical review scripts must retain their original spelling.
- Runtime constants and config references must agree on the new locations.
- Document/source pins must reflect changed bytes; historical hashes remain historical.
- The docs root must contain only the navigation files, with all 63 original documents accounted for.

### Task 1: Move and reconnect documents

**Files:** docs topic folders, docs/catalog.json, Markdown navigation throughout the repository, document constants under scripts/ and src/oracle_study/, configs/vidoseek*.json.

- [x] Inventory and compare all document hashes before moving.
- [x] Move the 30 root documents into their catalog category; place oracle proposals with their experiment family.
- [x] Rewrite relative links from the old source location to the new destination; update current repo-relative references.
- [x] Update only affected source pins and hardcoded document hashes, respecting dependency order.

### Task 2: Preserve preparation validation and verify

**Files:** docs/04_data_protocol/manifests/, scripts/prepare_vimdoc_m3.py, scripts/prepare_vimdoc_archive_content_audit.py, group READMEs and docs/catalog.json.

- [x] Publish current preparation manifests derived from historical manifests, recording parent commit and historical manifest hashes.
- [x] Point preparation scripts at current manifests; preserve historical artifacts unchanged.
- [x] Verify inventory, link resolution, duplicate detection, unaffected evidence hashes and root workbook/image preservation.
- [x] Run existing focused tests for moved proposal/config consumers and ViMDoc preparation; report preexisting failures separately.
- [x] Review the bounded migration diff.

Integration: commit the verified migration and push develop.

## Execution Notes

- No byte-identical duplicates were found among documentation files; all 63 source documents remain accounted for.
- Current preparation manifests are new checkout inventories. Their historical source manifests retain all original bytes and hashes.
- Ruling: run existing consumer tests and link/hash/AST checks without adding tests that mirror path substitutions; this change relocates existing files and constants.
- Ruling: keep root workbook changes and the user's untracked image outside the commit. The workbook was deleted externally during final verification; the complete workbook in docs remains unchanged.
- Verification: all 63 canonical documents exist, no exact duplicates exist, migrated input pins match, and active Markdown links introduce no missing targets.
- Existing consumer tests: 177 passed, 12 failed. An isolated baseline matching all 690 pre-migration working-file hashes had 172 passed, 17 failed; every current failure also exists in that baseline. Remaining failures involve preexisting source hash drift. Current ViMDoc preparation manifests avoid five previous inventory/hash failures without rewriting historical evidence.
