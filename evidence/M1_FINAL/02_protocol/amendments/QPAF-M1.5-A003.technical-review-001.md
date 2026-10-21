# A003 technical review — 2026-10-21

**Requested by:** Thanh. **Executed by:** Codex.
**Technical result:** `PASS`. **Independent human sign-off:** `PENDING`.

The reviewed amendment is
[`QPAF-M1.5-A003.md`](QPAF-M1.5-A003.md), SHA-256
`0afacbde32d2aa4a31a53c39888f11cd20d03af5febfe28aac074de4d23e514c`.
It is explicitly post hoc after one uncovered training query. This review
does not reclassify it as preregistered.

| Check | Finding |
| --- | --- |
| Label-free construction | `build_expanded_candidates` accepts score arrays and ordered IDs; it reads no qrels, split membership or query-ID content. Query IDs are carried as opaque row keys. |
| Fixed policy | One top-RRF document per query, RRF constant 60, original channel top-200 union preserved, at most 600 candidates. |
| Audit order | The runner freezes and replays candidates before opening development qrels, then opens test qrels only for frozen-set coverage. |
| Byte replay | Three source score matrices matched the M2.8-001 manifest. Six independently regenerated Parquet payloads matched the M2.8-002 manifest byte-for-byte. |
| Coverage and binding | 2,075 pages added; maximum 579 candidates per query; zero uncovered queries in all three splits. M2.7-003 real-input binding replay passed. |
| Claim boundary | No learned model was trained and no test ranking metric was used to choose the policy. Higher candidate recall makes no ranking-quality claim. |

The detailed replay is in [`m2.10-003`](../../../revisions/m2.10-003/README.md).
The original executor's Parquet files were not obtained; matching all six
frozen byte hashes verifies the regenerated payloads against the committed
manifest. This automated technical review does not satisfy the named human
sign-off required by the amendment procedure. A named reviewer must record
their acceptance and the M1.7 registry owner must append the governance event
before A003 can support a D1 `PASS`.
