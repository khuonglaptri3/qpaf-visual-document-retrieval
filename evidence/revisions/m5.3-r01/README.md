# M5.3/R3 — review độc lập QARF seed 20260821

**Owner review:** Thanh. **Kết quả kỹ thuật:** `PASS` trong
[`validation.json`](validation.json). Thanh đã chấp nhận phạm vi review này
trong [`owner_confirmation.json`](owner_confirmation.json); event `PASS` được
ghi nối tiếp ở [`governance_events.jsonl`](../m5.3-001/governance_events.jsonl).
Review này chỉ xét QARF seed 2 trên train/validation; không cấp quyền chạy
QPAF matched, mở test labels hay đưa ra claim nhiều seed.

[`audit_m53_qarf.py`](../../../scripts/audit_m53_qarf.py) kiểm SHA-256 của
authorization, prereg M5.1, receipt M5.2, method freeze M4.3, seal M3.1,
markers giám sát và toàn bộ 16 output trong receipt. Script chạy lại 35 kiểm
tra first-pass, tính metric độc lập từ predictions và development qrels, so
input/candidate order với seed 1, rồi nạp lại `best.pt` trong tiến trình review
và dự đoán lại 171 query. Dữ liệu test được giữ kín; seal verifier chỉ kiểm hash
file test như bytes, không đọc nhãn.

Seal M3.1 `PASS` (799 train, 171 validation; 82.255 trang ứng viên validation).
Metric validation tính lại khớp file run: nDCG@10 `0.7410159807755565`,
Recall@1 `0.5672514619883041`, Recall@3 `0.7777777777777778`, MRR@10
`0.6838438689315882`. Sai khác lớn nhất khi nạp lại checkpoint là
`3.3306690738754696e-16`, dưới ngưỡng `1e-7`; checkpoint cuối là epoch 20,
checkpoint được chọn là epoch 1. First-pass có 35 PASS, 0 FAIL.

Giá trị epoch 1 là cực đại chọn trên chính validation nên không phải ước lượng
test độc lập. Receipt M5.2 đạt kỹ thuật nhưng vẫn chờ owner nghiệm thu. Config
đóng băng và summary vẫn mang `experiment_id` M2.7; authorization và registry
gắn run thực với M5.3. Không suy ra cải thiện trước QPAF hay baseline.

Để replay, khôi phục 12 input M3.1 theo manifest SHA-256
`0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893`,
rồi dùng Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6,
PyArrow 26.0.0:

```powershell
python scripts/audit_m53_qarf.py --verify evidence/revisions/m5.3-r01/validation.json
```

Các input M3.1 đã khôi phục nằm ngoài Git; review không commit lại chúng.
