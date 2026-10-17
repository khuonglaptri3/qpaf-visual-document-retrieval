---
title: "Kế hoạch Oracle Study cho QPAF và Budget-Aware Adaptive HEAVEN"
version: "1.0"
date: "2026-08-21"
language: "vi"
status: "Preregistered plan — chưa có kết quả thực nghiệm chính thức"
seed: 20260820
---

# Kế hoạch Oracle Study cho QPAF và Budget-Aware Adaptive HEAVEN

## 1. Mục tiêu nghiên cứu

Oracle study được thực hiện trước khi huấn luyện QPAF hoặc router nhằm đo phần cải thiện
lý tưởng còn có thể khai thác (*oracle headroom*) của hai hướng nghiên cứu:

1. **QPAF:** candidate-specific weighting có cải thiện đáng kể so với query-level
   weighting hay không?
2. **Budget-Aware Adaptive HEAVEN:** có thể bỏ Stage 2 cho bao nhiêu query mà vẫn giữ
   chất lượng gần bằng full HEAVEN?

Đây chỉ là nghiên cứu về **page retrieval**. Nghiên cứu không huấn luyện router/gate và
không đánh giá answer generation.

## 2. Thiết kế thí nghiệm tổng thể

Thí nghiệm gồm hai vòng:

1. **Discovery:** chạy cả hai oracle trên toàn bộ ViDoSeek.
2. **Confirmation:** chỉ hướng vượt Discovery gate mới được kiểm tra trên 2.000 query
   ViMDoc. Query được lấy mẫu cố định theo `source` và nhóm một/nhiều trang liên quan,
   nhưng retrieval vẫn chạy trên **toàn bộ corpus ViMDoc**.

