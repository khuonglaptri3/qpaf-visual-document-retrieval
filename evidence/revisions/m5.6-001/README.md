# M5.6-001 — R6 feature-group và query-vs-page ablation (chỉ validation)

**Owner:** Tấn Phát. **Trạng thái:** run `SUCCESS`, post-run check 15 PASS / 0 FAIL
kèm lệch **D1** (xem dưới); review độc lập (Thanh) `PENDING`. Kết quả là chẩn đoán
khám phá: thứ tự ablation chốt sau khi nhóm đã thấy validation M4.4/M4.5 (M5.1).

- [`authorization.json`](authorization.json): pin
  `a89efaf416dc306dfc0bd09dd5bb1201d81c382dd0429dad6efd42fa99e1be98`, duyệt
  2026-10-27T16:46:35Z. `approval_text` là nguyên văn lời duyệt của Research Lead
  trong phiên làm việc, Claude Code ghi theo yêu cầu.
- Implementation `4330e631079d23b6fdd7e4417f1104584fe6bc60`; execution HEAD
  `c1da4f37f83ef9dcf1157c75c33af75ae0fb9170` (sau implementation chỉ đổi authorization).
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261027-0007`
  (AUTHORIZED), `0008` (STARTED), `0009` (VERIFICATION_RECORDED, vẫn `STARTED`).
- Run: [`RUN-QPAF-M5_6-ABL-001-20261027T164635Z-A01`](../../../results/m5.6/RUN-QPAF-M5_6-ABL-001-20261027T164635Z-A01/report.md),
  manifest `be69197b8fb1d724d86f0bcdde729c365d69638b63e8088adff38defa2630706`
  (39 file + 3 marker), 373 s CPU.
- [`post_run_check.py`](post_run_check.py) →
  [`post_run_verification.json`](post_run_verification.json)
  (`8434b05f5a8c38af4eb98e489feb13346161a21b9dd7fab1381a8dc12c9f4e7c`).

## Cách ablation giữ đúng "một yếu tố"

Gate pilot là `nn.Linear(13, 3)`. Cột feature bị bỏ được nhân 0 trước gate; trọng số
còn lại khởi tạo đúng như pilot, trọng số của cột bị bỏ nhận gradient 0 và được kiểm
là **không đổi** sau train (cả 4 run). Seed `20260820`, config M3.1 sealed, loss,
optimizer, 20 epoch, chọn epoch theo validation nDCG@10 — giống pilot. **R6-00**
(đủ 13 feature) là control thêm vào: tái tạo pilot M3.4 với sai khác dự đoán `0.0`,
cùng epoch 19. Reload checkpoint trong process mới: sai khác `0.0` cho cả 5 run.

## Kết quả (171 query validation)

| Run | Bỏ nhóm | Epoch | nDCG@10 | Δ so với R6-00 | 95% CI | W/T/L |
| --- | --- | ---: | ---: | ---: | --- | --- |
| R6-00 | — | 19 | 0.866280 | — | — | — |
| R6-01 | rank (3) | 19 | 0.865805 | −0.000475 | [−0.006412, +0.004994] | 3/166/2 |
| R6-02 | gap (3) | 11 | 0.866658 | +0.000378 | [−0.004469, +0.004924] | 4/165/2 |
| R6-03 | disagreement (3) | 7 | 0.866479 | +0.000199 | [−0.004517, +0.004480] | 5/163/3 |
| R6-04 | `query_length` | 19 | 0.867970 | +0.001690 | [+0.000000, +0.005071] | 1/170/0 |

Không nhóm feature phụ nào tạo khác biệt đáng kể: ≥163/171 query không đổi, mọi
CI chứa hoặc chạm 0. R6-04 chỉ khác ở **một** query, nên cận dưới CI bằng 0 không
phải bằng chứng cải thiện. Giá trị tuyệt đối lạc quan vì epoch được chọn trên chính
validation.

**R6-05 — QPAF (page) − QARF (query)**, 6 run matched đã được chấp nhận, không train:

| Seed | QARF | QPAF | ΔnDCG@10 | 95% CI | W/T/L |
| --- | ---: | ---: | ---: | --- | --- |
| 20260820 | 0.752147 | 0.866280 | +0.114132 | [+0.077501, +0.152040] | 57/101/13 |
| 20260821 | 0.741016 | 0.866252 | +0.125237 | [+0.087669, +0.163770] | 59/101/11 |
| 20260822 | 0.751118 | 0.867861 | +0.116743 | [+0.079825, +0.154720] | 58/100/13 |
| Trung bình 3 seed theo query | | | **+0.118704** | [+0.081876, +0.156545] | 61/97/13 |

Metric tính lại từ prediction + qrels development khớp CSV/summary của từng run
(sai khác `0.0`). Đây là so sánh validation; không thay R7/R8 trên TEST-172.

## Lệch D1 — bản chép authorization trong run

`runner.verify` từ chối ngay bước đầu: `authorization.json` được commit với CRLF
(`-text`), còn runner chép nó bằng `read_text`/`write_text(newline='\n')` nên bản
trong run (`e3270e2b…4789`) là đúng byte đã pin sau khi đổi CRLF→LF. Manifest,
`_ATTEMPTED.json` và pin ngoài đều là `a89efaf4…`. Không sửa output hay runner (cả
hai đã bị pin); `post_run_check.py` chạy lại mọi bước còn lại của `verify` bằng chính
các hàm đã pin và kiểm D1 một cách tường minh. Không ảnh hưởng train, checkpoint,
prediction hay thống kê. Reviewer quyết định có chấp nhận D1 hay không.

## Kiểm tra lại

```powershell
.venv/Scripts/python.exe evidence/revisions/m5.6-001/post_run_check.py
.venv/Scripts/python.exe -m unittest tests.test_m56_ablations -q
```

Cần M3.1 sealed inputs tại đường dẫn gốc và runtime Python 3.13.7, Torch 2.11.0+cpu,
NumPy 2.5.4, pandas 3.0.6, PyArrow 26.0.0.
