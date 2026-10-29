# Feature Lab — tìm thay đổi kiến trúc giúp QARF/QPAF tốt nhất

Lập ngày 30/10/2026, sau A005/A005-R1. Mục tiêu: **hai thành viên chạy song song bốn feature trên cùng một
harness**, rồi so sánh kết quả để chốt kiến trúc cuối nhanh nhất có thể.

| Feature | Plan | Người chạy (đề xuất) | Ý tưởng một dòng | Nâng chủ yếu |
| --- | --- | --- | --- | --- |
| F1 | [Feature nội dung](F1_content_features.md) | A | Gate được biết OCR rỗng/dày số liệu, loại câu hỏi, độ phủ từ query trong trang | QPAF |
| F2 | [Hiệu chỉnh điểm](F2_score_calibration.md) | A | Biến đổi đơn điệu học được thay min-max cố định, có thêm kênh rank kiểu RRF | cả hai |
| F3 | [Objective xếp hạng](F3_ranking_objective.md) | B | ApproxNDCG@10, học trên top-k + query khó, gộp document mềm | cả hai |
| F4 | [Embedding query](F4_query_embedding.md) | B | Embedding BGE-M3 của query vào gate (kiểu mFAR/DAT) | QARF |

Gợi ý người A là **Thanh**, vì F1 cần OCR ViMDoc trên Modal workspace `tranthanhzt123321`. Người B là **Khương**.
Research Lead (Tấn Phát) chốt luật giữ/bỏ (mục 6) trước khi chạy và làm bước ghép (mục 7).

## 1. Vì sao kết quả hiện tại nhỏ

Harness này chạy lại baseline của A005-R1 bằng CV 5-fold trên dev pool. Đây là hàng `baseline` bên dưới (1 seed,
nDCG@10, delta có CI95 bootstrap theo query và W/T/L):

| Dataset (dev pool) | static | QARF-SA | QPAF-SA | QARF − static | QPAF − static | QPAF − QARF |
| --- | ---: | ---: | ---: | --- | --- | --- |
| ViMDoc (2.000 query, đơn vị document) | 0,9586 | 0,9611 | 0,9613 | +0,0025 [+0,0000, +0,0051] 43/1931/26 | +0,0027 [−0,0002, +0,0058] 49/1911/40 | +0,0002 [−0,0027, +0,0032] |
| ViDoSeek (970 query, đơn vị trang) | 0,8655 | 0,8657 | 0,8609 | +0,0003 [−0,0027, +0,0032] 23/925/22 | **−0,0046 [−0,0081, −0,0010]** 20/910/40 | **−0,0049 [−0,0096, −0,0002]** |

Trên ViMDoc, các số này khớp với confirmation của A005-R1 (0,9589 / 0,9614 / 0,9616), nên harness tái tạo đúng
phương pháp cũ. Từ số liệu và code có thể rút ra bốn điểm:

1. **Gate không có thông tin mới.** 12/13 input ([features.py](../../src/qpaf/m12/features.py)) được tính từ chính ba
   điểm đang trộn. Gate theo trang vì vậy chỉ "uốn" lại ba con số đó. Trên ViDoSeek, cách này còn **làm hại**
   (QPAF thua static có ý nghĩa), trong khi oracle cho thấy chọn kênh đúng theo trang có headroom +0,05. Thứ còn
   thiếu là tín hiệu cho biết *vì sao* một trang cần kênh khác. → **F1**, và **F4** ở phía query.
2. **Thang điểm bị méo trước khi trộn.** Min-max trên union khoảng 470 trang làm vùng top bị nén, mỗi kênh một
   kiểu. → **F2**.
3. **Loss dồn vào query đã đúng.** 95% query ViMDoc đã hòa, metric chỉ đổi ở vùng top-10 của số ít query khó. → **F3**.
4. **Đánh giá cũ nhiễu.** Validation chỉ có 400/171 query và lại chọn epoch trên đó. Lab dùng CV trên toàn dev
   pool, không chọn epoch, nên mỗi so sánh có 2.000/970 query ghép cặp.

Ngoài phạm vi lab: thêm kênh thứ tư hoặc reranker (cần GPU, chậm), và CARF. Chỉ cân nhắc sau khi có kết quả lab.

## 2. Protocol chung (mọi người phải giống nhau)

