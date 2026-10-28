# M5.10 / G3A — Giới hạn kết luận tổng quát hóa

**Owner:** Thanh. **Quyết định:** `NOT_RUN` (`NOT_RUN_DEFERRED`), được
Thanh chấp nhận trong `owner_confirmation.json`; event
`QPAF-REG-20261028-0006` nằm trong `governance_events.jsonl`.
Workbook dòng 66 cho phép G3A kết thúc bằng `PASS`, `INCONCLUSIVE`,
`NEGATIVE` hoặc `NOT RUN`. Không có một run external đã được authorize và
kiểm chứng, nên trạng thái đúng là **NOT RUN**. `INCONCLUSIVE` hoặc `NEGATIVE`
sẽ ngụ ý đã có kết quả external để đánh giá.

## Bằng chứng ràng buộc

- M5.9/G3 đã được Research Lead xác nhận `LIMITED-CLAIM` vì QPAF không vượt
  `train_fitted_static` trên ViDoSeek TEST-172 và latency gate chưa đạt quy tắc
  ít nhất 1.000 query đo.
- M5.8/R9 ghi external benchmark `NOT_RUN_DEFERRED`; không có authorization
  hoặc kết quả external được nghiệm thu.
- G2A ghi ViMDoc confirmation `NOT_RUN_DEFERRED` vì chưa có score cache đã
  kiểm chứng. ViDoRe V3 là optional sealed external validation; không được
  thay thế bằng benchmark khác hoặc mở nhãn để điều chỉnh mô hình.
- M5.7/R8 chỉ bao gồm ba seed trên ViDoSeek TEST-172. So sánh QPAF với QARF
  matched dương; so sánh với baseline mạnh nhất âm.

### Cache ViDoRe P0-03 cũ

Repo **có** `data/raw_scores.parquet` và `data/cache/retrieval_scores.parquet`:
[`artifacts/extraction_manifest.json`](../../../artifacts/extraction_manifest.json)
ghi 309 query tiếng Anh, 140.083 dòng ứng viên và hash file; preflight P0-03
đã PASS cho phạm vi bundle đó. Vì vậy câu “không có score cache” nói chung là
không chính xác.

P0-03 không phải bằng chứng sealed R9/M5.8: file score chứa cột relevance;
[`scripts/extract_vidore_baseline.py`](../../../scripts/extract_vidore_baseline.py)
đã đọc qrels để quyết định mở rộng độ sâu ứng viên theo coverage; và
[`artifacts/baseline_metrics.json`](../../../artifacts/baseline_metrics.json)
ghi rõ metric chỉ kiểm candidate pool, không phải kết quả benchmark official
full corpus. Chưa có authorization R9, run QPAF-v1 external được niêm phong và
review nghiệm thu. `NOT RUN` nói về **run R9 hợp lệ**, không phủ nhận cache P0-03
cũ. ViMDoc thiếu cache đã kiểm chứng là một vấn đề riêng được ghi trong G2A.

`inputs.json` pin byte của năm file đầu vào. `scripts/decide_g3a.py` kiểm pin
và nội dung trước khi tạo hoặc replay `decision.json`. Nó chỉ đọc governance
records, không đọc nhãn, chạy evaluation, huấn luyện hay cấp quyền chạy mới.

## Ranh giới kết luận

Được báo cáo: QPAF-v1 vượt QARF-v1 matched trên ViDoSeek TEST-172 ở ba seed đã
đăng ký. Phải báo cáo cùng lúc kết quả âm so với baseline `train_fitted_static`
và việc latency gate chưa được xác lập. **Không có bằng chứng để kết luận QPAF
tổng quát hóa sang ViMDoc hoặc benchmark external.** G3A không thay đổi quyết
định `LIMITED-CLAIM` của G3.

Owner signoff được ghi ở file riêng, không sửa `decision.json` đã pin.

## Kiểm chứng

```powershell
python scripts/decide_g3a.py --inputs evidence/revisions/m5.10-001/inputs.json --output evidence/revisions/m5.10-001/decision.json --verify
python -m unittest tests.test_m510_g3a -q
```
