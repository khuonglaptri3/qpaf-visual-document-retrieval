# Parallel investigation provenance

Date: 2026-10-31. Research only, read-only agents. No training, downloads of corpora/models, cloud compute or sealed-label inspection.

- /root/fusion_primary_literature: gpt-6.1-sol, high reasoning, isolated context. Checked adaptive-fusion
  literature, fixed-fusion controls, page-aware precedent, and distinctions between inference/training weighting.
- /root/fusion_benchmark_evidence: gpt-6.1-sol, high reasoning, isolated context. Checked author dataset cards,
  benchmark protocols, counts, grouping and access constraints.
- Executor: local proposal/code/oracle audit, direct cross-check of core external sources, mathematical example,
  source ledger, synthesis and validation.

Integration corrections:
- mFAR/DAT support query adaptation; neither proves page adaptation.
- Unveil weights training instances; ViDoRAG changes retrieval depth. Neither is per-page score weighting.
- DRAG is a page-layout weighting heuristic, so page-conditioned fusion is not automatically a novel claim.
- MMDocIR release has 1,658 eval questions; old abstract counts and Hub train naming are misleading.
- UniDoc modality reversal is measured with different models/metric and is not a QPAF experiment.
- Local finance materialization is not proof of tuning, nor proof that labels remain unexposed; audit before reuse.
