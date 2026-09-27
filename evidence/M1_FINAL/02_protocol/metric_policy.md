# Metric Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1`  
> **Evaluation scope:** ViMDoc document retrieval  
> **Execution:** Closed

## 1. Evaluation unit

QARF/QPAF fuse scores ở page level. ViMDoc được evaluate ở **document level**:

1. map page ID sang HEAVEN document ID bằng cách bỏ segment cuối sau `_`;
2. sort page ID tăng dần để có deterministic tie behavior;
3. document score bằng max fused page score;
4. rank document theo score giảm dần, tie-break bằng ascending document ID;
5. IDCG dùng toàn bộ relevant documents của query, kể cả relevant document nằm ngoài
   candidate union.

Binary document qrels được giữ riêng; không nhân document label xuống pages.

## 2. Primary và secondary metrics

| Loại | Metric | Aggregation |
|---|---|---|
| Primary | `document nDCG@10` | Mean per query, equal query weight |
| Secondary | `Recall@1` | Mean per query |
| Secondary | `Recall@3` | Mean per query |
| Secondary | `MRR@10` | Mean per query |

Không thêm hoặc thay `k` sau khi thấy kết quả. Metric mới cần protocol amendment.
Metric implementation phải khớp repository fixtures với absolute tolerance `1e-12`.
Canonical registry/config token cho primary metric là `document_ndcg_at_10`.

## 3. Metric definitions

- Gain: `2^relevance - 1`.
- Discount tại one-based rank `i`: `1 / log2(i + 1)`.
- `nDCG@10 = DCG@10 / IDCG@10`; bằng 0 khi IDCG bằng 0.
- `Recall@k = số positive relevant units trong top-k / tổng positive relevant units`.
- `MRR@10` là reciprocal rank của positive unit đầu tiên trong top 10; bằng 0 nếu
  không có.
- Ranking luôn score descending rồi evaluation-unit ID ascending.

## 4. Primary comparisons

Hai paired comparisons bắt buộc:

1. learned QPAF minus matched learned QARF;
2. learned QPAF minus mọi co-strongest deployable baseline được xác định trước khi
   mở confirmation labels.

Positive quality threshold cho core claim:

- mean paired nDCG@10 delta `>= 0.01`; và
- query-bootstrap CI95 lower bound `> 0`; và
- QPAF vượt strongest deployable baseline(s).

Secondary metrics giải thích tradeoff; không được dùng post-hoc để cứu một primary
metric failure.

## 5. Operational gates

| Gate | Rule |
|---|---|
| Finite values | Không NaN/Inf trong score, loss, gradient, prediction hoặc metric |
| Latency | 20 warm-up queries; ít nhất 1.000 label-free measured queries; median added fusion latency `<= 10.0 ms/query` |
| Memory | Peak learned-fusion CUDA allocation `< 1.50 GiB`, tách khỏi retriever extraction |
| Reload parity | Fresh-process checkpoint reload tái tạo fused scores với absolute difference `<= 1e-7` |

Feature preprocessing, gate/fusion và document aggregation latency phải được báo riêng.

## 6. Required reporting

Mỗi method/seed phải lưu aggregate metrics, per-query metrics, exact query count,
prediction/ranking artifact và hashes. Final report phải tách rõ:

- oracle upper bound;
- learned development;
- untouched confirmation;
- sealed external evidence;
- operational measurements.

Không được điền estimate vào result table. Chưa đo thì ghi `NOT_RUN` và lý do.
Registry event phải ghi `primary_metric`, `primary_metric_value`, `metrics_path`,
`output_sha256`, protocol/config hashes và exact `result_claim_scope`.
