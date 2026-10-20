# M2.10 — Independent technical readiness audit

Owner: Thanh. Run `scripts/audit_m210_readiness.py --output <new-path>` from the
repo root to create a new, immutable report. The committed [`audit.json`](audit.json)
is the M2.10-001 snapshot. Its source hash and local test outputs are included.

The audit rehashes M2.6/M2.8 revision files, verifies frozen splits and cross-stage
identities, replays QARF/QPAF parity on a synthetic fixture, and recomputes
candidate coverage from every per-query row. It confirms one uncovered train
query under M2.8's frozen top-200/channel union. The required zero-uncovered
gate fails. The reviewed M2.8 full-payload receipts are checked, but the raw
Parquet payload is unavailable in this Git checkout. No real learned checkpoint
exists for reload. Named human review remains pending.

Status: `AUDIT_COMPLETED_READINESS_BLOCKED`. See the
[method note](../../../docs/03_method/m2.10-readiness-audit.md) and the
[M2.8 handover](../m2.8-001/README.md). This record is not a D1 PASS or a
scientific performance claim.
