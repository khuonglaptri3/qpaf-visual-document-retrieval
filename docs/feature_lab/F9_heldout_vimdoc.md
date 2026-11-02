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

## 6. Kết quả (mở nhãn một lần, 2/11/2026 09:00 UTC, post-hoc)

Phần trên được commit ở `075466b` trước khi có điểm reranker; top-10 niêm phong ở `0618428` (SHA-256 `3a47d1b4…52eb`);
lời cho phép của Research Lead ("Tôi cho phép mở") ở `d4a0c10`. Kết quả:
[`results/lab/vimdoc/heldout/heldout_result.json`](../../results/lab/vimdoc/heldout/heldout_result.json).
Qwen3-4B chấm 203.331 cặp: 88/204 chunk trên workspace Modal `buiphat251399` (hết credit giữa chừng), 116 chunk
còn lại trên `tranthanhzt123321` sau khi chép nguyên byte các chunk đã xong sang Volume mới; cùng image, revision và
code, GPU A10 và A10G. 5 trong 8.904 query không có document đúng trong pool (nDCG@10 = 0 ở mọi hàng).

| Hàng | nDCG@10 | R@1 | R@3 | CV dev (nDCG@10) |
| --- | ---: | ---: | ---: | ---: |
| static | 0,9589 | 92,13 | 97,26 | 0,9586 |
| QARF | 0,9615 | 92,57 | 97,57 | 0,9611 |
| QPAF | 0,9615 | 92,48 | 97,64 | 0,9613 |
| static + 4B (F7) | 0,9682 | 93,80 | 98,05 | 0,9706 |
| **QPAF + 4B (F9, hàng chính)** | **0,9708** | **94,09** | **98,42** | 0,9716 |

| So sánh ghép cặp (8.904 query) | nDCG@10 (thắng/hòa/thua) | R@1 (điểm %) |
| --- | --- | --- |
| **F9 − QPAF (chính)** | **+0,0092 [+0,0076, +0,0110]** 362/8.434/108 | **+1,62 [+1,25, +2,00]** |
| F9 − static | +0,0118 [+0,0099, +0,0138] 402/8.359/143 | +1,97 [+1,55, +2,38] |
| F9 − QARF | +0,0093 [+0,0075, +0,0111] 369/8.389/146 | +1,53 [+1,13, +1,91] |
| F9 − F7 | +0,0025 [+0,0009, +0,0042] 219/8.518/167 | +0,29 [−0,04, +0,63] |

Đọc kết quả: ba hàng baseline gần như trùng A005-R1 trên cùng split (0,9589 / 0,9614 / 0,9616) và CV dev, nên pipeline
held-out khớp lab. Mức tăng của reranker giữ trên confirmation (+0,0092 so với +0,0103 của CV) và có ý nghĩa với
khoảng tin cậy hẹp, nhưng nhỏ về tuyệt đối vì ViMDoc mức document đã gần trần (QPAF 0,9615). F9 − F7 lần này có ý
nghĩa trên nDCG@10 (+0,0025) nhưng không có ý nghĩa trên R@1; trên ViDoSeek nó là +0,0029 không có ý nghĩa. Hai bộ
cùng chiều, nên gate QPAF có thể thêm một chút khi đứng trước reranker, nhưng mức đó rất nhỏ và là một trong bốn so
sánh không hiệu chỉnh đa so sánh. Confirmation ViMDoc giờ đã mở ba lần (A005 Stage 5, R1 và lần này); không dùng nó
để chọn thêm gì.
