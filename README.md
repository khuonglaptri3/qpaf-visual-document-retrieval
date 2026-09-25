# QPAF — Query-Page Adaptive Fusion for Visual Document Retrieval

Repository nghiên cứu của **Group 01**. QPAF là phương pháp chính; QARF là
phương pháp so sánh có cùng đầu vào theo protocol của nhóm.

| Thành viên | Vai trò |
| --- | --- |
| Trần Đình Khương | Technical / Data Owner |
| Bùi Trần Tấn Phát | Research Lead / Protocol Owner |
| Trần Huỳnh Xuân Thanh | Experiment Governance / Independent QA |

## Phạm vi khởi tạo

Làm lại phần việc của Khương từ **M1.4**, theo lịch thực hiện **23–27/09/2026**
trong [TIMELINE_fixed.md](TIMELINE_fixed.md). Ngày trong lịch là ngày kế hoạch;
commit và báo cáo ghi thời điểm thực hiện thật.

Nguồn phân công toàn dự án là sheet `Milestones` trong
[workbook gốc](POAI_Milestone_Group01_Hoan_Chinh.xlsx). Sheet `WBS` có kế hoạch
khác; không dùng nó để mở rộng phạm vi hiện tại.

Repo khởi đầu từ hai tài liệu kế hoạch. Source nghiên cứu, corpus, config thí
nghiệm và kết quả cũ chưa được cung cấp trong workspace này.

## Gitflow

- `main`: mốc ổn định hoặc bản phát hành; commit đầu tiên là mốc khởi tạo.
- `develop`: nhánh tích hợp công việc đang thực hiện.
- `feature/*`: phát triển từ `develop`, review rồi merge về `develop`.
- `release/*`: chuẩn bị bản phát hành từ `develop`, merge vào `main` và `develop`.
- `hotfix/*`: sửa bản phát hành từ `main`, merge về `main` và `develop`.

Phần M1.4 được triển khai trên `feature/m1-repository-audit`.
Xem [quy trình đóng góp](CONTRIBUTING.md).

