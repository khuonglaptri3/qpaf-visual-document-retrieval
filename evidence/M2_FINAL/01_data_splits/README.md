# M2.1 — Frozen data-split roles

**Owner:** Thanh

**Selected revision:** [`m2.1-001`](../../revisions/m2.1-001/)

**State:** `VERIFIED_ACTIVE_PRIMARY_SPLITS`

The pinned ViDoSeek payload was reproduced from the tracked Hugging Face location
manifest and verified byte-for-byte before this revision was created. M2.1 reuses the
accepted M1.3 split artifacts read-only; it does not rewrite their IDs or hashes.

| Active role | Queries | Artifact |
|---|---:|---|
| Train | 799 | `train_ids.txt` from M1.3 |
| Validation | 171 | `val_ids.txt` from M1.3 |
| Frozen primary test | 172 | `test_ids.txt` from M1.3 |

The three active query sets have union size 1,142 and pairwise overlap 0. ViMDoc
confirmation remains future scope, and no external dataset has been adopted. This
data-readiness record does not authorize learned training or large-scale inference.

## Verification

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/audit_primary_corpus.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-zip data/raw/vidoseek-e91a92b/vidoseek_pdf_document.zip `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --verify-splits --dry-run

.venv/Scripts/python.exe scripts/freeze_m21_data_splits.py `
  --output-dir evidence/revisions/m2.1-new-revision
```

The selected revision is create-once. Use a new revision directory for any later
rerun; do not overwrite `m2.1-001`.