Implementation chính sử dụng repository chính thức của
[HEAVEN](https://github.com/juyeonnn/HEAVEN) với cấu hình:

| Thành phần | Cấu hình |
|---|---|
| Stage 1 | DSE |
| `reduction_factor` | 15 |
| `alpha` | 0.1 |
| Stage-1 `filter_ratio` | 0.5 |
| Stage 2 | ColQwen2.5 |
| `K` | 200 |
| Stage-2 `filter_ratio` | 0.25 |
| `beta` | 0.3 |
| Seed chung | `20260820` |

### 2.1. Metric

- **Primary:** mean per-query `nDCG@10`.
- **Secondary:** `Recall@1`, `Recall@3`, `MRR@10`.
- **Độ tin cậy:** paired bootstrap 10.000 lần trên query.

## 3. Chuẩn bị dữ liệu và cache dùng chung

### 3.1. Bước 1 — Đóng băng môi trường

Tạo `run_manifest.yaml` và ghi lại:

- commit hash của HEAVEN;
- checkpoint revision của DSE, ColQwen2.5 và BGE-M3;
- phiên bản CUDA, PyTorch và Python;
- GPU, VRAM và driver;
- checksum của dataset, qrels, query/page mapping;
- toàn bộ hyperparameter và seed.

Không thay đổi hyperparameter sau khi xem kết quả test. Chỉ được sửa lỗi tương thích nếu
reproduction thất bại và phải ghi lại thay đổi đó trong manifest.

Trước khi encode toàn bộ corpus, chạy smoke test trên 20 query.

#### Preflight gate

Chỉ được tiếp tục khi:

- không xảy ra OOM trên GPU có ít nhất 24 GB VRAM;
- `query_id`, `page_id` và qrels ánh xạ chính xác 100%;
- hai lần chạy Stage 1 và full HEAVEN sinh cùng ranking/content hash;
- chênh lệch reproduction so với paper/code sample không quá `±0.01` tuyệt đối.

### 3.2. Bước 2 — Tạo bốn tín hiệu retrieval

Với mỗi query, tạo và cache bốn score:

1. BM25 trên OCR của từng page;
2. BGE-M3 single-vector trên cùng OCR;
3. HEAVEN Stage 1/DSE visual score;
4. ColQwen2.5 multi-vector score cho candidate pages.

Candidate pool dùng chung cho QPAF:

$$
C_q = Top200_{\text{HEAVEN-S1}}
\cup Top100_{\text{BM25}}
\cup Top100_{\text{BGE}}.
$$

Sau khi deduplicate, tính đủ BM25, BGE-M3 và ColQwen2.5 score cho mọi
$p \in C_q$. Candidate construction tuyệt đối không được sử dụng qrels.

#### Candidate-coverage gate

- Nếu recall của relevant pages trong $C_q$ đạt ít nhất 95%: tiếp tục.
- Nếu thấp hơn: tăng đúng một lần thành
  `Top300 Stage 1 + Top200 BM25 + Top200 BGE`.
- Nếu vẫn dưới 95%: dừng QPAF oracle. Khi đó candidate generation là bottleneck nên
  không được diễn giải kết quả như fusion headroom.

Mọi query thiếu qrel, thiếu candidate hoặc không đạt coverage phải được ghi riêng; không
được âm thầm loại bỏ.

### 3.3. Bước 3 — Chuẩn hóa và lưu artifact

Thực hiện min–max normalization riêng cho từng query và từng retriever trên $C_q$:

$$
\hat{s}_{r}(q,p)=
\frac{s_r(q,p)-\min_{p'\in C_q}s_r(q,p')}
{\max_{p'\in C_q}s_r(q,p')-\min_{p'\in C_q}s_r(q,p')}.
$$

Nếu toàn bộ score của một branch bằng nhau, đặt score chuẩn hóa của branch đó bằng 0.

Hai interface ổn định:

#### `retrieval_scores.parquet`

```text
dataset, query_id, page_id, relevance,
bm25_score, dense_score, stage1_score, visual_score,
branch_ranks, source
```

#### `query_metrics.parquet`

```text
dataset, query_id, source, relevant_count,
ndcg_stage1, ndcg_full,
recall_stage1, recall_full,
stage1_margin, stage2_ms, stage2_flops,
recall1_stage1, recall1_full,
recall3_stage1, recall3_full,
mrr10_stage1, mrr10_full
```

Embedding và score chỉ được tính một lần. Hai oracle chỉ đọc cache, không chạy lại
retriever.

## 4. Oracle Study A — QPAF

### 4.1. A1 — QARF query-level oracle

Profile set chính:

$$
W_7 = \left\{
(1,0,0),(0,1,0),(0,0,1),
(0.5,0.5,0),(0.5,0,0.5),(0,0.5,0.5),
(1/3,1/3,1/3)
\right\}.
$$

Với mỗi query và profile $w=(w_B,w_D,w_V)$:

$$
S_w(q,p)=w_BS_B(q,p)+w_DS_D(q,p)+w_VS_V(q,p).
$$

Chọn một profile duy nhất cho toàn bộ pages:

$$
w_q^*=\arg\max_{w\in W_7}nDCG@10(q,w).
$$

Tie-break theo thứ tự:

1. `Recall@3`;
2. `MRR@10`;
3. thứ tự profile cố định trong $W_7$.

Kết quả này được gọi là **QARF-7 Oracle**.

Sensitivity analysis sử dụng:

$$
W_{66}=\{(a,b,c):a+b+c=1;\ a,b,c\in\{0,0.1,\ldots,1\}\}.
$$

### 4.2. A2 — Constrained QPAF oracle

Với từng query:

1. Khởi tạo mọi page bằng $w_q^*$ của QARF oracle.
2. Duyệt candidate theo QARF rank, rồi theo `page_id`.
3. Với từng page $p$, thử từng profile trong cùng weight set trong khi giữ profile của
   các page khác cố định.
4. Chỉ chấp nhận thay đổi nếu whole-query `nDCG@10` tăng.
5. Nếu hòa, giữ profile hiện tại.
6. Lặp tối đa hai sweep hoặc dừng sớm nếu không còn thay đổi.

Kết quả:

$$
w_{q,p}^* \quad\text{và}\quad nDCG_{\text{QPAF-oracle}}.
$$

Chạy cả $W_7$ và $W_{66}$. Qrels chỉ được dùng trong oracle selection; đây không phải
một model có thể deploy.

### 4.3. A3 — Phân tích QPAF

Báo cáo:

- $\Delta nDCG=nDCG_{\text{QPAF}}-nDCG_{\text{QARF}}$;
- tỷ lệ query tăng ít nhất `0.01`, `0.03`, `0.05`;
- paired-bootstrap 95% CI của mean gain;
- gain theo `source`;
- gain theo query có một hoặc nhiều relevant pages;
- số candidate thực sự đổi profile;
- phân bố profile BM25/Dense/Visual được chọn;
- tỷ trọng tổng gain do top 5% query tạo ra;
- so sánh $W_7$ với $W_{66}$.

### 4.4. A4 — QPAF decision gate

**GO QPAF** khi đồng thời:

- Discovery mean $\Delta nDCG@10 \ge 0.03$;
- Confirmation mean $\Delta nDCG@10 \ge 0.02$;
- lower bound của paired-bootstrap 95% CI lớn hơn 0;
- ít nhất 20% Confirmation query tăng từ `0.05` trở lên;
- toàn bộ kết luận trên giữ nguyên với cả $W_7$ và $W_{66}$.

**NO-GO QPAF** nếu:

- Confirmation mean gain dưới `0.01`; hoặc
- top 5% query tạo ra ít nhất 90% tổng positive gain.

Các trường hợp còn lại là **inconclusive**.

## 5. Oracle Study B — Budget-Aware Adaptive HEAVEN

### 5.1. B1 — Hai action cho mỗi query

- Cheap action $a_0$: HEAVEN Stage 1 only.
- Expensive action $a_1$: full HEAVEN Stage 1 + Stage 2.

Với mỗi query:

$$
M_0(q)=nDCG@10(a_0,q),
$$

$$
M_1(q)=nDCG@10(a_1,q),
$$

$$
\Delta(q)=M_1(q)-M_0(q).
$$

Chi phí tăng thêm:

$$
\Delta C(q)=C_1(q)-C_0(q).
$$

Chi phí phải gồm Stage-2 invocation, CUDA-event latency và FLOPs. Trước khi đo latency:

1. chạy 50 warm-up query;
2. chạy ba lượt với cùng query order;
3. đồng bộ CUDA event;
4. lấy median latency theo từng query.

### 5.2. B2 — Oracle quality–budget curve

Invocation budget:

$$
B\in\{0,5,10,\ldots,100\}\%.
$$

Sắp query theo $\Delta(q)$ giảm dần và chỉ escalate top-$B\%$. Đây là invocation oracle.

Các đường so sánh:

- **Cheap-only:** $B=0\%$;
- **Always-expensive:** $B=100\%$;
- **Random:** trung bình 100 seed tại cùng budget;
- **Stage-1 margin:** escalate query có margin Top1–Top2 thấp nhất;
- **Oracle:** escalate theo ground-truth gain.

Tìm budget nhỏ nhất $B^*$ thỏa cả hai:

$$
M_{\text{oracle}}(B^*)\ge M_{\text{full}}-0.01,
$$

$$
\frac{M_{\text{oracle}}(B^*)}{M_{\text{full}}}\ge0.98.
$$

Ngoài invocation curve, vẽ quality theo cumulative Stage-2 latency và FLOPs bằng cách
sắp theo $\Delta(q)/\Delta C(q)$.

### 5.3. B3 — Kiểm tra routing headroom

Định nghĩa:

- `beneficial`: $\Delta(q)>0.01$;
- `non-beneficial`: $\Delta(q)\le0.01$.

Nếu gần như mọi query thuộc cùng một nhóm thì routing không phải research problem tốt:

- hầu hết beneficial: nên luôn chạy Stage 2;
- hầu hết non-beneficial: Stage 1 đã đủ, không cần router.

### 5.4. B4 — Budget-Aware decision gate

**GO Budget-Aware** khi đồng thời trên Discovery và Confirmation:

- full HEAVEN hơn Stage 1 ít nhất `0.02 nDCG@10`;
- beneficial và non-beneficial đều chiếm ít nhất 20% query;
- $B^*\le50\%$;
- oracle tại $B^*$ hơn random và margin heuristic ít nhất `0.01 nDCG@10`;
- lower bound của 95% CI cho quality retention đạt ít nhất 98%.

**NO-GO Budget-Aware** nếu:

- full HEAVEN hơn Stage 1 dưới `0.01`; hoặc
- cần trên 70% query chạy Stage 2 để đạt quality retention 98%.

Các trường hợp còn lại là **inconclusive**.

## 6. Trình tự thực thi

1. Đóng băng manifest, qrels và metric implementation.
2. Chạy 20-query smoke test.
3. Encode và tính score ViDoSeek đúng một lần.
4. Build và kiểm tra cache dùng chung.
5. Chạy QPAF oracle và Budget-Aware oracle.
6. Áp dụng Discovery gate, không thay threshold sau khi xem kết quả.
7. Chỉ hướng đạt Discovery GO mới được chạy trên 2.000-query ViMDoc.
8. Chạy paired bootstrap, subgroup analysis và tạo decision memo.
9. Ra quyết định cuối.

### 6.1. Quy tắc quyết định cuối

| QPAF | Budget-Aware | Quyết định |
|---|---|---|
| GO | Không GO | Chọn QPAF |
| Không GO | GO | Chọn Budget-Aware Adaptive HEAVEN |
| GO | GO | Ưu tiên Budget-Aware; giữ QPAF làm follow-up |
| Không GO | Không GO | Không sửa proposal theo hai hướng này |
| Inconclusive | Bất kỳ | Chưa đổi proposal nếu chưa có một hướng GO rõ ràng |

## 7. Lệnh chạy tham chiếu

### 7.1. Discovery

```powershell
oracle-study manifest --heaven-root D:\HEAVEN `
  --dataset-file D:\data\ViDoSeek\test.json `
  --checkpoint-revision DSE=<revision> `
  --checkpoint-revision ColQwen2.5=<revision> `
  --output runs\discovery\run_manifest.yaml

oracle-study build-cache `
  --raw runs\discovery\raw_scores.parquet `
  --query-metrics runs\discovery\official_query_metrics.parquet `
  --output-dir runs\discovery

oracle-study preflight `
  --scores runs\discovery\retrieval_scores.parquet `
  --metrics runs\discovery\query_metrics.parquet `
  --reference-means runs\discovery\paper_sample_means.json `
  --output runs\discovery\preflight.json

oracle-study qpaf `
  --scores runs\discovery\retrieval_scores.parquet `
  --output-dir runs\discovery\qpaf

oracle-study budget `
  --metrics runs\discovery\query_metrics.parquet `
  --output-dir runs\discovery\budget
```

### 7.2. Confirmation

```powershell
oracle-study sample-vimdoc `
  --queries data\vimdoc_queries.parquet `
  --output runs\confirmation\vimdoc_2000.parquet `
  -n 2000
```

Sau khi chạy oracle trên sample Confirmation:

```powershell
oracle-study decide `
  --qpaf-discovery runs\discovery\qpaf\qpaf_summary.json `
  --qpaf-confirmation runs\confirmation\qpaf\qpaf_summary.json `
  --budget-discovery runs\discovery\budget\budget_summary.json `
  --budget-confirmation runs\confirmation\budget\budget_summary.json `
  --output-dir runs\decision
```

Không truyền Confirmation summary của hướng không vượt Discovery.

## 8. Kiểm thử bắt buộc

- Metric unit test bằng ranking nhỏ tính tay.
- Deterministic tie-break theo `page_id`.
- Candidate dedup không làm mất relevant page.
- Qrels không tham gia candidate construction hoặc score normalization.
- QPAF oracle không thấp hơn QARF oracle với cùng weight set.
- Fast QPAF update phải khớp brute-force reranking.
- Budget oracle tại 0% bằng Stage 1.
- Budget oracle tại 100% bằng full HEAVEN.
- Cùng manifest và seed sinh cùng content hash và oracle decision.
- Ngưỡng runtime phải khớp file preregistration.
- Query thiếu qrel/candidate phải được báo riêng.
- Chạy end-to-end synthetic test từ raw cache đến JSONL và biểu đồ.

## 9. Deliverable

- `run_manifest.yaml` đã đóng băng;
- `retrieval_scores.parquet`;
- `query_metrics.parquet`;
- `candidate_audit.parquet`;
- `coverage_report.json`;
- `preflight.json`;
- `qpaf_oracle_results.jsonl`;
- `qpaf_summary.json`;
- `budget_oracle_results.jsonl`;
- `budget_summary.json`;
- biểu đồ QARF-vs-QPAF oracle gain;
- biểu đồ quality-vs-Stage-2 invocation;
- biểu đồ quality-vs-latency/FLOPs;
- `decision_memo.md` kết luận bằng đúng threshold đã đăng ký trước.

## 10. Assumption và giới hạn

- Đây là oracle study, chưa train QPAF gate hoặc Budget-Aware router.
- Chỉ đánh giá page retrieval, không đánh giá answer generation.
- ViDoRe V3 và benchmark Việt chỉ được thêm sau khi đã chọn hướng.
- Không mở rộng oracle ban đầu trước khi hoàn tất Discovery.
- Không sửa proposal trước khi hoàn tất Confirmation gate.
- Trạng thái `pilot_v0` ngày 02/08/2026 từng được ghi nhận là chưa
  `experiment_ready`; phải kiểm tra lại trạng thái hiện tại trước khi sử dụng.
- Kết quả trên raw candidate table chỉ dùng cho smoke test. Kết quả chính phải sử dụng
  full-corpus ranking và `official_query_metrics.parquet`.

## 11. Trạng thái triển khai tại thời điểm tạo tài liệu

| Hạng mục | Trạng thái |
|---|---|
| Oracle-analysis package và CLI | Đã triển khai |
| QARF/QPAF $W_7$, $W_{66}$ | Đã triển khai |
| Budget invocation, latency và FLOPs curves | Đã triển khai |
| Bootstrap, subgroup và decision gates | Đã triển khai |
| Preflight, manifest, coverage audit | Đã triển khai |
| Unit/end-to-end synthetic tests | 18/18 đạt |
| ViDoSeek Discovery run thật | Chưa chạy |
| ViMDoc Confirmation run thật | Chưa chạy |
| GO/NO-GO chính thức | Chưa có |

Không được diễn giải trạng thái “đã triển khai” của pipeline thành kết quả nghiên cứu.
