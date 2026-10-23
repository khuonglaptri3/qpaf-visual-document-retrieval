# R3 — Báo cáo tiến độ Sprint 3 (M3.8)

**Người báo cáo:** Tấn Phát (Research Lead). **Ngày:** 2026-10-23.
**Sprint 3 (M3):** Matched Learned QARF vs QPAF Pilot, kế hoạch 2026-10-12 → 2026-10-25.
Mọi số liệu dưới đây lấy từ các file bằng chứng trong repo, có dẫn đường link.

## 1. Kết luận

**G2 = GO → nhánh M4 `continue_qpaf`.** Trên seed phát triển `20260820`, learned QPAF
vượt learned QARF matched ở cả 4 metric trên 171 query validation, với cận dưới CI95
dương. Mọi ngưỡng vận hành (latency, CUDA, reload) đều đạt.

| | Giá trị |
| --- | --- |
| nDCG@10 QARF → QPAF | 0,7521 → 0,8663 |
| Mean delta nDCG@10 | **+0,1141**, CI95 [+0,0775, +0,1520] |
| Thắng / hòa / thua (nDCG@10) | 57 / 101 / 13 |
| Tỷ lệ gain thuộc top 5% query | 0,281 (ngưỡng < 0,90) |

GO **chỉ cho phép xin** authorization cho seed `20260821` / `20260822` và các task M4.
Đây không phải claim cuối cùng 3 seed, chưa so với baseline và chưa đụng tới test.

## 2. Tiến độ theo task

| Task | Nội dung | Owner | Kết quả | PR |
| --- | --- | --- | --- | --- |
| M3.1 | Chốt (seal) đầu vào pilot, kiểm row parity | Khương | PASS kỹ thuật | #23 |
| M3.2 | Chạy learned QARF pilot | Tấn Phát | Chạy xong, 30/30 kiểm tra first-pass | #25 |
| M3.3 | Kiểm định độc lập run QARF | Thanh | PASS, Thanh ACCEPTED | #26 |
| M3.4 | Chạy learned QPAF pilot matched | Tấn Phát | Chạy xong, 39/39 kiểm tra first-pass | #27 |
| M3.5 | So sánh QPAF–QARF theo query | Thanh | PASS, Thanh ACCEPTED | #28 |
| M3.6 | Toàn vẹn output và tài nguyên | Khương | PASS (m3.6-006), Khương + Thanh ACCEPTED | #29, #30 |
| M3.7 | Quyết định G2 | Tấn Phát | **GO**, gate owner xác nhận | #31 (đang mở) |
| M3.8 | Báo cáo R3 | Tấn Phát | Tài liệu này | — |

M3.1 hoàn tất ngày 2026-10-21, M3.2–M3.7 trong 2026-10-22 → 23. So với kế hoạch
(M3.1: 12–13/10, M3.2: 14–16/10), các task đầu trễ khoảng một tuần, nhưng cả sprint vẫn
kết thúc trước hạn 25/10.

## 3. Bằng chứng chính

**Run pilot** (cùng seed `20260820`, 20 epoch, 42 tham số, test split không mở):

| Run | Epoch chọn | nDCG@10 | Recall@1 | Recall@3 | MRR@10 |
| --- | --- | --- | --- | --- | --- |
| QARF `RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01` | 1 | 0,7521 | 0,5848 | 0,7836 | 0,6969 |
| QPAF `RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01` | 19 | 0,8663 | 0,7368 | 0,9064 | 0,8283 |

**So sánh paired M3.5** ([`comparison.json`](../evidence/revisions/m3.5-001/comparison.json),
bootstrap 10.000 lần theo query; replay khớp với sai khác 0,0):

| Metric | Mean delta | CI95 | Thắng / hòa / thua |
| --- | --- | --- | --- |
| nDCG@10 | +0,1141 | [+0,0775, +0,1520] | 57 / 101 / 13 |
| Recall@1 | +0,1520 | [+0,0819, +0,2222] | 33 / 131 / 7 |
| Recall@3 | +0,1228 | [+0,0643, +0,1813] | 25 / 142 / 4 |
| MRR@10 | +0,1314 | [+0,0869, +0,1776] | 57 / 101 / 13 |

**Toàn vẹn và tài nguyên M3.6:**
- Integrity ([`m3.6-001`](../evidence/revisions/m3.6-001/integrity_review.json)): output hữu
  hạn; reload checkpoint trong tiến trình mới cho sai khác 0,0.
- GPU A10, giới hạn RAM 5 GiB ([`m3.6-004`](../evidence/revisions/m3.6-004/technical_review.json)):
  median latency fusion online QARF 2,486 ms, QPAF 2,447 ms (ngưỡng ≤ 10 ms); peak CUDA
  0,0324 / 0,0325 GiB (ngưỡng < 1,5 GiB).
- Bộ nhớ CPU ([`m3.6-006`](../evidence/revisions/m3.6-006/technical_review.json)): probe cho
  thấy Modal OOM-kill container khi vượt giới hạn, nên A02 dùng dưới 4.096 MiB và A03 dưới
  5.120 MiB. Đây là cận trên, peak chính xác không đo được.

