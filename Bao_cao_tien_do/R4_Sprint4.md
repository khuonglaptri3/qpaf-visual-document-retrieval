# R4 — Báo cáo tiến độ Sprint 4 (M4.8)

**Người báo cáo:** Tấn Phát (Research Lead). **Ngày:** 2026-10-24.
**Sprint 4 (M4):** Main Method Decision & Full Baseline Evaluation, kế hoạch 2026-10-26 → 2026-11-08.
Mọi số liệu dưới đây lấy từ các file bằng chứng trong repo, có dẫn link. Mọi số đều là
**validation** (171 query ViDoSeek, seed `20260820`); test 172 query vẫn sealed.

## 1. Kết luận

**G2A đã freeze: QPAF-v1 tiếp tục là phương pháp chính (`continue_qpaf`).** Kết luận chính
3 seed sẽ được đánh giá trên ViDoSeek test 172. ViMDoc confirmation được ghi `NOT_RUN_DEFERRED`.

| nDCG@10 (validation) | Giá trị |
| --- | --- |
| Baseline mạnh nhất `train_fitted_static` [0, 0,1, 0,9] | 0,8714 |
| QPAF-v1 (đã freeze ở M4.3) | 0,8663 |
| Learned QARF-v1 | 0,7521 |
| QPAF − baseline mạnh nhất | **−0,0051**, CI95 [−0,0135, +0,0028], W/T/L 3 / 161 / 7 |

Trên validation, **QPAF chưa vượt baseline mạnh nhất**. CI chứa 0, và đây mới là một seed.
Theo `baseline_policy.md` §3.5, câu hỏi này chỉ được quyết định trên test 3 seed.

Trong sprint, nhóm phát hiện **loss train (A001) xếp hạng trọng số fusion ngược với nDCG@10**.
Nhóm đã thử sửa một lần (`revise_once`, amendment A004). Gate preregister chỉ dùng train đã
trượt, nên A004 không được áp dụng, và hướng đi quay về `continue_qpaf`.

## 2. Tiến độ theo task

| Task | Nội dung | Owner | Kết quả | PR |
| --- | --- | --- | --- | --- |
| M4.1 | Seal ID và quyền truy cập confirmation ViMDoc | Thanh | `ID_SPLITS_SEALED_CONFIRMATION_ACCESS_CLOSED` | #33 |
| M4.2 | Freeze đầu vào baseline, fit static chỉ trên train | Khương | Hoàn thành kỹ thuật; trọng số [0, 0,1, 0,9] | #34 |
| M4.3 | Thực thi nhánh G2 (`continue_qpaf`): freeze QPAF-v1 | Tấn Phát | Replay PASS, Research Lead xác nhận | #35 |
| M4.4 | Đánh giá đầy đủ baseline triển khai được (validation) | Tấn Phát | 2 run `SUCCESS`, verify PASS | #36 |
| M4.5 | Kiểm định độc lập fairness và độ bất định của baseline | Thanh | PASS, Thanh ACCEPTED | #37 |
| M4.6 | Chốt hướng phương pháp chính | Tấn Phát | `revise_once` → gate A004 trượt → `continue_qpaf` | #38 |
| M4.7 | G2A: freeze lộ trình robustness | Tấn Phát | Freeze PASS, Research Lead xác nhận | #39 |
| M4.8 | Báo cáo R4 | Tấn Phát | Tài liệu này | — |

Toàn bộ M4.1–M4.7 được merge trong 2026-10-23 → 24, sớm khoảng hai tuần so với kế hoạch
(26/10 → 08/11).

## 3. Bằng chứng chính

**Bảng baseline M4.4** ([README](../evidence/revisions/m4.4-001/README.md)). Mọi phương pháp
dùng chung 82.255 candidate page, cùng điểm và cùng evaluator. Run MTH chạy 14,7 s, run ORC
chạy 267,5 s.

