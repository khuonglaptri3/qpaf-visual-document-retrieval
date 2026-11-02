# F9 — Kiểm chứng một lần trên ViMDoc confirmation (đăng ký trước)

**Trạng thái:** đăng ký ngày 2/11/2026, sau held-out ViDoSeek ([F9_heldout_vidoseek.md](F9_heldout_vidoseek.md)),
trước khi chấm reranker trên confirmation và trước khi mở nhãn. **Người duyệt mở nhãn:** Research Lead (Tấn Phát).

## 1. Mục đích và giới hạn

Đo cấu hình đã chọn trên CV, **QPAF + Qwen3-Reranker-4B**, trên 8.904 query confirmation của ViMDoc (M4.1), đơn vị
document (điểm document = điểm trang cao nhất), như lab. Đây là kết quả **post-hoc**:

- Nhãn confirmation đã được mở hai lần (A005 Stage 5 và R1). Các hàng baseline trên split này đã được biết gần
  đúng (A005-R1: static 0,9589, QARF 0,9614, QPAF 0,9616). Không lựa chọn nào trong F5–F9 dùng nhãn confirmation.
- Kết quả ViDoSeek held-out đã được xem trước khi viết bản này. Nó không đổi gì: cấu hình và luật chọn λ giống hệt
  bản ViDoSeek; λ của ViMDoc lấy từ dev ViMDoc.
- Dự án dùng nhãn mức document, còn bài báo HEAVEN báo Recall mức trang, nên ViMDoc **không** được đặt cạnh bảng
  của bài báo.

## 2. Mô hình cuối (chỉ fit trên 2.000 query dev: 1.600 train + 400 validation)

| Mục | Giá trị |
| --- | --- |
| Static anchor | `fit_anchor` trên cả 2.000 query dev |
| Gate QARF, QPAF | Variant `baseline` của lab, seed 20260820, `RECIPE`, train trên cả 2.000 query dev |
| Reranker | `Qwen/Qwen3-Reranker-4B` @ `22e68366`, prompt và `max_length` 1024 như F7 |
| Top-K | 20 trang theo gate QPAF (F9) và theo static (F7); chấm hợp hai tập |
| λ | λ hằng tốt nhất trên bảng OOF dev gộp, hòa lấy λ nhỏ: **F9 = 0,5** (0,9716; cả 5 fold đều 0,5), **F7 = 0,8** (0,9706) |

## 3. Hàng báo cáo, chỉ số và so sánh

- Hàng: `static`, `qarf`, `qpaf`, `f7_static_qwen4b` (static + 4B), **`f9_qpaf_qwen4b` (QPAF + 4B, hàng chính)**.
- Chỉ số: nDCG@10 mức document (chính, như lab); Recall@1 và Recall@3 mức document.
- So sánh ghép cặp (bootstrap 10.000 lần, seed 20260820) trên nDCG@10 và Recall@1: F9 − QPAF (**chính**), F9 − static,
  F9 − QARF, F9 − F7. Không thêm so sánh nào sau khi mở nhãn.
- Query không có document đúng trong pool vẫn được tính (nDCG@10 = 0) và được đếm riêng.

## 4. File niêm phong

ViMDoc có 4,2 triệu cặp (query, trang), nên file niêm phong `results/lab/vimdoc/heldout/confirmation_rankings.jsonl.gz`
lưu **top-10 document của mỗi hàng cho mỗi query** kèm điểm. Như vậy là đủ để tính đúng nDCG@10 và Recall@1/@3
(test `DocumentRankingTests` so với `unit_ndcg` của lab trên toàn bộ điểm, kể cả khi hai document hòa điểm).

## 5. Thứ tự (script `scripts/lab_heldout.py --dataset vimdoc`)

1. `prepare` (không nhãn): fit trên dev, chấm pool của 8.904 query confirmation, ghi cặp top-20 (OCR) ra cache.
2. Research Lead chạy Qwen3-4B trên Modal (`--detach`), rồi `collect` ra `test_scores_qwen3-4b.json`.
3. `seal` (không nhãn): tính năm hàng, ghi file top-10, băm SHA-256 vào `prediction_seal.json`, tạo bản nháp
   `authorization.json`; commit.
4. Research Lead viết lời cho phép; lời đó được ghi nguyên văn vào `authorization.json`; commit.
5. `open`: kiểm hash của file niêm phong, của nhãn sealed (theo marker `prepare` của A005 Stage 1: `ce9ad0fb…3f2b`)
   và code; đọc `confirmation_qrels.sealed.json` đúng một lần; ghi `heldout_result.json` (create-once). Không chạy
   lại, không chọn gì từ kết quả.
