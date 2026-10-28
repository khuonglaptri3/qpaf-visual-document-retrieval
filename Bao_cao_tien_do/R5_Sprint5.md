# R5 — Báo cáo tiến độ Sprint 5 (M5.11)

**Người báo cáo:** Tấn Phát (Research Lead). **Ngày:** 2026-10-28.
**Sprint 5 (M5):** Ablation, Robustness & Generalization, kế hoạch 2026-11-09 → 2026-11-22.
Mọi số liệu dưới đây lấy từ các file bằng chứng trong repo, có dẫn link. Test 172 query
ViDoSeek được mở **đúng một lần** ở R7. Các số ablation và đo tài nguyên chỉ dùng validation
(171 query).

## 1. Kết luận

**G3 = `LIMITED-CLAIM` (Research Lead xác nhận). G3A = `NOT_RUN` (Thanh chấp nhận).**

| nDCG@10 trên TEST-172, trung bình 3 seed | Giá trị |
| --- | --- |
| Baseline mạnh nhất `train_fitted_static` | 0,8255 |
| QPAF-v1 | 0,8188 |
| Learned QARF-v1 | 0,7426 |
| QPAF − QARF matched | **+0,0762**, CI95 [+0,0429, +0,1099], W/T/L 49 / 107 / 16 |
| QPAF − `train_fitted_static` | **−0,0067**, CI95 [−0,0190, +0,0053], W/T/L 7 / 152 / 13 |

QPAF vượt QARF matched ở cả ba seed, và kết quả ổn định (độ lệch chuẩn của delta giữa các
seed là 0,0017). Nhưng **QPAF không vượt baseline mạnh nhất**. Đây chính là phép thử quyết
định mà G2A đã ghi trước khi mở test. Kết quả âm này giống trên validation ở Sprint 4
(−0,0051).

Câu được phép nói: *trên ViDoSeek TEST-172, QPAF-v1 vượt QARF-v1 matched ở ba seed đã đăng
ký trước.* Câu này phải luôn đi kèm ba giới hạn:
1. QPAF không vượt `train_fitted_static`.
2. Gate latency chưa được xác lập.
3. Không có bằng chứng tổng quát hóa sang ViMDoc hay benchmark ngoài.

## 2. Tiến độ theo task

| Task | Roster | Nội dung | Owner | Kết quả | PR |
| --- | --- | --- | --- | --- | --- |
| M5.1 | R1 | Preregister ma trận 3 seed, thứ tự ablation, drop-first | Thanh | ACCEPTED | #41 |
| M5.2 | R2 | Receipt nhất quán cache 3 seed | Khương | ACCEPTED (owner tự báo đã review) | #42 |
| M5.3 | R3 | QARF/QPAF matched seed `20260821` | Tấn Phát | 2 run PASS, Thanh ACCEPTED | #43 |
| M5.4 | R4 | QARF/QPAF matched seed `20260822` | Tấn Phát | 2 run PASS, Thanh ACCEPTED | #44 |
| M5.5 | R5 | Retriever/normalization, latency, CUDA (validation) | Khương | ACCEPTED_WITH_SCOPE_LIMIT | #45 |
| M5.6 | R6 | Ablation feature, query-level vs page-level (validation) | Tấn Phát | ACCEPTED_WITH_DOCUMENTED_DEVIATION_D1 | #46 |
| — | R7 | TEST-172: một run sealed | Tấn Phát chạy, Thanh verify | PASS_WITH_NUMERICAL_PARITY_NOTE | #48 |
| M5.7 | R8 | Tổng hợp 3 seed | Thanh | ACCEPTED_WITH_NEGATIVE_BASELINE_RESULT | #48 |
| M5.8 | R9 | Benchmark ngoài sealed | Thanh | `NOT_RUN_DEFERRED` | #48 |
| M5.9 | — | G3: độ ổn định | Tấn Phát | `LIMITED-CLAIM`, Research Lead xác nhận | #49 |
| M5.10 | — | G3A: giới hạn claim | Thanh | `NOT_RUN`, Thanh chấp nhận | #50 |
| M5.11 | — | Báo cáo R5 | Tấn Phát | Tài liệu này | — |

M5.1–M5.10 được merge trong 2026-10-25 → 28, sớm khoảng ba tuần so với kế hoạch
(09/11 → 22/11). Không task lõi nào bị cắt (R1–R4, R7, R8). Cả hai task tuỳ chọn R5, R6
đều chạy xong, nên luật drop-first không phải dùng đến.

## 3. Bằng chứng chính

**Bảng TEST-172 của R7** ([`metrics_table.json`](../results/r7/RUN-QPAF-R7-TEST-001-20261028T034438Z-A01/metrics_table.json),
run `RUN-QPAF-R7-TEST-001-20261028T034438Z-A01`, 172 query, 83.119 candidate page):

