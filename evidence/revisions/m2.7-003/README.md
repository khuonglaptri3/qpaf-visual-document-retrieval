# M2.7 — Real-input binding for the matched pilot (revision 003)

Owner: Tấn Phát. Binding: [`configs/m2.7/input_binding.json`](../../../configs/m2.7/input_binding.json)
(`QPAF-M2_7-INPUTS-001`).

**Adds to [m2.7-002](../m2.7-002/README.md); does not replace it.**
`configs/m2.7/matched.json` stays byte-identical (`705dd570…`), because
M2.7-002, M2.10-001 and D1 record its hash. The binding pins that manifest by
SHA-256 and replaces its three `PENDING_M2.8` inputs with the accepted
[M2.8-002](../m2.8-002/README.md) files:

- score cache `raw_scores.parquet`;
- candidate set and freeze;
- development and sealed test qrels;
- query texts;
- the three split files.

Each bound hash must equal the M2.8-002 handover, and the handover must have
passed coverage under policy `qpaf_m28_top_document_expansion_v1`.

`verification.json` records:

- Every bound file was rehashed.
- The synthetic M2.7 parity checks still pass: config diff limited to
  `gate_granularity`, bit-identical initialization (42 parameters) for seeds
  20260820/21/22, and identical synthetic batch order.
- Real-row parity on the real cache: 799 train and 171 validation records
  build under the M2.4 contract (386,390 and 82,255 candidate rows, at most
  579 per record).
- For each of the three seeds, QARF and QPAF receive the same 1,000 training
  batches (20 epochs), with identical query IDs in identical order.

The real-row check replays the trainer's own seeded `torch.Generator` through
`iter_batches`. It runs no forward or backward pass, so **no model is trained**
before D1. Test qrels are hashed but not opened.

The file is create-once, produced by
`python scripts/verify_m27_binding.py --output evidence/revisions/m2.7-003/verification.json`
from committed code. The Parquet inputs must be present locally (see M2.8-002).
Independent review: `PENDING`.
