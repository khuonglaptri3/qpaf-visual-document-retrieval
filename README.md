# M2.3 — Hiệu chuẩn OCR

M2.3 chọn và khóa chính sách lấy văn bản trang PDF để các bước sau dùng chung một phiên bản tiền xử lý. Trạng thái: **COMPLETE_BOUNDED_CALIBRATION**; checklist **16/16** đã hoàn tất trong phạm vi bộ mẫu hiện có.

Điểm bắt đầu để dùng kết quả là [manifest bàn giao của revision m2.3-002](evidence/revisions/m2.3-002/handover.json). Manifest xác định cấu hình, hash, dữ liệu mẫu và nguồn bằng chứng.

## Dữ liệu và kết quả

| Hạng mục | Kết quả |
|---|---|
| Bộ mẫu calibration | 121 trang PDF |
| So sánh OCR | 150 và 300 DPI; 242 lượt, không có lỗi kỹ thuật |
| Review native cuối | 95 PASS, 25 HAS_ERRORS, 1 NO_TEXT; không còn pending |
| Bản chữ đối chiếu | 18 trang từ 12 PDF; 15 development, 3 holdout |
| Cấu hình được chọn | `mixed300_c60` |
| Đầu ra sau chính sách | 45 trang native, 70 native + OCR, 6 OCR |
| Kiểm thử M2.3 đã ghi nhận | 23 tests PASS |

100 quyết định native ban đầu được giữ lại; 21 điều chỉnh bổ sung do Codex AI thực hiện theo yêu cầu người dùng và có lưu provenance. Bộ chốt có 18 references đã xác nhận; không có tuyên bố ký duyệt độc lập của nhóm.

## Chính sách đã khóa

[Cấu hình chính thức](configs/m2.3/ocr_policy_frozen.toml) giữ văn bản native hợp lệ và bổ sung các từ OCR ở vùng chưa được native bao phủ:

- Tesseract **5.3.0**, tiếng Anh, **300 DPI**, OEM 3 / PSM 3.
- Confidence tối thiểu của từ OCR bổ sung: **60**; ngưỡng phần diện tích trùng vùng native: **0,5**.
- Parser PDFium **4.30.0**; đọc TSV bằng `QUOTE_NONE` để giữ đúng dấu ngoặc kép trong nội dung OCR.
- Giới hạn mỗi subprocess OCR: **15 giây**; 2 workers, 1 thread/subprocess, CPU 4, RAM 4096 MiB.
- Trang không phát hiện được chữ vẫn giữ page ID và đầu vào hình ảnh. Confidence thấp tạo cảnh báo chất lượng; lỗi kỹ thuật được ghi riêng.

SHA-256 của cấu hình:

```text
c0fcf0b3b13b27070716179d75545ba33ae406cc99a74902737bcf2dad19c4b8
```

Chỉ số chọn cấu hình là macro retrieval BWE trên phần development có chữ: **14,0001% → 11,3235%** so với chính sách fallback cũ. Trên 3 trang holdout đã được xem trước, chỉ số mô tả là **9,4241% → 8,4644%**. CER/WER và các ứng viên so sánh nằm trong [báo cáo quyết định](docs/superpowers/reports/2026-10-17-m23-research-and-final-decision.md).

## Bộ bàn giao chính thức

| File | Mục đích |
|---|---|
| [handover.json](evidence/revisions/m2.3-002/handover.json) | Điểm vào, trạng thái, đường dẫn và các hash cần kiểm tra |
| [ocr_policy_frozen.toml](configs/m2.3/ocr_policy_frozen.toml) | Chính sách vận hành đã khóa |
| [resolved_pages.json](evidence/revisions/m2.3-002/resolved_pages.json) | Văn bản và trạng thái xử lý của 121 trang mẫu |
| [human_reviews.final.json](evidence/revisions/m2.3-002/human_reviews.final.json) | Review và 18 bản chữ đối chiếu cuối |
| [decision.json](evidence/revisions/m2.3-002/decision.json) | Quyết định lựa chọn cùng giới hạn áp dụng |
| [hashes.json](evidence/revisions/m2.3-002/hashes.json) | Hash của các file trong revision |
| [Báo cáo nghiên cứu và quyết định](docs/superpowers/reports/2026-10-17-m23-research-and-final-decision.md) | Nguồn tham khảo, phương pháp, kết quả và giới hạn |
| [Hướng dẫn dùng đầu ra M2.3](docs/superpowers/reports/2026-10-17-m23-downstream-handoff.md) | Hợp đồng dữ liệu cho loader, feature và cache ở các bước tiếp theo |

Kết quả làm việc cuối nằm ở `results/m2.3/closure/2026-10-17-closed/`. Các gói closure `v1`, `final`, `complete` và revision `m2.3-001` được giữ làm lịch sử; bản hiện hành là **m2.3-002**.

## Mã nguồn và kiểm tra local

```text
configs/m2.3/                    Cấu hình calibration, policy và QA
src/qpaf/m23/                    Chọn mẫu, worker OCR, review và policy
scripts/run_m23_calibration.py   Chuẩn bị, chạy và kiểm chứng calibration
scripts/repair_m23_references.py Sửa references và lưu provenance/diff
scripts/summarize_m23_reviews.py Tổng hợp review theo protocol ban đầu
scripts/finalize_m23_calibration.py  Tạo gói kết quả chốt từ dữ liệu đã có
requirements/m23-modal.lock      Môi trường calibration đã pin
results/m2.3/                   Run metadata, review và kết quả
evidence/revisions/m2.3-002/    Bộ bằng chứng bàn giao chính thức
```

Chạy kiểm thử M2.3 bằng Python 3.11 trở lên:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[calibration]"
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_m23*.py" -v
```

Khi các payload gốc đã có ở local, có thể tái tạo gói phân tích vào một thư mục mới, không chạy lại OCR/cloud:

```powershell
.venv/Scripts/python.exe scripts/finalize_m23_calibration.py --output results/m2.3/closure/<id-moi>
```

Git lưu mã nguồn, cấu hình, báo cáo, văn bản mẫu, provenance và hash. PDF nguồn, ảnh render, raw OCR và hồ sơ trình duyệt tạm không được đưa vào Git. Xem [runbook](results/m2.3/README.md) để biết vị trí payload và các lệnh chạy; giao diện HTML cần ảnh local để hiển thị trang gốc.

## Phạm vi và tài liệu

Đây là hiệu chuẩn trên mẫu nhỏ, chưa phải xác nhận độ chính xác OCR toàn corpus. Holdout đã được xem nên chỉ dùng mô tả; chưa có bản chép tay regression. Chất lượng trên chữ nhỏ, chữ xoay và chữ trong ảnh vẫn có giới hạn. M2.3 chưa chạy OCR toàn corpus, tạo cache retrieval toàn bộ hoặc huấn luyện mô hình.

- [Thiết kế](docs/superpowers/specs/2026-10-17-m23-ocr-calibration-design.md), [protocol chốt](docs/superpowers/specs/2026-10-17-m23-closure-decision-protocol.md), [kế hoạch](docs/superpowers/plans/2026-10-17-m23-ocr-calibration.md).
- [Báo cáo QA references](docs/superpowers/reports/2026-10-17-m23-reference-qa-completed.md) và [nhật ký thực hiện](docs/superpowers/progress/2026-10-17-m23-ocr-calibration.md).
- [Danh mục đầy đủ các file liên quan M2.3 trong workspace](docs/superpowers/reports/2026-10-17-m23-file-inventory.md); danh mục gồm cả payload local và file tạm không có trong Git.