**Quyết định G2** ([`decision.json`](../evidence/revisions/m3.7-001/decision.json), SHA-256
`888c51d5…d621`): 13/13 kiểm tra PASS, các file đầu vào pin SHA trong
[`inputs.json`](../evidence/revisions/m3.7-001/inputs.json); gate owner xác nhận trong
[`owner_confirmation.json`](../evidence/revisions/m3.7-001/owner_confirmation.json).

## 4. Vấn đề phát sinh và cách xử lý

1. **Blocker bộ nhớ M3.6 (`M3_6_CPU_RSS_ACCOUNTING_001`).** Ở giới hạn 4 GiB, RSS đo trong
   gVisor là ~4,87 GiB nhưng run không bị OOM; telemetry Modal chỉ ~0,9 GiB. gVisor trên GPU
   không cung cấp bộ đếm peak, nên không đo được peak thật. Xử lý: chứng minh Modal cưỡng chế
   giới hạn bằng probe 2 control (2.048 MiB chạy xong; 4.608 MiB bị kill 8/8 lần với
   `exit code 137`). Probe chỉ cấp phát bộ nhớ giả, không chạm dữ liệu hay mô hình.
2. **Ba quyết định post hoc, đã công khai:**
   - [m3.6-005](../evidence/revisions/m3.6-005/criteria_revision.md): đổi bằng chứng bộ nhớ
     từ "peak" sang "cận trên do Modal cưỡng chế", sau khi thấy A02/A03.
   - [m3.6-006](../evidence/revisions/m3.6-006/criteria_revision.md): tính dòng log
     `Runner killed (SIGKILL)` của Modal là provider exit reason, sau khi classifier đã pin
     trả `INCONCLUSIVE`. Review BLOCKED của m3.6-005 được giữ nguyên.
   - [m3.7-001](../evidence/revisions/m3.7-001/criteria.md): quy tắc G2 một seed, viết sau khi
     biết kết quả M3.5, nhưng không thêm ngưỡng mới mà áp nguyên ngưỡng 3 seed đã đóng băng.

   Không quyết định nào thay đổi mô hình, dữ liệu, seed, metric hay ngưỡng của nghiên cứu.
   m3.6-005/006 được Thanh nghiệm thu QA ở PR #30.

## 5. Hạn chế và tồn đọng

1. **Một seed, chọn checkpoint trên chính validation dùng để so sánh**, nên kết quả lạc quan.
   Validation nDCG@10 của QARF đạt đỉnh ở epoch 1 rồi giảm; QPAF đạt đỉnh ở epoch 19.
2. Chưa có so sánh baseline, chưa có dữ liệu confirmation hay test.
3. **PR #31 (M3.7) chưa merge** vào `develop`.
4. Hồ sơ M3.1 trong repo vẫn ghi `independent_human_review: PENDING`
   ([`verification.json`](../evidence/revisions/m3.1-001/verification.json)), dù PR #23 đã merge.
5. `summary.json` và config đóng băng của M3.2/M3.4 vẫn ghi `experiment_id = QPAF-M2_7-MTH-001`,
   khác với namespace run `QPAF-M3_x`; giữ nguyên để không phá hash.
6. Probe bộ nhớ chạy ở workspace Modal `buiphat251399`, còn A02/A03 ở `tranthanhzt123321`.
7. Toàn bộ test suite: 23 test M1/M2 cũ lỗi do hash drift fixture (ví dụ `configs/datasets.yaml`),
   lỗi y hệt trên `develop`; mọi test M3 đều PASS (ghi ở PR #30).
8. Trạng thái trong workbook `POAI_Milestone_Group01_Hoan_Chinh.xlsx` chưa được cập nhật
   (M3.x vẫn ghi Not Started / Blocked).

## 6. Kế hoạch Sprint 4 (M4, 2026-10-26 → 2026-11-08)

| Task | Nội dung | Owner | Thời gian |
| --- | --- | --- | --- |
| M4.1 | Đóng băng quyền truy cập confirmation và hash đánh giá | Thanh | 26–27/10 |
| M4.2 | Đóng băng đầu vào baseline và thiết lập train-only | Khương | 26–28/10 |
| M4.3 | Thực thi nhánh G2 đã chốt (`continue_qpaf`) | Tấn Phát | 28/10–02/11 |
| M4.4 | Đánh giá baseline triển khai được, đầy đủ | Tấn Phát | 03–05/11 |
| M4.5 | Kiểm định độc lập tính công bằng baseline và độ bất định | Thanh | 05–06/11 |
| M4.6 | Chốt hướng phương pháp chính | Tấn Phát | 06/11 |
| M4.7 | G2A — chốt lộ trình robustness | Tấn Phát | 06/11 |
| M4.8 | R4 — báo cáo tiến độ Sprint 4 | Tấn Phát | 05–06/11 |

Việc cần làm ngay:
1. Merge PR #31 (M3.7).
2. Lập authorization cho seed `20260821` và `20260822` (QARF và QPAF matched); mỗi run cần
   duyệt riêng.
3. Ghi bổ sung review M3.1 và cập nhật trạng thái workbook.
