# Oracle Study for QPAF and Budget-Aware HEAVEN

Package này triển khai phần **oracle analysis** của hai hướng nghiên cứu:

- QPAF: so sánh query-level fusion với candidate-conditioned fusion.
- Budget-Aware HEAVEN: đo quality–Stage-2-invocation Pareto frontier.

Package không train router/gate và không thay thế official HEAVEN retrieval. Score DSE,
ColQwen2.5, BM25 và BGE-M3 phải được tạo trong môi trường cloud/GPU rồi xuất theo
raw-score contract bên dưới. `sources/` không bị chỉnh sửa.

## Pilot ngắn ViDoRe V3 Finance EN

Notebook [vidore_v3_short_oracle.ipynb](notebooks/vidore_v3_short_oracle.ipynb) là
artifact Colab tự chứa cho feasibility pilot đã đăng ký trước:

- dataset `vidore/vidore_v3_finance_en` tại revision
  `7f432c176d82e27546501ad8064a713ac3071809`;
- toàn bộ 309 query tiếng Anh và 2.942 trang;
- Global Fusion, QARF và constrained QPAF với `W7`;
- candidate pool `DSE Top200 ∪ BM25 Top100 ∪ BGE Top100`, mở rộng đúng một lần khi
  coverage dưới 95%;
- paired bootstrap 2.000 lần và feasibility report cho riêng hai bước
  `Global → QARF` và `QARF → QPAF`.

Cách chạy:

1. Tải notebook lên Google Colab và chọn A100 hoặc GPU có ít nhất 24 GB VRAM.
2. Chạy lần lượt mọi cell và cấp quyền mount Google Drive.
3. Nếu runtime bị ngắt, mở lại và chạy từ đầu; embedding/score checkpoint trong
   `MyDrive/vidore_v3_finance_en_short_oracle/cache` sẽ được dùng lại.
4. Đọc kết quả tại thư mục `output`, đặc biệt là `pilot_feasibility.md`,
   `fusion_oracle_summary.json` và `global_qarf_qpaf_oracle.png`.

Notebook dừng thay vì kết luận nếu GPU dưới 24 GB hoặc candidate coverage vẫn dưới 95%.
Khi OOM, nó chỉ hạ batch size trong danh sách đã đóng băng; model và candidate pool
không bị thay đổi. File nguồn sinh notebook là
`notebooks/build_vidore_v3_short_oracle.py`; chạy lại file này sau khi sửa lõi oracle
để cập nhật phần implementation được nhúng vào notebook.

### Chạy trên Kaggle

Dùng [vidore_v3_short_oracle_kaggle.ipynb](notebooks/vidore_v3_short_oracle_kaggle.ipynb):

1. Tạo Kaggle Notebook, chọn **File → Import Notebook** và tải file `.ipynb` lên.
2. Bật **Internet** và chọn GPU có ít nhất 24 GB VRAM. P100/T4 16 GB sẽ bị preflight
   từ chối để không làm thay đổi protocol.
3. Chạy toàn bộ cell bằng **Save Version → Save & Run All**. Artifact cuối được ghi vào
   `/kaggle/working`; model và embedding cache lớn nằm trong `/kaggle/temp` để không làm
   Kaggle Output vượt dung lượng.
4. Chỉ xem run là hoàn tất khi `_SUCCESS.json` xuất hiện. Cell cuối kiểm tra đủ mười
   artifact bắt buộc, ghi SHA-256, tạo `artifact_manifest.json` và đóng gói
   `vidore_v3_finance_en_short_oracle_results.zip`.

Các file dễ đọc được đặt ngay ở Kaggle Output:

- `PILOT_FEASIBILITY.md` — kết luận feasibility cho Global → QARF và QARF → QPAF;
- `global_qarf_qpaf_oracle.png` — biểu đồ so sánh ba tầng;
- `fusion_oracle_summary.json` — metric tổng hợp;
- `README_RESULTS.md` — hướng dẫn đọc artifact;
- `_SUCCESS.json` — completion marker và hash của ZIP;
- `vidore_v3_finance_en_short_oracle_results.zip` — toàn bộ artifact đầy đủ.

Nếu đã lưu cache từ một lần chạy trước thành Kaggle Dataset với slug
`vidore-v3-short-oracle-cache`, attach dataset đó vào notebook. Notebook ưu tiên checkpoint
tạm của run hiện tại, sau đó mới đọc cache bất biến từ `/kaggle/input`.
File sinh phiên bản Kaggle là `notebooks/build_vidore_v3_short_oracle_kaggle.py`.

## 1. Cài đặt

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## 2. Raw-score contract

Mỗi hàng tương ứng một `(dataset, query_id, page_id)` và phải có:

```text
dataset, query_id, page_id, source, relevance,
bm25_score, dense_score, stage1_score, visual_score, full_score,
stage2_ms, stage2_flops
```

- Candidate construction chỉ dùng branch scores/ranks; `relevance` chỉ dùng để đo coverage.
- Raw table phải chứa đủ scored pages để hình thành ít nhất union Top300/Top200/Top200
  và phải chứa relevant pages để audit coverage.
