# M2.10 — Readiness replay on the A003 revision (prepared, owner confirmation pending)

Owner: Thanh. **Executed by:** Tấn Phát (Research Lead) via Claude Code. This is
**not** the independent M2.10 owner's audit, because the executor also built
A003. Thanh confirms it by rerunning the same command.

Status: `AUDIT_REPLAY_PREPARED_READINESS_PENDING_REVIEW`. Report: [`audit.json`](audit.json).

```
python scripts/audit_m210_a003_readiness.py --output <new create-once path>
```

`scripts/audit_m210_a003_readiness.py` imports the M2.10-001 checks unchanged.
`scripts/audit_m210_readiness.py` is still byte-identical (`da4e3b6f…`), so
[M2.10-001](../m2.10-001/README.md) remains replayable. The replay then covers:

| Check | Result |
| --- | --- |
| Revision bytes: m2.6-001, m2.8-001, m2.8-002, m2.7-003 (17/30/13/2 files) | `PASS` |
| Frozen splits 799/171/172 and M2.7 structural + synthetic parity | `PASS` |
| Coverage recomputed from 1,142 per-query rows | `PASS`: macro recall 1.0, uncovered 0 in train, validation and test |
| Label order: label-free freeze → development qrels → test qrels (coverage only) | `PASS` |
| A003 lineage: amendment hash, baseline freeze, array hashes, expansion log, M2.7 binding | `PASS` |
| Local Parquet rehash (six artifacts) | `PASS_REHASHED` |
| Full-array replay of the expanded candidates and handover | `PASS_FULL_ARRAY_REPLAY` |
| M2.7 binding live replay versus m2.7-003 | `PASS_MATCHES_M2.7-003` |
| Local tests M2.4/M2.5/M2.7/M2.8/M2.10 (20/6/24/56/6) | all OK |
| Reload | Synthetic in-process only; real checkpoint reload belongs after a pilot |

M2.10-001 could replay only archived receipts. This replay rehashed and rebuilt
the actual payloads, because the three M2.8-001 score matrices and the
M2.8-002 Parquet files were present locally.

**Resolved blockers:**

- `M2.8_ZERO_UNCOVERED_GATE_FAILED`;
- `M2.7_REAL_INPUT_BINDING_NOT_FROZEN`.

**Remaining blockers:**

- `A003_INDEPENDENT_REVIEW_PENDING`;
- `M2.10_OWNER_CONFIRMATION_PENDING`;
- `NAMED_HUMAN_REVIEW_PENDING`.

No test ranking metric was computed and no model was trained. This is not a
D1 decision.