| Mục | Quy định |
| --- | --- |
| Dữ liệu | Chỉ **dev pool**: ViMDoc train + validation (2.000 query, M4.1), ViDoSeek train + validation (970 query, M2.1). Harness không bao giờ đọc nhãn confirmation (ViMDoc) hay TEST-172 (ViDoSeek). |
| Chia fold | 5 fold, `fold = SHA-256(query_id) mod 5`. Mỗi query được chấm đúng một lần, bởi model chưa thấy nhãn của nó. |
| Anchor | Mỗi fold tự fit static trên lưới 66 điểm bằng các fold train (luật hòa của A005). Hàng `static` = anchor đó. |
| Recipe | A005-R1: Adam lr 0,01 với cosine, 40 epoch, trung bình trọng số epoch 20–40, ε = 1e-6, batch 16, clip 5. **Không chọn epoch.** |
| Seed | Sàng lọc: 1 seed (`20260820`). Hàng cuối cho tổ hợp thắng: 3 seed (`--seeds 3`). |
| Metric | nDCG@10 trên đơn vị có nhãn (document ở ViMDoc, trang ở ViDoSeek). Query không có positive trong pool vẫn giữ, tính 0. |
| So sánh | Bootstrap theo cặp 10.000 lần trên toàn bộ query của dataset (seed 20260820), cùng W/T/L. Variant so với `baseline` **cùng method** (QARF với QARF, QPAF với QPAF). |
| Siêu tham số | Chốt sẵn trong từng plan. Không quét trên kết quả CV; nếu thử giá trị thứ hai thì báo cáo cả hai. |

Mỗi variant cho ra ba hàng `static`, `qarf`, `qpaf` trên mỗi dataset. Muốn chạy một granularity thì dùng `--granularity`.

## 3. Chuẩn bị (một lần cho mỗi người)

1. Lấy code: `git fetch` rồi tạo branch riêng từ `feature/lab-feature-plans`, theo tên ở mục 5.
2. Môi trường: `.venv` của dự án (`py -m venv .venv`, `.venv/Scripts/pip install -e .`, và các gói trong
   `requirements-lock.txt`). Harness chỉ cần `torch`, `numpy`, `pandas`, `pyarrow`.
3. Dữ liệu:
   - **ViDoSeek** đã có trong repo:
     `results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle` (đọc `raw_scores.parquet`,
     `queries.json`, `qrels_development.json`, `splits/`; không bao giờ đọc `qrels_test_sealed.json`).
   - **ViMDoc** nằm ngoài repo: một thư mục chứa `candidate_scores.parquet` (SHA-256 `296e0821…`, 205 MB),
     `queries.jsonl` và `dev_qrels.json`. Tấn Phát đang giữ bản tại `C:\Users\HP\qpaf-cache\a005-s1-001`. **Chỉ
     chia sẻ ba file này**, không chia sẻ `confirmation_qrels.sealed.json`.