- `stage1_score` là output HEAVEN Stage 1.
- `visual_score` là ColQwen2.5 score dùng cho QPAF.
- `full_score` là final HEAVEN Stage 1 + Stage 2 score.
- Latency dùng CUDA event sau 50 warm-up query, median ba lượt cùng query order.

Official HEAVEN configuration:

```text
stage1_model=dse, stage2_model=colqwen25,
reduction_factor=15, alpha=0.1, filter_ratio_stage1=0.5,
k=200, filter_ratio_stage2=0.25, beta=0.3
```

Trong official repository, Stage 1 score được cache bởi `heaven.py`; khi chạy cloud,
export `stage1_scores` và `final_scores` ngay trước lời gọi `evaluate(...)`, đồng thời
export BM25/BGE-M3/ColQwen2.5 score theo page mapping. Không dùng qrels để thêm page
vào candidate union.

Lưu ý kỹ thuật: `Stage2Retrieval.filter_and_combine()` của upstream mask score tensor tại
chỗ. Vì vậy raw ColQwen2.5 score cho QPAF phải được snapshot trước lời gọi này; chi tiết
hook nằm trong `docs/heaven_export_contract.md`.

Với benchmark thật, nên export thêm `official_query_metrics.parquet` trực tiếp từ
ranking trên **toàn bộ corpus**, theo schema `query_metrics.parquet`. Raw score table
có thể chỉ chứa union candidate và các relevant page dành cho audit; không dùng metric
tính lại trên bảng rút gọn làm kết quả chính.

## 3. Discovery workflow

```powershell
oracle-study manifest --heaven-root D:\HEAVEN `
  --dataset-file D:\data\ViDoSeek\test.json `
  --checkpoint-revision DSE=<revision> `
  --checkpoint-revision ColQwen2.5=<revision> `
  --output runs\discovery\run_manifest.yaml

oracle-study build-cache --raw runs\discovery\raw_scores.parquet `
  --query-metrics runs\discovery\official_query_metrics.parquet `
  --output-dir runs\discovery

oracle-study preflight `
  --scores runs\discovery\retrieval_scores.parquet `
  --metrics runs\discovery\query_metrics.parquet `
  --reference-means runs\discovery\paper_sample_means.json `
  --output runs\discovery\preflight.json

oracle-study qpaf --scores runs\discovery\retrieval_scores.parquet `
  --output-dir runs\discovery\qpaf

oracle-study budget --metrics runs\discovery\query_metrics.parquet `
  --output-dir runs\discovery\budget
```

`build-cache` tự thử candidate pool Top200/100/100, mở rộng đúng một lần thành
Top300/200/200 khi coverage dưới 95%, và dừng bằng lỗi nếu vẫn không đạt.
Nếu bỏ `--query-metrics`, công cụ tính metric từ raw table chỉ để smoke test; report sẽ
ghi rõ `query_metrics_source=raw_score_table`.
`candidate_audit.parquet` ghi riêng từng query thiếu/không có relevant page và từng query
không đạt coverage; `preflight.json` chứa content hash của cả score và metric cache để
đối chiếu hai lần chạy cùng manifest.
Khi metric export có các cột `recall1_*`, `recall3_*`, `mrr10_*`, Budget report cũng giữ
và báo các secondary metric này tại budget được chọn.

## 4. Confirmation workflow

Tạo sample ViMDoc cố định, không nhìn retrieval outcomes:

```powershell
oracle-study sample-vimdoc --queries data\vimdoc_queries.parquet `
  --output runs\confirmation\vimdoc_2000.parquet -n 2000
```

Query table cần `query_id`, `source` và `relevant_count` (khuyến nghị), hoặc `doc_ids`;
sampling được phân tầng theo `source × single/multi relevant page` với seed cố định.

Sau khi chạy lại score/cache/oracle cho hướng vượt Discovery, áp dụng gate cuối:

```powershell
oracle-study decide `
  --qpaf-discovery runs\discovery\qpaf\qpaf_summary.json `
  --qpaf-confirmation runs\confirmation\qpaf\qpaf_summary.json `
  --budget-discovery runs\discovery\budget\budget_summary.json `
  --budget-confirmation runs\confirmation\budget\budget_summary.json `
  --output-dir runs\decision
```

Không truyền summary của hướng không vượt Discovery. Khi thiếu Confirmation, kết luận
sẽ là `inconclusive_do_not_rewrite_proposal`, không tự động coi Discovery là kết quả cuối.

## 5. Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Các test kiểm tra metric tính tay, deterministic tie-break, candidate construction không
dùng relevance, QPAF oracle không thấp hơn QARF, Budget endpoints và sampling cố định.

Ngưỡng đăng ký trước nằm tại `configs/preregistered.yaml`. Quy trình export score chính
xác từ môi trường HEAVEN/GPU nằm tại `docs/heaven_export_contract.md`.
