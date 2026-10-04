# Khương — làm lại M1 theo lịch 23–27/09/2026

**Bàn giao hiện tại bắt đầu từ M1.1/M1.2:** xem
[trạng thái đầu vào](m1-restart-handoff.md) và [README](../../README.md).
M1.1 đã có báo cáo Oracle nhưng thiếu artifact gốc; M1.3 chưa có gói audit
để kiểm chứng. Bảng dưới là lịch tham chiếu cho phần Khương từ M1.4.

Nguồn: `TIMELINE_fixed.md`, phần 3, 9, 10 và 11.
Ngày trong bảng là ngày kế hoạch; thời điểm quan sát nằm trong audit metadata
và lịch sử Git. Không backdate để biến việc thực hiện sau thành đúng hạn.

| Ngày kế hoạch | Nhiệm vụ | Bằng chứng/điều kiện |
| --- | --- | --- |
| 23/09 | M1.4 kiểm kê repo/data/config/run/Git/hash | `01_repository_audit/`; thiếu asset phải ghi gap |
| 24/09 | M1.6 kiểm manifest/duplicate/alias/leakage/qrels | Có corpus, ID, split, qrels thật; report được review |
| 24/09 | Soạn M1.8 trong lúc chờ scan | Draft OCR và artifact namespace |
| 25/09 | Chốt M1.8, trình bằng chứng G1 | Có calibration/threshold và đối chiếu protocol |
| 26/09 | Sửa technical blocker từ G1 | Issue có owner, evidence mới, kiểm lại hash/collision |
| 27/09 | Technical Freeze và sign-off | Review dữ liệu/code/hash/OCR hoàn tất; Thanh QA độc lập |

## Trạng thái cập nhật ngày 28/09/2026

- Repo và quy trình Gitflow: hoạt động ổn định trên `develop` và feature branches.
- M1.3: **ĐÃ TRIỂN KHAI HOÀN TẤT** ([`docs/04_data_protocol/m1.3-primary-corpus.md`](../04_data_protocol/m1.3-primary-corpus.md)); bộ công cụ CPU audit package tại `src/qpaf/m13/`, 16/16 test đạt 100%.
- M1.4: **ĐÃ TẠO SNAPSHOT MỚI `evidence/revisions/m1.4-003/`**; kiểm kê 307 tệp, ghi nhận 20 source, 2 config, 225 run assets; đóng 3/5 gaps lớn (`RESEARCH_CODE_MISSING`, `CONFIG_MISSING`, `RUNS_MISSING` đã được giải quyết).
- M1.5: **ĐÃ BAN HÀNH 2 AMENDMENTS** (`QPAF-M1.5-A001` chốt Pairwise Logistic Loss và `QPAF-M1.5-A002` chốt ViDoSeek).
- M1.6: **ĐÃ TRIỂN KHAI VÀ KIỂM TOÁN HOÀN TẤT** ([`evidence/revisions/m1.6-001/`](../../evidence/revisions/m1.6-001)); hệ thống `src/qpaf/m16/` và CLI `scripts/audit_collisions.py` xác nhận 100% canonical IDs, zero cross-split leakage, và 0 orphan queries.
- Báo cáo kiểm kê toàn diện M1.4–M1.5–M1.6: xem [`docs/06_handover/m1.4-m1.5-m1.6-audit-report.md`](m1.4-m1.5-m1.6-audit-report.md).
- M1.8: **ĐÃ TRIỂN KHAI VÀ XUẤT BẢN GÓI HIỆU CHUẨN** ([`evidence/revisions/m1.8-001/`](../../evidence/revisions/m1.8-001)); gồm `ocr_checklist.md`, `ocr_failure_threshold.md` (công thức toán học và ngưỡng dự kiến PROVISIONAL chờ M2.3 freeze), `artifact_namespace.md` (đồng bộ 100% với Thanh M1.7), `calibration_methodology.md`, phân hệ `src/qpaf/m18/` và CLI `scripts/audit_ocr_policy.py`.
- Technical sign-off: **NOT SIGNED**; G1 do Phát quyết định với QA của Thanh. Sẵn sàng trình Hội đồng Gate G1 bộ bằng chứng hoàn chỉnh M1.4–M1.8.


## Việc tiếp theo của Khương

Trước khi coi M1.3 hoàn tất, xác định với Phát corpus/revision/phạm vi và
gói audit cần kiểm chứng. Không yêu cầu “khôi phục” một gói chưa từng nhận.

1. Xác định research code cũ ở đâu, hoặc xác nhận chưa có để nhóm cập nhật scope.
2. Nhận nguồn/phiên bản corpus và split/qrels theo protocol của Phát.
3. Nhận config/output/log cũ nếu có; yêu cầu đủ liên kết để Thanh audit.
4. Đưa asset hợp lệ vào cấu trúc, tạo snapshot M1.4 mới, xử lý từng gap.
5. Chạy M1.6 trên corpus thật; review aliases, trùng/xung đột và leakage.
6. Chốt với Phát phạm vi M1.8 so với calibration M2.3; chuẩn bị OCR policy,
   ghi ngưỡng chưa đo là dự kiến. Full OCR thuộc M2.6. Cập nhật tiêu chí
   review/sign-off theo phạm vi nhóm thống nhất.

## Phối hợp và cách báo tiến độ

Phát cung cấp frozen protocol (split/metrics/seeds/run policy), tổng hợp G1
và blocker log. Thanh cung cấp registry/naming và audit độc lập. Khương gửi
file, revision, hash, trạng thái và lý do còn block; không chỉ báo phần trăm.

Ví dụ trạng thái hợp lệ: `hash_manifest.csv GENERATED; data_inventory.csv
EMPTY — awaiting corpus; collision_report.md BLOCKED — no primary corpus`.
Ngày 26–27 không mở experiment/architecture/feature/benchmark mới.