| Hạng | Phương pháp | nDCG@10 | R@1 | MRR@10 | QPAF − hàng này |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `train_fitted_static` (co-strongest duy nhất) | 0,8255 | 0,6512 | 0,7756 | −0,0067 |
| 2 | `colqwen25` | 0,8250 | 0,6628 | 0,7755 | −0,0062 |
| — | **QPAF-v1** (trung bình 3 seed) | 0,8188 | 0,6628 | 0,7716 | — |
| 3 | `rrf_k60` | 0,7878 | 0,5988 | 0,7297 | +0,0310 |
| 4 | `uniform_combsum` | 0,7865 | 0,5930 | 0,7279 | +0,0323 |
| 5 | `learned_qarf` (seed `20260820`) | 0,7428 | 0,5465 | 0,6803 | +0,0760 |
| 6 | `bge_m3` | 0,7348 | 0,5349 | 0,6701 | +0,0839 |
| 7 | `bm25` | 0,7226 | 0,5291 | 0,6596 | +0,0962 |

QPAF theo từng seed: 0,8173 / 0,8200 / 0,8190. QARF theo từng seed: 0,7428 / 0,7422 /
0,7428. Hàng `colqwen25` chỉ để mô tả: chênh lệch đó không phải phép so sánh đã preregister.
Oracle dùng nhãn (chỉ là cận trên, không được chọn) cho per-page W66 0,9107 và per-query
W66 0,8895, tức khoảng trống từ QPAF đến oracle page-level là 0,0919.

**Tổng hợp 3 seed M5.7** ([README](../evidence/revisions/m5.7-001/README.md),
`summary.json` `03581b79…05f9`, event `QPAF-REG-20261028-0003`):
- Cách tính: trung bình delta của 3 seed theo từng query trước, rồi bootstrap 10.000 lần theo
  cặp query, seed `20260820`.
- Delta QPAF − QARF theo seed: +0,0745 / +0,0778 / +0,0762. Top-5% query đóng góp 31,0%
  phần tăng, dưới ngưỡng 90%.
- Delta QPAF − `train_fitted_static` theo seed: −0,0083 / −0,0055 / −0,0065, âm ở cả ba seed.
- Subgroup (chỉ để mô tả): QPAF − QARF dương ở cả hai nửa theo số candidate (+0,066 / +0,086)
  và theo độ dài query (+0,085 / +0,065). Mọi query đều có đúng một trang liên quan.

**Seed 2 và 3 trên validation** (M5.3/M5.4, mỗi run có authorization riêng, chạy CPU local):

| nDCG@10 validation | `20260820` | `20260821` | `20260822` |
| --- | ---: | ---: | ---: |
| QARF | 0,7521 | 0,7410 | 0,7511 |
| QPAF | 0,8663 | 0,8663 | 0,8679 |

Mọi run đều finite. Reload trong process mới lệch tối đa `3,33e-16` (ngưỡng `1e-7`). M5.2
xác nhận 1.142 query và 551.764 dòng candidate khớp giữa 6 luồng input.

**G3 M5.9** ([README](../evidence/revisions/m5.9-001/README.md), `decision.json`
`c87033bf…390c`, event `QPAF-REG-20261028-0005`). Áp 9 điều kiện của `frozen_protocol.md` §5:
- Đạt 7 điều kiện.
- Điều kiện 4 (vượt baseline) **trượt**.
- Điều kiện 6 (latency) **chưa xác lập**.

**G3A M5.10** ([README](../evidence/revisions/m5.10-001/README.md), event `QPAF-REG-20261028-0006`):
`NOT_RUN`, vì không có run external nào được authorize và kiểm chứng. Cache ViDoRe P0-03 cũ
có tồn tại, nhưng đã đọc qrels khi tạo, nên không phải bằng chứng sealed.

**Chẩn đoán M5.5 trên validation** ([báo cáo](../docs/reports/milestones/M5.5/README.md)):
- Bỏ ColQwen2.5 khỏi fusion đều làm giảm nhiều nhất: nDCG@10 0,7892, so với 0,8413 khi
  dùng đủ ba kênh.
- Bỏ BM25 lại tăng lên 0,8615. Z-score cho 0,8453.
- GPU A10G: QPAF median 2,43 ms/query, peak CUDA 0,0324 GiB.

**Ablation M5.6 trên validation** ([báo cáo](M5_6_TanPhat.md)):
- Bỏ từng nhóm feature phụ chỉ làm ΔnDCG@10 thay đổi trong ±0,002.
- Page-level conditioning là yếu tố tạo khác biệt: QPAF − QARF = +0,1187,
  CI [+0,0819, +0,1566].

## 4. Vấn đề phát sinh và cách xử lý

