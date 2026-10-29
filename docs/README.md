# Tài liệu QPAF

Nguồn chính thức thống nhất cho đề xuất, tổng quan, milestone và phân công là
[`GUILDLINE_OVERVIEWS_PROPOSAL/`](GUILDLINE_OVERVIEWS_PROPOSAL/README.md).
Đọc workbook `POAI_Milestone_Group01_Hoan_Chinh.xlsx`, sheet `Milestones`, để xác định
task, owner, deliverable và dependency. Các bản tổng quan/kế hoạch cũ bên ngoài
thư mục này đã được loại bỏ theo yêu cầu của Khương.

Trạng thái thực hiện được xác định bằng evidence của từng revision, không suy ra
từ cột trạng thái hoặc ngày kế hoạch trong workbook. D1 hiện hành là
[`m2.11-002`, PASS](../evidence/revisions/m2.11-002/decision.json).

M5.2 hiện **HOÀN THÀNH / ACCEPTED** theo xác nhận của Khương ngày 27/10/2026
rằng review đã hoàn tất. Xem [hồ sơ nghiệm thu hiện hành](../results/m5.2/verification/README.md).
Trạng thái trong workbook và các receipt đã đóng băng là snapshot lịch sử.

M5.5: **R5-01/02/03/04 đã hoàn thành kỹ thuật**, chờ nghiệm thu độc lập.
QARF/QPAF median online2.569362/2.4263995ms/query; CUDA allocated khoảng0.0324GiB.
Xem [báo cáo hiện hành, spec/plan và bằng chứng PR #45](reports/milestones/M5.5/README.md)
và [bàn giao](06_handover/m5.5-cpu-results-and-gpu-handoff.md).
Các receipt CPU ghi GPU-deferred được giữ nguyên như snapshot lịch sử.

| Vị trí | Mục đích |
| --- | --- |
| [Tài liệu chính thức](GUILDLINE_OVERVIEWS_PROPOSAL/README.md) | Đề xuất, workbook, Word, tổng quan và timeline |
| [Phương pháp](03_method/README.md) | Hợp đồng feature, gate, loss, pipeline và matched config |
| [Dữ liệu](04_data_protocol/README.md) | Corpus, qrels, OCR và định danh trang |
| [Oracle lịch sử](05_oracle_experiments/README.md) | Protocol, review và kết quả của từng study |
| [Bàn giao kỹ thuật](06_handover/README.md) | Audit, runbook và hồ sơ bàn giao |
| [Feature lab](feature_lab/README.md) | Bốn thay đổi kiến trúc F1–F4 cho QARF/QPAF, harness CV chung và phân công chạy song song |
| [Evidence](../evidence/) | Manifest, hash, quyết định và revision đã ghi nhận |

Các tài liệu kỹ thuật và hồ sơ lịch sử giữ vai trò giải thích implementation hoặc
truy nguồn evidence; chúng không thay thế workbook chính thức. Manifest, receipt
và source snapshot đã đóng băng giữ nguyên byte. Liên kết trong snapshot áp dụng
cho commit nguồn; dùng Git history khi cần đọc tài liệu đã được loại bỏ.

[`catalog.json`](catalog.json) là danh mục tài liệu và ghi nhận các đường dẫn cũ
đã loại bỏ; danh mục này không phải biên bản nghiệm thu nghiên cứu.