| Hạng | Phương pháp | nDCG@10 | R@1 | MRR@10 |
| ---: | --- | ---: | ---: | ---: |
| 1 | `train_fitted_static` (co-strongest duy nhất) | 0,8714 | 0,7368 | 0,8331 |
| 2 | `colqwen25` | 0,8693 | 0,7368 | 0,8305 |
| 3 | `uniform_combsum` | 0,8413 | 0,6959 | 0,7970 |
| 4 | `rrf_k60` | 0,8294 | 0,6784 | 0,7817 |
| 5 | `bge_m3` | 0,7639 | 0,5848 | 0,7055 |
| 6 | `learned_qarf` | 0,7521 | 0,5848 | 0,6969 |
| 7 | `bm25` | 0,7251 | 0,5497 | 0,6653 |
| — | QPAF-v1 (không tham gia chọn baseline) | 0,8663 | 0,7368 | 0,8283 |

Oracle dùng nhãn (chỉ là cận trên): per-page W66 0,9401, per-query W66 0,9119. Khoảng trống
so với QPAF là +0,0738 và +0,0456.

**Audit M4.5** ([`verification.json`](../evidence/revisions/m4.5-001/verification.json),
Thanh ACCEPTED, event `QPAF-REG-20261024-0001`):
- Fit lại lưới static 66 điểm chỉ từ 799 query train, ra cùng trọng số.
- Replay điểm của cả 7 baseline, sai khác tối đa `2,22e-16`.
- So với ColQwen2.5 dùng một mình: QPAF − ColQwen = −0,0030, CI95 [−0,0079, +0,0004].

**Probe loss và gate A004 ở M4.6** ([`loss_alignment_probe.json`](../evidence/revisions/m4.6-001/loss_alignment_probe.json),
chỉ dùng 799 query train, lưới static 66 điểm):

| | Loss A001 (đang dùng) | Loss A004 (đề xuất) | Ngưỡng gate |
| --- | ---: | ---: | --- |
| Spearman(loss, nDCG@10) | +0,537 | +0,361 | ≤ −0,5: trượt |
| Trọng số có loss thấp nhất | [1, 0, 0] (BM25) | [0,6, 0, 0,4] | |
| nDCG@10 tại điểm đó (max 0,8642) | 0,7290 | 0,7908 | ≥ 0,8542: trượt |

QARF train đủ 20 epoch thì hội tụ về đúng nghiệm BM25-only: trọng số ≈ [0,9985, 0,0006, 0,0008].
Điều này giải thích vì sao QARF chỉ đạt 0,7521.

**Freeze G2A M4.7** ([README](../evidence/revisions/m4.7-001/README.md),
`g2a_freeze.json` `26d9bab6…3217`, event `QPAF-REG-20261024-0006`):
- QPAF-v1: checkpoint `e4b00ab4…`, epoch 19, loss A001.
- Seed 20260821/22 chỉ đổi `training.seed`.
- Baseline cần đánh bại là `train_fitted_static`.
- Held-out: test 172, sealed qrels `05eaaa81…`.
- Roster R1–R10. Chỉ R7 được mở test, và chỉ mở một lần.

## 4. Vấn đề phát sinh và cách xử lý

1. **Loss train lệch hướng với metric.** Đây là phát hiện quan trọng nhất của sprint.
   - Xử lý: chạy probe chỉ đọc, không train.
   - Đề xuất A004 kèm gate và luật dừng được preregister trước khi chạy.
   - Gate trượt, nên dừng đúng luật: không thử loss thứ hai, không train v2.
2. **Các quyết định post hoc, đã công khai:**
   - Chọn `revise_once` và hai ngưỡng của gate A004: đặt sau khi đã thấy M4.4/M4.5 và probe,
     nhưng được chốt trước khi gate chạy.
   - Bản xác nhận M4.3 được ghi sau run M4.4. Thứ tự này được giữ nguyên, không ghi lùi ngày.
3. **PR #36 (M4.4) bị merge vào nhánh `feature/m4-3-qpaf-freeze` thay vì `develop`**, vì base
   của stacked PR không được đổi. M4.4 vào được `develop` nhờ nhánh M4.5 được tạo trên M4.4.
   Quy tắc từ nay: merge theo thứ tự, dùng "Create a merge commit", và kiểm tra base là
   `develop` trước khi merge PR sau.