1. **Verifier R7 gốc so sánh float tuyệt đối nên trượt trên CPU khác.**
   - Score học lệch tối đa `4,44e-16`, không có query nào đổi thứ hạng.
   - Thanh dùng audit độc lập với dung sai `1e-7` đã authorize, và không sửa runner đã pin.
2. **Đo GPU M5.5 cần ba lần gọi.**
   - A01 mất phản hồi. A02 lỗi BlobCreate 401 khi xuất kết quả.
   - A03 được khôi phục từ log của chính provider call đó, không chạy GPU lại.
   - Marker lỗi của client được giữ nguyên.
3. **Lệch D1 ở M5.6.** Bản authorization chép vào run dùng LF, bản commit dùng CRLF. Nội
   dung giống nhau từng byte sau khi đổi xuống dòng. Thanh chấp nhận kèm ghi chú.
4. **Luật G3 là post hoc, đã công khai.**
   - Protocol không ánh xạ 9 điều kiện sang GO / LIMITED-CLAIM / NO-GO / BLOCKED.
   - Research Lead chọn "trượt điều kiện 4 → `LIMITED-CLAIM`" sau khi đã biết kết quả M5.7.
   - Không thêm ngưỡng mới nào.
5. **Câu "không có score cache" ở các bản ghi trước bị nói quá rộng.** G3A làm rõ: cache
   ViDoRe P0-03 có tồn tại nhưng không hợp lệ cho R9. Riêng ViMDoc thì vẫn chưa có cache đã
   kiểm chứng.

## 5. Hạn chế và tồn đọng

1. **QPAF không vượt baseline mạnh nhất trên test.** Không được báo cáo QPAF là cải tiến so
   với fusion tĩnh. Kết quả âm này phải xuất hiện trong luận văn.
2. **QARF là đối chứng yếu**, do loss A001 lệch hướng (Sprint 4). Phần vượt QARF chủ yếu cho
   thấy gate page-level chịu được loss sai tốt hơn.
3. **Gate latency chưa xác lập.** M5.5 đo 171 ID khác nhau × 6 vòng, trong khi quy định cần
   ít nhất 1.000 query đo. Không được claim về vận hành.
4. **Một held-out split, một dataset.** Gộp 3 seed không tạo thêm query mới. Không có kết quả
   ViMDoc hay external.
5. **Review kỹ thuật QPAF seed 2 và 3 không phải replay độc lập.** Báo cáo do trợ lý của người
   chạy viết, Thanh nghiệm thu. R7 và M5.7 thì Thanh audit riêng.
6. **M5.2 được ghi hoàn thành theo lời Khương**, không ghi tên reviewer.
7. **Tồn đọng từ Sprint 4:**
   - Thanh chưa có review riêng cho A004.
   - M4.2 vẫn chờ owner nghiệm thu.
   - Workbook `POAI_Milestone_Group01_Hoan_Chinh.xlsx` vẫn ghi M3–M5 là Not Started.

## 6. Kế hoạch Sprint 6 (M6, 2026-11-23 → 2026-12-06)

| Task | Nội dung | Owner | Thời gian |
| --- | --- | --- | --- |
| M6.1 | Kiểm tra load checkpoint và inference trong môi trường sạch (parity ≤ 1e-7) | Tấn Phát | 23–25/11 |
| M6.2 | Freeze ledger thí nghiệm và link provenance | Thanh | 23–25/11 |
| M6.3 | Chốt manifest dữ liệu và retrieval | Khương | 23–26/11 |
| M6.4 | Sinh bảng kết quả cuối từ ledger | Thanh | 26–30/11 |
| M6.5 | Hình, ví dụ, phân tích lỗi | Thanh | 01–02/12 |
| M6.6 | Viết phần phương pháp và kết quả dương/âm | Tấn Phát | 30/11–03/12 |
| M6.7 | Đóng gói và kiểm tra archive tái lập | Khương | 27/11–03/12 |
| M6.8 | Dàn ý luận văn, slide, demo | Tấn Phát | 02–03/12 |
| M6.9 | Audit độc lập cuối cùng | Thanh | 03–04/12 |
| M6.10 | G4: gói bằng chứng có đủ để nộp không | Tấn Phát | 04/12 |
| M6.11 | Báo cáo R6 | Tấn Phát | 03–04/12 |

Việc cần làm ngay:
1. M6.6 viết đúng claim boundary của G3/G3A. Đặt kết quả âm so với `train_fitted_static`
   ngang hàng với kết quả dương so với QARF, và nêu khoảng trống oracle–learned (0,0919).
2. M6.4 lấy số trực tiếp từ `metrics_table.json` của R7 và `summary.json` của M5.7, không
   chép tay.
3. Không mở lại TEST-172. Không chạy seed, loss hay checkpoint mới để "sửa" kết quả.
4. Cập nhật workbook, nghiệm thu M4.2, và xin Thanh review A004.
