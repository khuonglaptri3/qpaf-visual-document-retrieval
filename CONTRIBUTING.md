# Quy trình làm việc của Group 01

## Gitflow

`main` là lịch sử ổn định; `develop` là nhánh tích hợp và đích mặc định của PR
cho feature. Mốc khởi tạo trên `main` không có nghĩa M1 hoặc G1 đã hoàn thành.

### Feature

```sh
git switch develop
git pull --ff-only origin develop
git switch -c feature/m1-repository-audit
# Sửa code/tài liệu, kiểm tra, commit.
git push -u origin feature/m1-repository-audit
```

Tên nhánh khác: `feature/m1-collision-audit`, `feature/m1-ocr-artifacts`,
`feature/m1-protocol-freeze`, `feature/m1-experiment-registry`.
Đợt bàn giao M1.1/M1.2 dùng `feature/m1-1-oracle-review` cho Thanh và
`feature/m1-2-method-core` cho Phát. Mỗi người tạo nhánh riêng từ
`develop`; xem [README](README.md) để biết đầu vào, việc làm và output.
Mở PR vào `develop`; ghi task, file bàn giao, lệnh kiểm tra và blocker.
Một thành viên khác review khi nhóm đã có quyền truy cập.
Merge theo `--no-ff` để giữ ranh giới feature; không force-push nhánh dùng chung.

### Release

Tạo `release/<version>` từ `develop` khi nhóm đã xác định phạm vi phát hành.
Chỉ sửa lỗi, hoàn thiện tài liệu và xác minh bằng chứng trong nhánh release.
Sau review: merge `--no-ff` vào `main`, gắn annotated tag `v<version>`, rồi
merge nhánh release về `develop`. Không gắn tag hoàn thành M1 nếu thiếu G1.

### Hotfix

Tạo `hotfix/<issue>` từ `main` cho lỗi của bản phát hành hiện có. Kiểm tra và
review, merge vào `main`, gắn patch tag, merge về `develop` và nhánh release
đang mở nếu có.

## Commit và bằng chứng

- Dùng tiền tố `chore:`, `docs:`, `feat:`, `fix:`, `test:`; ghi hành động cụ thể.
- Chạy `python -m unittest discover -s tests -v` trước khi merge code.
- Không sửa lịch sử hoặc ngày commit để khớp ngày kế hoạch 23/09.
- Không đưa dataset/checkpoint lớn hay thông tin đăng nhập vào Git.
- Lưu manifest, SHA-256, config, commit, lệnh chạy và vị trí output của thí nghiệm.
- Output đã tạo phải được bảo toàn; lần kiểm tra mới dùng namespace mới.
- Khương chuẩn bị bằng chứng; Thanh QA độc lập; Phát chốt protocol và gate.
- Với M1.1 do Thanh thực hiện, một thành viên khác review kết quả của Thanh.
  Vai trò QA của Thanh không thay thế review độc lập cho chính run của mình.
- Bản báo cáo Oracle đã nhận nằm trong `results/m1.1/reference/`; các lần
  chạy mới dùng thư mục riêng và ghi rõ sai khác với nguồn.

## Chính sách GitHub

Repo mới được tạo private để nhóm chuẩn bị dữ liệu và phạm vi chia sẻ.
Các quy tắc review ở trên là quy trình làm việc; không tự coi là branch
protection đã được GitHub cưỡng chế. Cần thêm tài khoản của Phát/Thanh và chọn
các kiểm tra bắt buộc trước khi cấu hình enforcement cho cả nhóm.
