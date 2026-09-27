# Candidate and Score Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1_DATA_NOT_READY`  
> **Execution:** Closed

## 1. Retrieval channels

Candidate generation dùng đúng ba frozen channels:

1. BM25 trên approved OCR/text;
2. BGE-M3 dense-text retrieval;
3. ColQwen2.5 visual page retrieval.

DSE/HEAVEN historical artifacts không được thay thế BGE-M3/BM25/ColQwen2.5 contract
cho learned ViMDoc study.

## 2. Candidate construction

Cho từng query:

1. rank riêng từng channel theo raw score giảm dần, tie theo ascending page ID;
2. lấy top 200 pages của mỗi channel;
3. union theo page ID;
4. deterministic output order là ascending page ID;
5. vì có ba channel × 200, union tối đa 600 pages/query;
6. tính/giữ đủ cả ba raw scores cho mọi page trong union.

Candidate construction không được đọc qrels, relevance, oracle profiles, split outcome
metrics hoặc learned predictions.

## 3. Score and normalization contract

- Raw score cache: finite `float64`, lưu riêng từng channel.
- Normalization: per query, per channel, trên frozen union.
- Nếu `max - min > 1e-15`, dùng `(score - min) / (max - min)`.
- Nếu range `<= 1e-15`, normalized score của channel bằng exact `0.0`.
- Reject missing/non-finite score; không impute bằng 0 hoặc channel mean.
- Normalized cache giữ `float64`; model input cast explicit sang `float32` và phải có
  parity tolerance/check.
- Normalized rank: best = 1, worst = 0; equal-score ties theo ascending page ID.

## 4. Coverage gate

Qrels chỉ được join **sau** candidate freeze để audit/evaluate. Data-readiness PASS cần:

- macro relevant-document recall `>= 0.95`;
- zero queries without a positive candidate;
- không drop uncovered query;
- candidate count, union provenance và channel-rank permutations verify;
- page → document mapping và all-document IDCG contract verify.

Fail coverage là `BLOCKED`, không phải lý do để inject relevant pages, đổi top-k sau
khi xem labels hoặc làm sạch query set.

## 5. Required candidate artifacts

- channel top-list manifests và hashes;
- union candidate table với `(split, query_id, page_id)` unique key;
- raw score table và normalized score table;
- candidate provenance/rank columns;
- document mapping and qrels table stored separately;
- coverage report;
- source dataset/retriever/config/commit hashes;
- independent integrity review.

M1.7 registry phải ghi human-readable `candidate_definition` và exact
`candidate_sha256`. Hash này định danh candidate artifact/manifest đã freeze; không
được dùng config hash hoặc coverage-report hash thay thế.

Real ViMDoc candidate/cache artifacts chưa tồn tại ở trạng thái verified. File này
freeze candidate/score semantics, không chứng minh data readiness.
