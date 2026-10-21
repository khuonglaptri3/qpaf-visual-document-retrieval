# Tài liệu chính thức QPAF

Theo yêu cầu của Khương, thư mục này là nguồn thống nhất cho đề xuất, tổng quan,
milestone và phân công. Giữ nguyên các tài liệu nguồn đã được chỉnh sửa:

| Tài liệu | Cách sử dụng |
| --- | --- |
| [POAI_Milestone_Group01_Hoan_Chinh.xlsx](POAI_Milestone_Group01_Hoan_Chinh.xlsx) | Nguồn chính cho task, owner, deliverable, dependency và lịch kế hoạch; sheet `Milestones` và `Proposal Traceability` |
| [Đề xuất nghiên cứu](DE_XUAT_NGHIEN_CUU_QPAF.md) | Phạm vi và câu hỏi nghiên cứu |
| [Tổng quan](overview.md) | Phối hợp và bối cảnh dự án |
| [Timeline](TIMELINE_fixed.md) | Chi tiết timeline trong phạm vi tài liệu |
| [Nghiên Cứu Kỹ Thuật QPAF](Nghi%C3%AAn%20C%E1%BB%A9u%20K%E1%BB%B9%20Thu%E1%BA%ADt%20QPAF.docx) | Tài liệu Word nguồn |

Workbook quy định M3.1 tại dòng 39: Khương chốt bộ đầu vào pilot và kiểm chứng
cache/splits bất biến, cùng rows, thứ tự, features và qrels giữa QARF/QPAF;
dependency là D1. M3.2/M3.4 do Tấn Phát chạy pilot; Thanh kiểm chứng và so sánh
ở M3.3/M3.5; Khương kiểm tra integrity/resource ở M3.6.

Trạng thái nghiệm thu và các tham số/dữ liệu cụ thể lấy từ revision evidence và
protocol/amendment có hiệu lực. D1 hiện hành:
[`m2.11-002`](../../evidence/revisions/m2.11-002/decision.json).
G2 chỉ so sánh matched learned QPAF với QARF; full baseline matrix thuộc M4.

Các bản tổng quan, kế hoạch và workbook cũ bên ngoài thư mục này đã được loại bỏ.
Hồ sơ bằng chứng, protocol đã đóng băng và tài liệu kỹ thuật vẫn được lưu để truy
nguồn từng kết quả. Xem [mục lục kỹ thuật](../README.md) và
[danh mục thay đổi tài liệu](../catalog.json).

Hướng dẫn triển khai và bàn giao M3.1: [M3_1_HANDOFF.md](M3_1_HANDOFF.md).
