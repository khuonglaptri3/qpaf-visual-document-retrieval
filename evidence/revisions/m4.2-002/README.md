# M4.2 — Active-primary baseline inputs and train-only fit

Owner: Khương. Scope: approved A002 ViDoSeek active primary, page evaluation.
Technical deliverable complete; owner acceptance remains pending user review.

All seven required baselines bind the exact M3.1 expanded candidate/cache
identities. Static weights fitted on 799 train queries are `[0.0, 0.1, 0.9]`
in BM25/BGE-M3/ColQwen2.5 order; train nDCG@10 is `0.8642244283102866`.
RRF remains fixed at k=60. Independent 66-point replay selected identical
weights, with objective difference 3.33e-16.

Run: `results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01`.
Manifest SHA-256:
`4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86`.
Source commit: `363db3f18252a794c5edd9cec4803e1fecccbf83`.

`authorization.json` and `invocation.json` record the user instruction and single
CPU calibration invocation. `execution_receipt.json` records the stdout encoding
error AFTER complete outputs and `_SUCCESS.json` were written. No fit attempt
was repeated. UTF-8 read-only verification passed.

`verification.json` contains real input/fit/replay evidence. `delivery.json`
locates the complete local ZIP, including ignored score/checkpoint payloads.
No test labels, ViMDoc confirmation access, GPU/cloud work or learned training
was performed. Future ViMDoc prerequisites remain pending separately.

45 related tests pass. Full suite has 29 historical/environment failures,
reproduced on the clean base. Sources and details are in the
[completion report](../../../Bao_cao_tien_do/M4_2_Khuong.md).
