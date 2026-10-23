# M4.1 — ViMDoc confirmation ID and access seal

**Owner:** Thanh. **G2 prerequisite:** confirmed `GO` / `continue_qpaf` in
`evidence/revisions/m3.7-001`. **Seal status:** `ID_SPLITS_SEALED_CONFIRMATION_ACCESS_CLOSED`.
This revision freezes exact query IDs and the access/evaluation contract. It
does not authorize a confirmation evaluation or a training run.

## Source and split

The source is the public ViMDoc query Parquet at revision
`25657f1fe0358f49147148ca89e231291ba42788`, SHA-256
`7ccac6c8715cc338c041e9276583b79a818131a9b13a5abf4b9ced73bcc0`.
The source bytes match the historical materialization receipt. The seal reads
**only** its Parquet `id` column. It does not deserialize query text,
`doc_ids`, qrels or retrieval scores; the source Parquet itself is not
committed. The receipt's historical document-qrels hash is recorded in
[`manifest.json`](manifest.json) as provenance, not revalidated from labels.

The frozen SHA-256 order over `20260820:<query_id>` reproduces the historical
2,000-ID development sample byte-for-byte (hash `0fc5a2f0…a3482a`). The
frozen `vimdoc_m3_local_v1:dev_split:20260820` namespace divides that sample
into train and validation. Confirmation is the 8,904 IDs after the first
2,000 in the same full-universe hash order. All files are UTF-8, one ID per
line, with a final newline. The three groups are disjoint and their union is
all 10,904 source IDs.

| File | IDs | SHA-256 |
| --- | ---: | --- |
| [`train_ids.txt`](train_ids.txt) | 1,600 | `970a9f9c71d9e307c6ecc9c12f1620816de0b568aeaf016964f0aa48176ae26e` |
| [`validation_ids.txt`](validation_ids.txt) | 400 | `cd31064b91d1c977d09d61b98ff3d3e886ba7a338b03b76e8490b331b90ba330` |
| [`confirmation_ids.txt`](confirmation_ids.txt) | 8,904 | `4dd15fb9996eee00439633f07cb3fb0fa87a1a2b217468e532d605fc0e7520ac` |

[`manifest.json`](manifest.json) binds the dataset receipt, confirmed G2
decision, these files, and eight frozen policy hashes. It freezes the document
evaluation unit, page-to-document mapping, score aggregation, tie break,
primary metric and paired three-seed bootstrap contract. It also states the
method/seed/checkpoint selection rule and the required future baseline
selection evidence. The proposed checkpoint-selection rule is recorded for
traceability, but it has not been adopted for a ViMDoc execution.

## Access gate

Only the ID-only seal is open now. Confirmation labels, predictions and
metrics remain unopened. Project use of the confirmation split requires:

1. Verified ViMDoc score/candidate data and document-qrels contract.
2. Matched, independently reviewed QARF/QPAF configs and checkpoints for all
   three seeds; the current ViDoSeek pilot checkpoints do not substitute for
   ViMDoc checkpoints.
3. A verified ViMDoc evaluation implementation hash and the full deployable
   baseline validation/selection artifact, including every co-strongest row.
4. Separate result-bearing authorization before the first confirmation run.

The historical `vimdoc_m3_local_v1` package is still a preparation proposal.
Its method config is hash-bound as context, while adoption, checkpoint hashes,
evaluation implementation hash and selected baseline IDs remain explicitly
`PENDING` in the manifest. G2 `GO` permits requests for M4 authorization; it
is not such an authorization. This seal does not claim M4.3/M4.4 completion or
a three-seed scientific result.
The required document-overlap analysis also remains pending until authorized
access to the relevant document IDs.

## Replay

Download the pinned public Parquet from
[`data/ViMDoc-00000-of-00001.parquet`](https://huggingface.co/datasets/kaistdata/ViMDoc/resolve/25657f1fe0358f49147148ca89e231291ba42788/data/ViMDoc-00000-of-00001.parquet),
verify its source SHA-256, then run with PyArrow available:

```powershell
python scripts/seal_m41_confirmation.py --source-parquet <verified-parquet> --output-dir evidence/revisions/m4.1-001 --verify
```

The verifier is read-only and rejects a changed source, receipt, G2 record,
policy byte, query ID or output file. Creation omits `--verify` and requires a
new output directory. No Modal/GPU job is needed for this ID-only seal.
