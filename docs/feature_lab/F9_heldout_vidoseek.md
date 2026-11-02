# F9 — Kiểm chứng một lần trên ViDoSeek TEST-172 (đăng ký trước)

**Trạng thái:** đăng ký ngày 2/11/2026, trước khi chấm reranker trên test và trước khi mở nhãn.
**Người duyệt mở nhãn:** Research Lead (Tấn Phát).

## 1. Mục đích và giới hạn

Đo cấu hình đã chọn trên CV, **QPAF + Qwen3-Reranker-4B** ([F9](F9_gate_rerank.md)), trên 172 query mà lab F5–F9
chưa bao giờ đọc nhãn. Đây là kết quả **post-hoc**: nhãn TEST-172 đã được mở một lần ở R7, nên đây không phải
kết quả độc lập tuyệt đối. Tuy vậy, không lựa chọn nào trong F5–F9 (model, K, λ, biến thể) dùng nhãn TEST-172.

## 2. Mô hình cuối (chỉ fit trên 970 query dev)

| Mục | Giá trị |
| --- | --- |
| Static anchor | `fit_anchor` trên cả 970 query dev (lưới 66 điểm, hòa lấy điểm lưới trước) |
| Gate QARF, QPAF | Variant `baseline` của lab, seed 20260820, `RECIPE`, train trên cả 970 query dev |
| Reranker | `Qwen/Qwen3-Reranker-4B` @ `22e68366`, prompt và `max_length` 1024 như F7 |
| Top-K | 20 trang theo gate QPAF (F9) và theo static (F7); chấm hợp hai tập |
| λ | λ hằng tốt nhất trên bảng OOF dev gộp, hòa lấy λ nhỏ: **F9 = 0,9** (0,9215; 0,8 cho 0,9214), **F7 = 0,8** (0,9220) |

## 3. Hàng báo cáo, chỉ số và so sánh

- Hàng: `static`, `qarf`, `qpaf`, `f7_static_qwen4b` (static + 4B), **`f9_qpaf_qwen4b` (QPAF + 4B, hàng chính)**.
- Chỉ số: nDCG@10 như lab; Recall@1 và Recall@3 mức trang như bảng 2 của HEAVEN ([arXiv:2510.22215](https://arxiv.org/abs/2510.22215)).
- So sánh ghép cặp (bootstrap 10.000 lần, seed 20260820) trên nDCG@10 và Recall@1: F9 − QPAF (**chính**), F9 − static,
  F9 − QARF, F9 − F7. Với 172 query, khoảng tin cậy sẽ rộng; không thêm so sánh nào sau khi mở nhãn.
- Phụ: trung bình trên 1.142 query = 970 hàng OOF dev đã commit + 172 hàng test, để đặt cạnh bảng của bài báo
  (bài báo dùng đúng 1.142 query này, toàn corpus). Pool của chúng ta là hợp các top list, không phải toàn corpus.

## 4. Thứ tự (script `scripts/lab_heldout.py`)

1. `prepare` (không nhãn): fit trên dev, chấm pool của 172 query test, ghi cặp top-20 (OCR) ra cache.
2. Research Lead chạy Qwen3-4B trên Modal (`--detach`), rồi `collect` ra `test_scores_qwen3-4b.json`.
3. `seal` (không nhãn): tính năm hàng, ghi `results/lab/vidoseek/heldout/test_predictions.csv.gz`, băm SHA-256
   vào `prediction_seal.json`, tạo bản nháp `authorization.json`; commit.
4. Research Lead viết lời cho phép; lời đó được ghi nguyên văn vào `authorization.json`; commit.
5. `open`: kiểm hash của file dự đoán, của nhãn sealed (`05eaaa81…d154`) và code; đọc `qrels_test_sealed.json`
   đúng một lần; tính chỉ số từ file đã niêm phong; ghi `heldout_result.json` (create-once). Không chạy lại, không
   chọn gì từ kết quả.
