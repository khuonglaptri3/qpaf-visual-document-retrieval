# M2.10-003 — A003 readiness replay

**Owner:** Thanh. **Executed by:** Codex at Thanh's request on 2026-10-21.
**Technical replay:** `PASS`. **Owner confirmation:** `PENDING_THANH_REVIEW`.

[`audit.json`](audit.json) repeats the M2.10-002 checks without changing the
M2.10 audit source. The three frozen M2.8-001 `scores.npy` files were read from
Modal workspace `tlcn-group1`, Volume `qpaf-m28-score-cache`, and each SHA-256
matched `portable_manifest.json`. The six missing M2.8-002 Parquet files were
rebuilt from those matrices. All six regenerated files matched the byte sizes
and SHA-256 values in [`bundle_hashes.json`](../m2.8-002/bundle_hashes.json)
before the audit used them. The original executor's local Parquet files were
not obtained.

| Check | Result |
| --- | --- |
| Six Parquet payload hashes | `PASS_REHASHED` |
| Full-array candidate replay | `PASS_FULL_ARRAY_REPLAY` |
| M2.7 real-input binding replay | `PASS_MATCHES_M2.7-003` |
| Coverage, train / validation / test | `799/799`, `171/171`, `172/172`; zero uncovered |
| M2.4 / M2.5 / M2.7 / M2.8 / M2.10 tests | `20 / 6 / 24 / 56 / 6`, all pass |

Every field in the M2.10-002 report except local test logs was reproduced.
The source script hard-codes its original `executed_by` value, so this successor
report corrects that attribution and records how its payloads were obtained.
The script itself and the M2.10-002 record remain unchanged.

This is an assisted technical replay, not a named human sign-off. Thanh still
needs to confirm the audit as M2.10 owner. A003 amendment sign-off and the
named independent D1 review remain pending; this record does not change the
M2.11-001 `BLOCKED` decision or authorize M3.
