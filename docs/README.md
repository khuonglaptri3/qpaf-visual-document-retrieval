# Mục lục tài liệu QPAF

Thư mục này được phân nhóm theo mục đích đọc. Dùng mục lục thay cho việc suy ra trạng thái dự án từ tên file hoặc ngày trong một snapshot cũ.

## Bắt đầu ở đây

1. [Milestone hoàn chỉnh](GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx), sheet `Milestones`: nhiệm vụ, người phụ trách, deliverable và gate.
2. [Tổng quan dự án](01_overview/HUONG_DAN_HIEU_DU_AN_QPAF.md): thuật ngữ và ý nghĩa các giai đoạn.
3. [Checklist bàn giao của Khương](khuong-m1-checklist.md) và [báo cáo audit M1.4–M1.6](06_handover/m1.4-m1.5-m1.6-audit-report.md): tiến độ theo bằng chứng.
4. [Hồ sơ G1](../evidence/M1_FINAL/06_G1/README.md), [registry/QA](../evidence/M1_FINAL/04_experiment_registry/README.md) và [báo cáo R1](../evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md): trạng thái nghiệm thu.

## Các nhóm tài liệu

| Thư mục | Nội dung |
|---|---|
| [01_overview](01_overview/README.md) | Tổng quan, kiến trúc, hướng dẫn đọc |
| [02_project_plan](02_project_plan/README.md) | Milestone, timeline, đề xuất và kế hoạch |
| [03_method](03_method/README.md) | Feature, gate, fusion, loss và method core |
| [04_data_protocol](04_data_protocol/README.md) | Corpus, qrels, OCR và hợp đồng score |
| [05_oracle_experiments](05_oracle_experiments/README.md) | Oracle, calibration, execution review và kết quả |
| [06_handover](06_handover/README.md) | Bàn giao, checklist, audit và quy trình phát triển |
| [GUILDLINE_OVERVIEWS_PROPOSAL](GUILDLINE_OVERVIEWS_PROPOSAL/overview.md) | Bộ đề xuất, workbook, Word và timeline gốc |
| [superpowers](06_handover/README.md#superpowers) | Spec và kế hoạch triển khai đã lưu |

## Cách đọc trạng thái

- **Plan / proposal / execution review:** kế hoạch hoặc điều kiện chạy; kiểm tra authorization và artifact trước khi kết luận đã thực hiện.
- **Results / receipt / integrity review:** kết quả trong phạm vi ghi rõ của từng run; kiểm tra dữ liệu thật hay fixture.
- **Method-core verification:** chứng minh phần mềm hoạt động trên workload đã kiểm; chưa tự chứng minh chất lượng learned trên corpus.
- **Sign-off / gate decision:** bằng chứng nghiệm thu; chỉ coi milestone đóng khi quyết định cần thiết đã được ghi.

Workbook và timeline là nguồn kế hoạch. [Tasks.md](../Tasks.md), [PROJECT_TRACKING.md](../PROJECT_TRACKING.md) và evidence giữ lịch sử thực hiện của từng protocol. Khi snapshot khác thời điểm hoặc phạm vi, đối chiếu artifact và amendment đang áp dụng.

## Quy tắc tổ chức và truy nguồn

- Tài liệu mới đặt vào nhóm phù hợp; cập nhật mục lục nhóm và [catalog.json](catalog.json).
- Các tài liệu được script/config/manifest tham chiếu giữ nguyên đường dẫn và byte. Mục lục nhóm liên kết tới các file đó.
- File hướng dẫn ở vị trí cũ có nội dung “Tài liệu đã chuyển” là liên kết tương thích cho hồ sơ và tài liệu lịch sử.
- Bộ workbook/Word/timeline gốc và các spec/plan đã lưu giữ nguyên vị trí.
- [catalog.json](catalog.json) ghi vị trí cũ/mới, nhóm và SHA-256 của 63 tài liệu nguồn tại lần sắp xếp ngày 04/10/2026; đây là inventory tổ chức tài liệu, không phải nghiệm thu nghiên cứu.