4. Kiểm tra môi trường:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_lab -v
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --limit 120 --epochs 2 --folds 2
```

5. Chạy `baseline` trên cả hai dataset một lần (khoảng 8 + 5 phút). Kết quả phải khớp bảng ở mục 1 đến 4 chữ số
   thập phân. Nếu lệch, dữ liệu hoặc môi trường đang khác; báo ngay, đừng chạy tiếp.

## 4. Viết một variant

Mỗi variant là **một file** trong `src/qpaf/lab/variants/<tên>.py`, có hàm `build(assets) -> Variant`. Hai người
không sửa file chung nào, nên branch merge không xung đột. Bốn hook (chi tiết ở docstring của
[`variants/__init__.py`](../../src/qpaf/lab/variants/__init__.py)):

| Hook | Dùng bởi | Ràng buộc |
| --- | --- | --- |
| `page_features(query_id, text, page_ids, raw)` | F1, F4 | Không nhận nhãn. Trả về `[pages, k]` hữu hạn; harness tự z-score theo fold train |
| `calibrator()` | F2 | Module biến đổi `scores [B,N,3]`; phải là identity lúc khởi tạo |
| `loss(...)` | F3 | Thay listwise loss; nhận cả điểm của anchor để cắt top-k hoặc đánh dấu query khó |
| `aggregate(...)` | F3 | Thay max-pooling trang → document; dùng cho cả train lẫn chấm điểm |
| `hidden` | F1, F4 | 0 = tuyến tính; > 0 = thêm một lớp tanh, lớp ra khởi tạo 0 |

Mọi variant (trừ `f3_lse_pool`) đều bắt đầu **đúng bằng static anchor** ở epoch 0, giống A005. Mỗi variant cần một
file test riêng `tests/test_lab_<feature>.py` trên dữ liệu giả lập (xem `tests/test_lab.py::synthetic`).

## 5. Chạy và nộp kết quả

```powershell
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc   --data <vimdoc-cache> --variant <tên> [--asset name=path]
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --variant <tên> [--asset name=path]
.venv/Scripts/python.exe scripts/compare_lab.py --output results/lab/SUMMARY.md
```

- Kết quả được ghi vào `results/lab/<dataset>/<dataset>-<variant>.json`, gồm điểm từng query, anchor của từng fold,
  SHA-256 của input và asset, và commit nguồn. Chạy với `--limit`/`--epochs` là smoke test, ghi vào
  `results/lab/_smoke/` (bị Git bỏ qua).
- **Commit code trước khi chạy thật**, để `source_commit` trong JSON đúng và `tracked_changes` là `false`.
- Branch: `feature/lab-f1-content`, `feature/lab-f2-calibration`, `feature/lab-f3-objective`, `feature/lab-f4-qemb`.
  Mỗi branch gồm module variant, test và JSON kết quả. Không commit OCR text hay embedding.
- Mỗi người gửi Research Lead bảng `compare_lab.py` của mình kèm 3–5 dòng nhận xét, theo mục "Đọc kết quả" trong plan.

## 6. Luật giữ/bỏ

Research Lead chốt luật trong `verdict()` ở [`src/qpaf/lab/compare.py`](../../src/qpaf/lab/compare.py)
**trước khi** có kết quả đầu tiên. Khi hàm chưa được viết, cột verdict hiện `n/a`.

Đề xuất cách gộp hai dataset (Research Lead có thể đổi): một feature được ghép vào hệ thống cuối nếu verdict là
KEEP cho ít nhất một method (QARF hoặc QPAF) trên **cả hai** dataset, hoặc KEEP trên ViDoSeek và không DROP trên
ViMDoc. Lý do: ViMDoc đã gần trần, nên trên dataset này "không tệ hơn" đã là đủ.

## 7. Sau khi có kết quả: ghép và chốt

1. **Ghép** (Research Lead): tạo variant `combo` gồm mọi feature được KEEP (ví dụ feature của F1 + calibrator F2
   + loss F3), rồi chạy cả hai dataset với `--seeds 3`. Chọn QARF hay QPAF làm method chính dựa trên hàng này. Nếu
   QPAF không hơn QARF, chọn QARF đơn giản hơn, đúng cổng H3 của đề xuất.
2. **Kiểm chứng một lần trên held-out** (bước sau, cần một script nhỏ: train trên toàn dev pool, chấm trên held-out).
   Chỉ chạy cho `combo` cuối, mỗi dataset một lần. Cả ViMDoc confirmation (đã mở hai lần) và TEST-172 (đã mở ở R7)
   đều **không còn sạch**, nên kết quả này phải ghi là *post-hoc*. Kết quả chính thức sạch vẫn là A005 §2 và M5.9.
3. **Thiên lệch do chọn:** lab thử khoảng 10 variant rồi chọn cái tốt nhất trên cùng CV, nên con số CV của
   `combo` hơi lạc quan. Bước 2 tồn tại để đo phần lạc quan này. Khi báo cáo, nói rõ điều đó.

## 8. Lịch dự kiến

| Ngày | Người A | Người B | Research Lead |
| --- | --- | --- | --- |
| 1 | Tải và gộp OCR (F1); viết `f2_pwl`, `f2_pwl_rrf` + test, chạy | Viết `f3_*` + test, chạy; encode query (F4) | Chốt `verdict()`; push branch lab |
| 2 | Viết `f1_content`, `f1_content_mlp` + test, chạy | Viết `f4_*` + test, chạy | Gom bảng |
| 3 | `f1_page_only` nếu F1 thắng; phân tích hình dạng `g_m` (F2) | Phân tích W/L (F3), bảng "loại câu hỏi → trọng số" (F4) | `combo`, 3 seed |
| 4 | — | — | Held-out một lần, viết kết luận |

Một lần chạy đầy đủ (5 fold × 2 granularity × 1 seed) mất khoảng **8 phút trên ViMDoc** và **4–5 phút trên
ViDoSeek** (CPU laptop, đo lúc hai dataset chạy song song). ApproxNDCG chậm hơn khoảng 2–3 lần. Ba seed thì nhân 3.

## 9. Điều không làm

- Không đọc hay chia sẻ nhãn confirmation/TEST-172, không thêm split mới vào harness.
- Không chọn epoch, không quét siêu tham số trên kết quả CV rồi báo cáo như kết quả độc lập.
- Không sửa `src/qpaf/lab/{data,model,train,compare}.py` trên branch feature. Nếu harness có lỗi, báo Research
  Lead để sửa trên `feature/lab-feature-plans`, rồi mọi người chạy lại `baseline`.
