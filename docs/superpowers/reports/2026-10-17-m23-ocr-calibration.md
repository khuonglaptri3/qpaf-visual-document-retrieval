# M2.3 — Dữ liệu hiệu chuẩn OCR và bàn giao review

**Ngày:** 2026-10-17.
**Đã hoàn tất:** COMPLETE_BOUNDED_CALIBRATION, policy vận hành FROZEN tại
[m2.3-002](../../../evidence/revisions/m2.3-002/README.md). Xem
[nghiên cứu và quyết định cuối](2026-10-17-m23-research-and-final-decision.md).
Các trạng thái chờ review bên dưới là lịch sử của đợt chạy/nhận dữ liệu.

**Cập nhật mới nhất:** đã sửa theo ảnh/xác nhận đủ 18 bản chữ theo chỉ dẫn
người dùng; còn 8 kết luận native và quyết định ngưỡng. Xem
[báo cáo QA hoàn tất](2026-10-17-m23-reference-qa-completed.md) và
[giao diện có sẵn bản sửa](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/index.html#reference).
Các trạng thái nhận file ban đầu bên dưới là lịch sử.

**Cập nhật sau bàn giao:** đã nhận JSON của Khuong; còn 8 native và 41
references, trạng thái `HUMAN_REVIEW_INCOMPLETE`. Xem
[tổng hợp review thủ công](2026-10-17-m23-human-review-summary.md).
Các số liệu và trạng thái bên dưới ghi nhận thời điểm bàn giao dữ liệu.

**Trạng thái:** `DATA_READY_REVIEW_PENDING` — đã triển khai và chạy dữ liệu thật;
chưa hoàn thành nghiệm thu chất lượng M2.3, chưa đóng băng ngưỡng.

**Run chọn:** `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`.
**Giao diện:** [mở review dữ liệu thật](../../../results/m2.3/review/index.html).
**Runbook:** [lệnh và cách bàn giao JSON](../../../results/m2.3/README.md).

## 1. Dữ liệu đã chuẩn bị

| Thành phần | Kết quả |
|---|---:|
| Mẫu chính | 30 PDF / 120 trang |
| Development | 20 PDF / 80 trang |
| Holdout độc lập theo PDF | 10 PDF / 40 trang |
| Ca regression M2.2 | 1 trang / 1 PDF khác |
| Tổng trang cần review native | **121** |
| Bản chữ toàn trang bắt buộc | **41**: 30 dev +10 holdout +1 regression |
| OCR attempts | **242**: mỗi trang ở 150 và 300 DPI |
| Lỗi kỹ thuật ở run chọn | **0** |
| Source/page/asset verification | **VERIFIED_ENGINEERING_DATA** |

Mẫu dùng ID/hash, số trang và bounded native-text probes, không dùng qrels hoặc
test queries để chọn/configure. PDF thuộc corpus dùng chung, không coi là
document-disjoint theo query splits của M2.1. Tài liệu ngắn được oversample;
trang đầu/cuối/sparse/rich được ưu tiên nên tỷ lệ lỗi gộp không phải ước lượng
không chệch của corpus. Nhãn lĩnh vực/bố cục chưa được người kiểm tra xác nhận.

Native tự động có 99 trang text_present, 16 short và 6 empty. Đây là tín hiệu
chọn mẫu, chưa phải kết luận đúng/sai hoặc xác nhận trang không có chữ.

## 2. OCR và tài nguyên đo thật

Engine: Tesseract 5.3.0, Leptonica 1.82.0, eng, OEM 3 / PSM 3,
không preprocessing; cùng traineddata SHA-256 ở cả hai DPI:
`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
PDF parser 4.30.0; chi tiết runtime trong `remote/environment.json`.

| Chỉ số | 150 DPI | 300 DPI |
|---|---:|---:|
| Attempts hoàn tất | 121 | 121 |
| Có từ nhận dạng (`OK`) | 118 | 118 |
| Không nhận ra từ (`NO_TEXT_DETECTED`) | 3 | 3 |
| OCR time trung bình/attempt | 0.860 s | 1.577 s |
| P50 | 0.567 s | 1.011 s |
| P95 | 2.121 s | 3.895 s |
| P99 | 4.846 s | 6.611 s |
| Max | 5.042 s | 7.329 s |
| Peak RSS subprocess Tesseract đo được | 152.19 MiB | 433.80 MiB |

Hai mức DPI cùng không nhận ra từ trên ba trang:

- `00d8d22ded241c20c75d49578359057cd25739d1_page_0023`.
- `03244446f5499b38d84fb09e3ba09f995eb0692a_page_0001`.
- `048ce9cbabf9b58c9764e8be143b7196b5478ac1_page_0007` (regression M2.2).

Chưa tự coi ba trang trên là không có chữ; người review xác nhận bằng ảnh.
`OK` cũng chỉ xác nhận có output kỹ thuật, không đồng nghĩa chữ đúng.

Wall-time worker **285.917 s**, trong đó render **131.058 s**; tổng thời gian
OCR attempts 294.846 s được xử lý với 2 workers nên không cộng trực tiếp vào
wall-time. Peak RSS Python + descendants **1281.48 MiB (~1.25 GiB)**, lấy mẫu
20 ms. Output worker khoảng **301.16 MiB**. Không GPU, OOM hoặc timeout.

Các số trên không gồm local preparation, upload, build/start container,
fetch/download, chờ logs hoặc dựng HTML. P99 từ mẫu nhỏ chỉ là số đo tham khảo.
300 DPI tốn khoảng 1.83 lần thời gian OCR trung bình của 150 DPI trên mẫu;
chưa kết luận mức DPI nào có chất lượng tốt hơn trước human reference.

## 3. Điều chỉnh có lưu lịch sử

| Run suffix | Trạng thái | Ý nghĩa |
|---|---|---|
| `101052Z-A01` | Prepare-only, chưa execute | Chuẩn bị đầu tiên; tạo run mới sau khi hoàn thiện normalization backend |
| `101215Z-A01` | DATA_READY_WITH_ERRORS_REVIEW_PENDING | Cap 32M pixels làm 8 trang không render được 300 DPI; 226 attempts, lưu đủ lỗi |
| **`101949Z-A01`** | **DATA_READY_REVIEW_PENDING** | Cap 40M, pixel projection preflight; cùng mẫu/model/command, đủ 242 attempts |

Tám trang thuộc hai PDF vuông cần 36.0–36.013M pixels ở 300 DPI. Protocol v2
nâng cap render lên 40M, giữ RAM 4096 MiB, không đổi ngưỡng chất lượng hoặc
downsample ngầm. Đã so IDs/native/PDF hashes/reference subset/splits với parent,
tất cả giống nhau. Hai lượt và lỗi ban đầu được giữ nguyên.

Client báo chờ final app logs bị timeout ở cuối lượt v2; worker đã hoàn tất,
artifact đã tải về và xác minh hash thành công. Đây không phải OCR timeout.

## 4. Code nào tạo dữ liệu và chỉ số?

| File / hàm | Đầu ra |
|---|---|
| `scripts/run_m23_calibration.py` | Entry point, source snapshot, điều phối Modal, fetch, verification và HTML |
| `src/qpaf/m23/sample.py::prepare_sample()` | Khóa sample IDs/splits, source PDF/native hashes, pixel preflight |
| `worker.py::runtime_identity()` | Engine, dependencies, traineddata identity |
| `worker.py::execute()` | Ảnh 150/300 DPI và trạng thái run, source verification |
| `worker.py::run_ocr()` | Lệnh Tesseract thật, txt/TSV/stderr, latency và RSS subprocess |
| `worker.py::MemoryMonitor` | RSS Python + subprocesses, không dùng telemetry Torch của M2.2 |
| `review.py::build_review()` | HTML dữ liệu thật và namespace hash |
| `review.py::validate_reviews()/summarize()` | Nhập human export, kiểm tra identity, CER/WER và coverage |

Trong `results/m2.3/<run-id>/`: `inputs/` giữ mẫu gốc; `remote/pages.json` giữ
native và hai output OCR từng trang; `remote/ocr/<dpi>/` giữ raw txt/TSV;
`resources.json`, `errors.json`, `environment.json`, `summary.json`, `hashes.json`
cho từng lớp bằng chứng. PDFs/ảnh/raw OCR/HTML được sinh nằm ngoài Git.

Volume: `qpaf-m23-ocr-artifacts`, `runs/<run-id>/output/`. Local đã tải đủ payload
để verify và review. `source.json` + `source_snapshot.zip` nhận diện bytes code
chưa commit; không dùng Git base một mình để đại diện toàn implementation.

Giao diện hiện hành có sửa navigation sau run: khi lọc 41 trang tham chiếu,
Trang tiếp/Trang trước chỉ đi trong bộ lọc, tự chọn trang khớp. Không thay OCR
hay sample hash; template lúc run giữ trong source snapshot, template bàn giao
được nhận diện riêng trong `review/workspace.json` và revision kỹ thuật.

## 5. Kiểm chứng

- 13 unit/integration tests M2.3 PASS: sampling disjoint/deterministic, bound,
  UTF-8/NFC, exact edit-distance đối chiếu 300 random DP cases, TSV confidence,
  timeout dừng subprocess thật, review import/coverage và không tự freeze.
- Receipt: `results/m2.3/verification/tests-v2-2026-10-17.json`; source Python
  khớp run và không đổi trong thời gian kiểm thử.
- 6 nhóm browser checks dữ liệu thật PASS, gồm ảnh local, 121/41 namespace,
  filter/pagination, OCR300 thật, draft/confirmation invalidation, export/import,
  mobile và không có lỗi JavaScript. Test dùng profile tạm, không tạo human labels.
- Export từ browser được backend chấp nhận, vẫn **121 native pending /41
  required references pending**. Receipt: `verification/browser-real-2026-10-17.json`.
- Verify toàn payload run: remote hash manifest SHA-256
  `1f4a3de4a9bfd1aa5d1caba855b4be4943d951dc4dad9e789159aba0100761cf`.

## 6. Người dùng cần làm tiếp

1. Mở [HTML review](../../../results/m2.3/review/index.html), điền tên reviewer.
2. **Bước 2:** xem ảnh/native và lưu đánh giá của 121 trang.
3. **Bước 4:** chọn **Cần bản chữ đối chiếu** (tự chọn khi vào bước 4), kiểm tra
   và xác nhận 41 bản chữ toàn trang. Có thể lấy native làm nháp để giảm công gõ.
4. Xuất JSON, giữ file tải xuống và bàn giao để tổng hợp.

Nháp lưu trình duyệt, không tự ghi vào repo. Sau khi nhận JSON, chạy summarizer
vào thư mục mới, báo riêng development/holdout/regression, thống kê thiếu review,
CER/WER và trang không chữ. Chưa chọn/freeze ngưỡng từ dữ liệu chưa review.

## 7. Chi phí và trạng thái tài nguyên

Billing API đọc sau khi các app kết thúc ghi nhận **0.08859549 USD gross** cho
preflight và cả hai lượt calibration: CPU 0.05710329, RAM 0.00962445,
network 0.02186775; không GPU. Số liệu trước credit/allowance và có thể cập nhật
trễ, không phải cam kết hóa đơn cuối kỳ. Giữ planning budget 1 USD, không đổi
workspace spend limit 30 USD.

Receipt chỉ chứa phạm vi M2.3: `results/m2.3/verification/billing-2026-10-17.json`.
Ba app M2.3 đã `stopped`, `tasks=0`; Volume còn giữ dữ liệu.

**Kết luận bàn giao:** phần triển khai và lấy dữ liệu đã hoàn tất, sẵn sàng
review. **M2.3 chưa được kết luận PASS chất lượng và chưa freeze ngưỡng.**
