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

## Bắt đầu với M1.4

Yêu cầu: Python **3.11 trở lên** và Git. Công cụ audit dùng thư viện chuẩn,
không cần cài package hoặc tải model.

```sh
python -m unittest discover -s tests -v
python scripts/audit_repository.py --root . --verify evidence/M1_FINAL/01_repository_audit/hash_manifest.csv
```

Lần audit đầu được lưu tại `evidence/M1_FINAL/01_repository_audit/`. Khi có
code/data/config mới, tạo snapshot mới để bảo toàn bằng chứng trước đó:

```sh
python scripts/audit_repository.py --root . --output evidence/revisions/m1.4-002
python scripts/audit_repository.py --root . --verify evidence/revisions/m1.4-002/hash_manifest.csv
```

Lệnh tạo báo cáo trả về exit code 0 khi tạo file thành công. Trạng thái
`PARTIAL` trong báo cáo vẫn yêu cầu review; nó không có nghĩa M1.4/G1 đã đạt.
Lệnh verify thất bại nếu file bị sửa/xóa, hash sai hoặc manifest không hợp lệ.
Snapshot không ghi đè; các lần sau dùng tên mới. Commit trong snapshot là
revision được kiểm kê, trước commit bổ sung chính báo cáo đó.

## Cấu trúc

```text
configs/                Cấu hình thí nghiệm; chưa có config nghiên cứu
data/                   Hướng dẫn dữ liệu; payload lớn nằm ngoài Git
docs/                   Checklist, thiết kế và kế hoạch triển khai
manifests/              Định danh, split và hash của dữ liệu khi được cung cấp
results/                Bảng kết quả nhỏ có nguồn gốc rõ ràng
scripts/                Lệnh chạy audit từ checkout
src/qpaf/               Công cụ hỗ trợ; method QPAF chưa được đưa vào repo
tests/                  Fixture tổng hợp cho phần mềm, không phải corpus
evidence/M1_FINAL/      Bảy thư mục bàn giao theo TIMELINE_fixed.md
```

Xem [checklist của Khương](docs/khuong-m1-checklist.md) và
[bộ bàn giao M1](evidence/M1_FINAL/README.md). Chưa có giấy phép phân phối
được cả nhóm thống nhất; không tự gán giấy phép cho dữ liệu/model bên ngoài.

## Gitflow

- `main`: mốc ổn định hoặc bản phát hành; commit đầu tiên là mốc khởi tạo.
- `develop`: nhánh tích hợp công việc đang thực hiện.
- `feature/*`: phát triển từ `develop`, review rồi merge về `develop`.
- `release/*`: chuẩn bị bản phát hành từ `develop`, merge vào `main` và `develop`.
- `hotfix/*`: sửa bản phát hành từ `main`, merge về `main` và `develop`.

Phần M1.4 được triển khai trên `feature/m1-repository-audit`.
Xem [quy trình đóng góp](CONTRIBUTING.md).
