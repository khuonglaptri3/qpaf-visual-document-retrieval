# M5.4/R4 — technical review QPAF seed 20260822

**Owner review:** Thanh. **Kết quả kỹ thuật:** `PASS` trong [`validation.json`](validation.json).
**Thanh chưa chấp nhận:** chưa có `owner_confirmation.json` và chưa có event `ACCEPTANCE_RECORDED`.

**Về tính độc lập:** giống [`m5.3-r02`](../m5.3-r02/README.md). Claude Code làm review này theo yêu cầu
của Thanh (qua Tấn Phát), và cũng là trợ lý đã chạy run. Vì vậy Thanh cần tự xem và tự xác nhận bằng lời
của mình.

[`audit_m5_qpaf.py`](../../../scripts/audit_m5_qpaf.py) chạy cùng các kiểm tra như M5.3 cho:
- authorization `1d7e64d3…f845`;
- run QARF seed 3 đã được chấp nhận (`QPAF-REG-20261026-0002`);
- QPAF seed 1 (M3.4).

Kết quả: 41 kiểm tra first-pass đều PASS, 16 output đã hash lại, metric tính lại khớp file run:

| Metric | Giá trị |
| --- | --- |
| nDCG@10 | `0.8678608672449859` |
| Recall@1 | `0.7368` |
| Recall@3 | `0.9064` |
| MRR@10 | `0.8287` |

Sai khác khi nạp lại checkpoint là `0.0`. Checkpoint được chọn là epoch 20, cũng là epoch cuối. Gate
theo trang: cả 171 query đều có trọng số thay đổi theo trang.

## Quan sát (không phải claim)

- Epoch được chọn: QARF là 1 / 1 / 1; QPAF là 19 / 9 / 20 (seed 1 / 2 / 3).
- nDCG validation của QARF ở epoch 2–20 bằng nhau tuyệt đối ở cả ba seed.
- Seed 3 chọn epoch cuối, nên không biết nDCG có còn tăng nếu train thêm hay không. Ngân sách 20 epoch đã
  được đóng băng ở M5.1, và đây chỉ là quan sát để xét ở M5.7.

## Replay

```powershell
.venv/Scripts/python.exe -X utf8 scripts/audit_m5_qpaf.py --task M5.4 --verify evidence/revisions/m5.4-r02/validation.json
```
