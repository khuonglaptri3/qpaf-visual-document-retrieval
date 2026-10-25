# M5.2 — Biên nhận cache cho ba seed

Owner: Khương. Roster: R2. Kết quả kỹ thuật: PASS; nghiệm thu/review của người
phụ trách vẫn `PENDING_USER_REVIEW`. Đây là data audit / engineering evidence,
không phải kết quả chất lượng QPAF hay authorization huấn luyện.

`cache_identity.json` SHA-256: `960aed613336e5f6faa8335881306ffc340bceff3094836eb6e3f135babc3291`.
Implementation commit: `a127eaedc557dabbe0b9b349eb13febfffe67132`.

Đã kiểm 1142 query, 551764 candidate rows;
split counts: {"test": 172, "train": 799, "validation": 171}.
Raw/normalized/candidate keys và thứ tự khớp; normalization sai khác tối đa
0.0. Sáu input replay (hai method × ba
seed 20260820/21/22) khớp theo từng cặp. Seed đầu khớp toàn bộ fingerprints
không nhãn của M3.1 qua 20 epoch train và một lượt validation. Đây là replay
dữ liệu, không thực hiện bước tối ưu hoặc model forward.

Cache/candidate order giữ nguyên. Shuffle train có thể khác giữa seed theo
RNG đã freeze; QARF/QPAF phải cùng batch order trong mỗi seed. Validation
giữ cùng stream cho mọi seed. 13 feature, loss/config/budget/evaluator đã
khóa không bị sửa. Nhãn development/test và checkpoint không được nạp.
ViMDoc chỉ kiểm seal ID; nguồn Parquet/qrels ngoài không được mở lại.
ViMDoc và benchmark ngoài tiếp tục deferred theo G2A.

## Chạy lại

Dùng Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6, PyArrow
26.0.0. Tải gói M4.2 theo `docs/06_handover/m4.2-baseline-handoff.md`, rồi:

```powershell
python scripts/verify_m52_cache_parity.py --restore-from-archive <M42.zip> --inputs-dir .cache/m52-inputs
python scripts/verify_m52_cache_parity.py --verify evidence/revisions/m5.2-001 --inputs-dir .cache/m52-inputs --expected-receipt-sha256 960aed613336e5f6faa8335881306ffc340bceff3094836eb6e3f135babc3291
```

Restore chỉ đọc mười ZIP member không nhãn, từ chối thư mục đã tồn tại.
Verify chỉ đọc, kiểm lại payload/source hashes và replay toàn bộ ma trận;
dùng receipt hash từ bản Git/PR đã review. Không dùng chế độ create để
ghi đè revision này. Chi tiết và giới hạn: `docs/06_handover/m5.2-cache-parity-handoff.md`.

Phát dùng đúng input hashes/config của receipt cho M5.3/M5.4 và xin
authorization riêng. QARF cần được review trước QPAF matched; checkpoint
reload/finite-output checks thuộc các task chạy seed. Không mở TEST-172 ở M5.2.
