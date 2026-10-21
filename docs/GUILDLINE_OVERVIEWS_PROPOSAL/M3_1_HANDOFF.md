# M3.1 — Gói đầu vào matched learned pilot

**Owner:** Khương. **Nguồn yêu cầu:** workbook
[POAI_Milestone_Group01_Hoan_Chinh.xlsx](POAI_Milestone_Group01_Hoan_Chinh.xlsx),
sheet `Milestones`, dòng 39. Dependency: D1.

M3.1 chốt cache/splits bất biến và kiểm chứng QARF/QPAF dùng cùng rows, thứ tự,
features và qrels. M3.2/M3.4 là các task huấn luyện riêng của Tấn Phát.

## Đầu vào kế thừa

| Task nguồn | Artifact được sử dụng |
| --- | --- |
| M2.1 — Thanh | Split manifest: 799 train, 171 validation, 172 frozen test |
| M2.8 sau A003 | Revision `m2.8-002`: raw scores và candidate set đã mở rộng, query texts, development qrels, sealed test qrels, split files và handover |
| M2.4 — Tấn Phát | Dataset, batching và feature path dùng trong pilot |
| M2.7 — Tấn Phát | Shared base, matched manifest và `input_binding.json`; revision 003 đã kiểm chứng hash và thứ tự batch thật |
| M2.10–M2.11 — Thanh | Audit replay và quyết định `m2.11-002`, D1 PASS |

`configs/m3.1/seal.json` pin SHA-256 của workbook chính thức, D1, input binding
và bằng chứng M2.7-003. Config không sửa các revision cũ.

## Nội dung kiểm chứng

1. Đối chiếu task/owner/dependency trực tiếp trong workbook và lineage D1.
2. Kiểm tra hash các input theo binding được D1 chấp nhận; copy sang namespace
   M3.1 mới. Giữ nguyên byte, không thay candidate policy hoặc tính lại retrieval.
3. Kiểm tra score schema chỉ có query/page IDs và ba scores; candidate keys/thứ tự
   khớp, split hashes/counts đúng M2.1, không trùng/mất query hoặc vượt cap 600.
4. Dùng hai lần load records độc lập qua cùng hợp đồng M2.4. Replay seed development
   `20260820`, 20 epoch × 50 batch train và một lượt validation cố định.
5. So sánh fingerprint theo từng batch cho query IDs/texts, page IDs, raw scores,
   normalized scores, 13 features, padding mask, labels và tổng positive trong qrels.
   Thứ tự batch train phải khớp cả bằng chứng M2.7-003.
6. Kiểm tra lại coverage train/validation. Test qrels chỉ được copy/hash dưới dạng
   bytes; không deserialize, dựng test records hoặc tính test ranking metric.

Không gọi model forward/backward hoặc optimizer trong seal/replay. Chỉ gate
granularity được phép khác nhau giữa các pilot; config và input còn lại được giữ
matched. Positive retrieval gain được đánh giá ở M3.5/G2, không suy ra từ M3.1.

## Môi trường và lệnh

Môi trường audit được ghi trong `manifest.json`. Matched runtime sử dụng
`requirements-learned-local.txt`; kiểm tra Torch phải đúng pin trong file đó.
`requirements/dev-local.txt` cung cấp các dependency kiểm chứng còn lại. Sau khi
cài dev-local, áp dụng lại matched requirements để dùng đúng Torch CPU:

```powershell
uv venv --python 3.13.7 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements/dev-local.txt
uv pip install --python .venv/Scripts/python.exe -r requirements-learned-local.txt
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
```

Các payload lớn không nằm trong Git. Chuẩn bị đúng đường dẫn/hash M2.8-002 đã
ghi trong `configs/m2.7/input_binding.json`. `--payload-root` cho phép lấy payload
từ một checkout khác có cùng cấu trúc đường dẫn. Thiếu hoặc sai hash thì dừng.

```powershell
# Đặt một tên namespace mới; thư mục đã tồn tại sẽ bị từ chối.
.venv/Scripts/python.exe scripts/seal_m31_inputs.py --output results/m3.1/<new-run-id>
```

Đầu ra gồm `inputs/` (payload local), `manifest.json`, `verification.json`,
`_ATTEMPTED.json` và `_SUCCESS.json`. Run lỗi giữ `failure.json` và không có marker
thành công. Payload copies không được commit; manifest/receipt có thể commit.

Trước pilot, lấy **manifest SHA-256 từ hồ sơ M3.1 đã review/commit**, rồi verify:

```powershell
.venv/Scripts/python.exe scripts/seal_m31_inputs.py `
  --verify results/m3.1/<sealed-run-id> `
  --expected-manifest-sha256 <hash-from-reviewed-evidence>
```

Verify không ghi file và không cần vị trí payload M2 ban đầu. Nó kiểm tra pin bên
ngoài, mọi sealed input, source hashes và numerical runtime, rồi replay parity.
Không lấy expected hash từ một manifest vừa bị thay đổi trong payload.

## Bàn giao cho các task sau

- **M3.2 — Tấn Phát:** dùng `inputs/shared_base.toml`, `score_cache.parquet`,
  `query_texts.json`, `qrels_development.json` và `inputs/splits/` của seal.
- **M3.3 — Thanh:** dùng manifest/pin để kiểm chứng lại đầu vào của QARF, sau đó
  kiểm chứng checkpoint/prediction/reload từ run M3.2.
- **M3.4 — Tấn Phát:** dùng lại đúng seal của QARF, sau independent QARF review.
- **M3.5 — Thanh:** có cơ sở paired comparison trên cùng query/candidate/features/qrels.
- **M3.6 — Khương:** có workload và hash cố định để kiểm tra integrity/resource.
- **M3.7/G2, M3.8/R3 — Tấn Phát:** dùng evidence này trong chuỗi truy nguồn quyết định.

M3.1 PASS là kết quả kiểm chứng đầu vào. Human review và authorization cho từng run
huấn luyện vẫn là các trạng thái riêng. Các test regression không là learned result.