4. **Lệch bit cuối khi verify.** Trên Python 3.11, verifier M4.4 lệch tối đa `6,66e-16` so với
   Python 3.13, do hàm `sum` khác nhau. M4.5 so sánh theo dung sai `1e-12` của protocol và
   không sửa code M4.4 đã seal.

## 5. Hạn chế và tồn đọng

1. **Một seed, checkpoint được chọn trên chính validation**, nên số validation lạc quan.
2. **QARF là đối chứng yếu**, do lỗi loss. QPAF − QARF ≥ 0,01 trên test chủ yếu cho thấy gate
   page-level chịu được loss sai tốt hơn. Phép thử quyết định là QPAF có vượt
   `train_fitted_static` hay không.
3. **Thanh chưa review A004 và kết quả gate.** Thủ tục amendment yêu cầu bước này.
4. **M4.2 vẫn chờ owner nghiệm thu** ([README](../evidence/revisions/m4.2-002/README.md)).
5. **ViMDoc chưa có score cache.** Yêu cầu baseline selection cho ViMDoc của M4.1 vẫn mở;
   claim bị giới hạn trong ViDoSeek.
6. **23 test M1/M2 cũ lỗi** do hash drift fixture, y hệt trên `develop`. Mọi test M4 đều PASS.
   Phải chạy bằng `.venv` (Python 3.13.7, NumPy 2.5.4, pypdfium2 4.30.0); Python hệ thống
   cho lỗi giả.
7. **Workbook `POAI_Milestone_Group01_Hoan_Chinh.xlsx` chưa cập nhật trạng thái** (M3.x, M4.x
   vẫn ghi Not Started).

## 6. Kế hoạch Sprint 5 (M5, 2026-11-09 → 2026-11-22)

| Task | Roster | Nội dung | Owner | Thời gian |
| --- | --- | --- | --- | --- |
| M5.1 | R1 | Preregister ma trận 3 seed, thứ tự ablation, luật drop-first (chỉ tầng tuỳ chọn) | Thanh | 09–10/11 |
| M5.2 | R2 | Receipt về độ nhất quán cache cho các seed; nhãn ngoài vẫn sealed | Khương | 09–11/11 |
| M5.3 | R3 | QARF/QPAF matched seed `20260821`, kèm kiểm tra reload và NaN/Inf | Tấn Phát | 11–13/11 |
| M5.4 | R4 | QARF/QPAF matched seed `20260822`, kèm kiểm tra reload và NaN/Inf | Tấn Phát | 16–18/11 |
| M5.5 | R5 (tuỳ chọn) | Kiểm tra retriever/normalization, latency, bộ nhớ; chỉ validation | Khương | 16–18/11 |
| M5.6 | R6 (tuỳ chọn) | Ablation feature và so query-level với page-level; chỉ validation | Tấn Phát | 18–19/11 |
| — | R7 | **TEST-172**: một run sealed gồm 7 baseline, QARF ×3, QPAF ×3, oracle W7/W66 | Tấn Phát chạy, Thanh verify | sau M5.3/M5.4 |
| M5.7 | R8 | Tổng hợp 3 seed: CI, W/T/L, độ ổn định, subgroup, lỗi | Thanh | 19–20/11 |
| M5.8 | R9 (deferred) | Benchmark ngoài sealed | Thanh | 19–20/11 |
| M5.9 | — | G3: kết quả có ổn định qua các seed không | Tấn Phát | 20/11 |
| M5.10 | — | G3A: giới hạn claim trong bằng chứng sealed | Thanh | 20/11 |
| M5.11 | — | R5: báo cáo tiến độ Sprint 5 | Tấn Phát | 19–20/11 |

Lõi không được cắt: R1–R4, R7, R8. Test 172 chỉ được mở ở R7, sau khi seed 2 và 3 đã được review.

Việc cần làm ngay:
1. Lập authorization cho R3 (seed `20260821`) và R4 (seed `20260822`). Mỗi run duyệt riêng,
   chạy CPU local như M3.2/M3.4.
2. Thanh bắt đầu M5.1 và review A004. Khương bắt đầu M5.2.
3. Cập nhật trạng thái workbook. Nghiệm thu M4.2.
