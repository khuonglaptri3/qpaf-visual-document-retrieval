# M5.3/R3 — technical review QPAF seed 20260821

**Owner review:** Thanh. **Kết quả kỹ thuật:** `PASS` trong [`validation.json`](validation.json).
**Thanh đã chấp nhận** trong [`owner_confirmation.json`](owner_confirmation.json) (câu trả lời
nguyên văn của Thanh, do Tấn Phát chuyển lại). Event `PASS` `QPAF-REG-20261026-0009` được ghi nối tiếp ở
[`governance_events.jsonl`](../m5.3-002/governance_events.jsonl). `validation.json` vẫn ghi
`PENDING_THANH_CONFIRMATION` vì hash của nó đã được ghim trước khi Thanh chấp nhận.

**Về tính độc lập:** Thanh nhờ (qua Tấn Phát) Claude Code làm technical review này. Claude Code cũng là
trợ lý đã soạn authorization, chạy run và viết first-pass check, nên đây **không phải** replay độc lập do
một người review khác thực hiện. Các phần tính metric, kiểm receipt và kiểm marker dùng lại helper M3.3
của Thanh. Phần nạp lại checkpoint QPAF, kiểm gate và báo cáo này do Claude Code viết. Thanh cần tự xem
và tự xác nhận bằng lời của mình trước khi event `PASS` được ghi.

[`audit_m5_qpaf.py`](../../../scripts/audit_m5_qpaf.py) kiểm:
- authorization (pin `132a1287…eaecd`), prereg M5.1, receipt M5.2, method freeze M4.3 và seal M3.1;
- run QARF seed 2 đã được chấp nhận (`QPAF-REG-20261026-0001`), và authorization chỉ khác run đó ở
  `--method`;
- ba marker giám sát và toàn bộ 16 output trong receipt.

Script chạy lại 41 kiểm tra first-pass và tính metric từ predictions cùng development qrels. Nó cũng so
data manifest, provenance và trang ứng viên với QPAF seed 1 (M3.4) và với QARF seed 2. Sau đó nó nạp
`best.pt` vào model QPAF dựng mới và dự đoán lại 171 query. Test labels không được đọc.

Metric tính lại khớp file run:

| Metric | Giá trị |
| --- | --- |
| nDCG@10 | `0.866252499336626` |
| Recall@1 | `0.7368` |
| Recall@3 | `0.9123` |
| MRR@10 | `0.8297` |

Sai khác khi nạp lại checkpoint là `0.0` (ngưỡng `1e-7`). Checkpoint được chọn là epoch 9. Gate theo
trang: trọng số 3 chiều có tổng bằng 1, và cả 171 query đều có trọng số thay đổi theo trang.

## Quan sát (không phải claim)

- Epoch được chọn: QARF là 1 ở mọi seed; QPAF là 19 (seed 1) và 9 (seed 2).
- nDCG validation của QARF ở epoch 2–20 bằng nhau tuyệt đối giữa seed 1 và seed 2.
- Giá trị được chọn là cực đại trên chính tập validation, nên không phải ước lượng test. Phép so sánh
  ghép cặp QPAF–QARF và gộp seed thuộc về M5.7.

## Replay

```powershell
.venv/Scripts/python.exe -X utf8 scripts/audit_m5_qpaf.py --task M5.3 --verify evidence/revisions/m5.3-r02/validation.json
```

`--verify` yêu cầu mọi trường khớp với file đã lưu. Riêng sai khác khi nạp lại chỉ cần nằm dưới ngưỡng,
vì giữa các máy có thể lệch khoảng 1e-16.
