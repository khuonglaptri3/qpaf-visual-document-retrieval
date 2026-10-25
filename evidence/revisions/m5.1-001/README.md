# M5.1 — Đăng ký trước kế hoạch ba seed và ablation

**Owner:** Thanh. **Roster:** R1, G2A core. **Trạng thái:** `ACCEPTED` qua
[`owner_confirmation.json`](owner_confirmation.json) và sự kiện
`QPAF-REG-20261025-0001` trong
[`governance_events.jsonl`](governance_events.jsonl). Bản
`preregistration.json` giữ nguyên trạng thái lúc tạo
`PREREGISTERED_PENDING_OWNER_SIGNOFF`; xác nhận được ghi thêm, không sửa record.
Nội dung được ghi trước các run M5.3/M5.4. Đây là kế hoạch quản trị, không cấp phép chạy model,
không dùng nhãn test/ViMDoc và không tạo kết quả khoa học.

[`preregistration.json`](preregistration.json) (SHA-256
`45269eafe36907f99990027f067e724939da69db5ee351669d1e5e7854bf7e29`)
pin G2A freeze `26d9bab6…3217`, xác nhận Research Lead `5f80b431…95e6`,
protocol/seed/statistics/baseline policy và scoped ViDoSeek contract. G2A giữ
QPAF-v1 với A001; A004 đã trượt gate, chưa được áp dụng. M5.1 không thay đổi
freeze M4.3/M4.7 hay các run M3/M4.

## Ma trận ba seed đã khóa

| Seed | QARF | QPAF | Task | Trạng thái |
| --- | --- | --- | --- | --- |
| `20260820` | M3.2 | M3.4 | pilot | Đã có, giữ nguyên |
| `20260821` | cùng seed | cùng seed | M5.3 / R3 | Chưa chạy |
| `20260822` | cùng seed | cùng seed | M5.4 / R4 | Chưa chạy |

M5.3 và M5.4 phải có receipt M5.2 về cùng cache/rows/order, authorization riêng
cho từng run, và QARF được review trước QPAF matched. Ngoài
`training.seed` và `gate_granularity` theo method, config, 13 feature, loss,
optimizer, budget, phần cứng, evaluator và thứ tự dữ liệu phải matched. Mỗi
checkpoint phải qua kiểm finite output và fresh-process reload sai khác
`<= 1e-7`; mọi seed hợp lệ đều được báo, không chọn seed tốt nhất hoặc thay seed
sau khi xem metric. Run không hợp lệ cần independent review và amendment mới
trước khi thay thế.

## Thứ tự kiểm tra một yếu tố — chỉ validation

Các phép dưới đây là **diagnostic**, so với reference đầy đủ trên cùng candidate
pool. Chúng không thay thế QPAF-v1, strongest baseline hoặc các checkpoint đã
freeze. Mỗi run mới vẫn cần authorization của task sở hữu nó.

| Thứ tự | Task | Một yếu tố thay đổi |
| ---: | --- | --- |
| 1 | M5.5 / R5 | Đối chiếu ba retriever singleton BM25, BGE-M3, ColQwen2.5 đã có trên cùng candidate pool; không fit lại. |
| 2 | M5.5 / R5 | Bỏ lần lượt một kênh khỏi uniform CombSUM; hai kênh còn lại giữ trọng số `0.5/0.5`, cùng normalized-score cache. |
| 3 | M5.5 / R5 | Chỉ uniform CombSUM: min–max đã freeze so với z-score theo query trên raw scores (`ddof=0`, kênh phương sai 0 cho điểm 0); trọng số vẫn `1/3` mỗi kênh. |
| 4 | M5.5 / R5 | Đo latency và memory của checkpoint QARF/QPAF đã freeze, tách chi phí retriever khỏi fusion. |
| 5–8 | M5.6 / R6 | Từ bản 13 feature đầy đủ, lần lượt bỏ **một nhóm mỗi run**: ba rank, ba gap, ba disagreement, rồi `query_length`; không cộng dồn. |
| 9 | M5.6 / R6 | So query-level với page-level bằng output QARF/QPAF matched; chỉ `gate_granularity` khác nhau. |

Các model diagnostic của R6 dùng seed `20260820`, cùng train/validation, nguồn,
loss và training budget của pilot, lưu checkpoint riêng. Chúng không được vào
TEST-172 hoặc đổi primary. Thứ tự này chốt **sau** khi nhóm đã thấy validation
M4.4/M4.5; vì vậy ablation vẫn là phân tích khám phá, không phải phép thử xác
nhận độc lập.

## Luật drop-first và claim

Lõi **R1–R4, R7, R8 không được cắt**. Nếu lịch hoặc compute đã được duyệt không
đủ cho cả hai task optional trong khi vẫn giữ lõi, ghi budget/deadline và lý do
**trước khi xem kết quả diagnostic hoặc mở TEST-172**, rồi bỏ **R6 trước, R5
sau**. Mỗi mục bỏ phải ghi `NOT_RUN` cùng tác động lên claim. R9/R10 vẫn ở
trạng thái deferred của G2A, không được tự nâng lên core. Nếu không đo được
latency/memory theo policy, không được tuyên bố đạt operational gate dù chất
lượng nghiên cứu có thể được báo riêng.

R7 chỉ được mở ViDoSeek test **172 query một lần**, sau khi R3/R4 được review
độc lập: bảy baseline deployable, QARF ×3, QPAF ×3, W7/W66 chỉ là oracle
context. Không dùng test để chọn seed, checkpoint, baseline hay method. R8/M5.7
tính mean delta của ba seed **theo từng query trước**, rồi bootstrap paired trên
172 query (10.000 lần, RNG `default_rng` seed `20260820`, CI percentile 95%),
W/T/L và gain concentration. Phép thử quyết định vẫn gồm QPAF so với matched
QARF **và** `train_fitted_static`; metric phụ hoặc ablation không cứu được
primary failure.

## Kiểm tra read-only

```powershell
python scripts/preregister_m51.py --verify evidence/revisions/m5.1-001
python -m unittest tests.test_m51_preregistration -q
```

Verifier chỉ đọc các policy và G2A record đã pin, rồi kiểm hash của xác nhận và
sự kiện; không tải corpus, mở nhãn, huấn luyện hoặc chạy evaluation. Review
A004 của Thanh là việc riêng, chưa được hoàn tất bằng xác nhận M5.1 này.
