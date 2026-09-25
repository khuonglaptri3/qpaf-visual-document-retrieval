# M1 evidence package

Đợt bàn giao M1.1/M1.2 và trạng thái mới nhất được mô tả tại
[README chính](../../README.md) và
[trạng thái bàn giao](../../docs/m1-restart-handoff.md).
Snapshot mới nằm tại `evidence/revisions/m1.4-002-handoff/`.

Đây là **bộ bàn giao đang chuẩn bị**, không phải quyết định M1 CLOSED.
Từ `FINAL` trong tên thư mục là cấu trúc bắt buộc của timeline, không mô tả
trạng thái nghiệm thu. File có sẵn không đồng nghĩa task đã hoàn thành.

| Thư mục | Owner | Trạng thái/đầu vào |
| --- | --- | --- |
| `01_repository_audit/` | Khương | Snapshot M1.4; xem `audit_metadata.json` và `gap_log.md` |
| `02_protocol/` | Tấn Phát | Chờ frozen protocol thật |
| `03_collision_audit/` | Khương | BLOCKED; CSV chỉ có schema, chưa có corpus |
| `04_experiment_registry/` | Thanh | Chờ registry và independent QA |
| `05_ocr_artifacts/` | Khương | DRAFT; chưa calibration/chốt threshold; NOT SIGNED |
| `06_G1/` | Tấn Phát | Chờ đủ evidence và review của nhóm |
| `07_R1/` | Tấn Phát | Chờ G1 final và báo cáo thật |

Snapshots mới lưu dưới `evidence/revisions/` với ID mới. Bộ được lựa chọn để
nghiệm thu phải được ghi rõ ở quyết định G1; bảo toàn các snapshot trước đó.
Snapshot hash manifest không tự chứa chính nó hoặc bằng chứng sinh ra sau đó.
Commit chứa evidence bảo vệ phiên bản của toàn bộ các file bàn giao.
