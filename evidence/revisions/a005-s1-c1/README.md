# A005 Stage 1 calibration C1 — ViMDoc archive content audit

**Status:** `FAILED_ATTEMPT_CONSUMED_NO_RETRY` at stage `frozen_identity_contract`.
The data contract is `BLOCKED_DIFFERENT_CONTENT_PAGE_ID_COLLISION`.

## Run

| | |
| --- | --- |
| Authorization | `configs/vimdoc_archive_content_audit_v1.json` at `3c56aac`, SHA-256 `5ce4d505…3c72` (one invocation, CPU 1 core, 4 GiB, 6 h timeout) |
| Approval | Research Lead: "Duyệt calibration", cost cap 10 USD |
| Source commit | `a689d9ecd7c9e06e3332e410c4cbe61cc2c71392` |
| Modal | app `ap-1S2STvGdqW62jl4O6TmJtW`, call `fc-01M61GYZ9HRNM7K5GCG4XGKVSB` |
| Elapsed | 140 s inside the function (reserved cost bound 0.47 USD) |
| Retries | none |

Files copied unchanged from the volume path `audits/vimdoc/vimdoc_archive_content_audit_v1/`:

| File | SHA-256 |
| --- | --- |
| [`_ATTEMPTED.json`](_ATTEMPTED.json) | `e5cdc5bf740091fd12e4186d241b91db67636a038e726276812aaca94a9e58ea` |
| [`_FAILED.json`](_FAILED.json) | `2346a158925b906e2f04102d423b3f15d54a77f9ac2c80c38116f9644ac630a2` |
| [`audit_summary.json`](audit_summary.json) | `e1f8378162c1cf73ab083bda1a9ddabdcacc702b02b8b71f1794ceb92b3e22e1` |
| `asset_inventory.jsonl` (17.8 MB, left on the volume) | `fabee762b46b6aa3fd3402c784e2b5cf4b88148eac73d58245ab68c7c39ab1ad` |

## Findings

- **Archive.** It matches the frozen bytes: SHA-256 `de569c8d…2c71`, 17,455,193,968 bytes.
- **Assets and page IDs.** There are 76,347 assets (55,952 `.png`, 20,395 `.jpg`) and
  70,080 page IDs.
- **Collisions.** Every one of the 6,267 page IDs that has two assets is a `.jpg` + `.png`
  pair, and in **every** pair the bytes differ. The frozen identity rule treats this as
  `BLOCK` and forbids preferring an extension.
- **Document count.** Over all 70,080 page IDs there are **1,247 documents**, matching the
  expectation. The collisions sit in 132 documents. With the blocked pages removed, only
  63,813 canonical pages in 1,116 documents remain. That is why the contract check reported
  1,116 against the expected 1,247.
- **Duplicates across page IDs.** There are 308 content-duplicate groups that span different
  page IDs. The spec keeps these.

## HEAVEN reference behaviour

HEAVEN (`retrieval/heaven/utils.py` at `3eea5ca`) maps pages to documents by removing the
final `_` segment. It does not deduplicate pages; `check_dict` only prints a warning.
ViMDoc evaluation is document-level with the max fused page score. The two assets of a
colliding page always belong to the same document, so keeping both cannot move relevance
across documents.

## What this blocks

OCR and score extraction must not start until the Research Lead decides the collision
policy. That decision is a change to the frozen identity spec. No OCR, no retriever, no
qrels and no query table was touched. The calibration cap has about 9.5 USD left.
