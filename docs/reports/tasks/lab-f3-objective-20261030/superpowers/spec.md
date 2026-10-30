# F3 objective experiment execution specification

Ngày bắt đầu: 2026-10-30. Đây là hoạt động mới; không hồi tố quy trình cho code cũ.

## Authorization and scope

Người dùng: “Thực hiện luôn đi chạy luôn đi”, sau khi được giải thích nhánh feature/lab-f3-objective.
Thực thi trực tiếp trong phiên này theo thiết kế đã có tại [F3](../../../../feature_lab/F3_ranking_objective.md)
và [protocol](../../../../feature_lab/README.md), source 2f15eb19b1a224f5768a5cfaa28692fb06e55b95.
Không thiết kế variant mới, không thay đổi harness, không quét tham số, không gọi compute GPU/cloud hoặc mở nhãn test.
Được kiểm tra và tải cache hiện có từ Modal volume bằng tài khoản đã cấu hình; không khởi tạo compute hay tạo dữ liệu mới.
Giữ nguyên nhánh làm việc ban đầu bằng managed worktree.

## Deliverables

- Chạy test hiện có, smoke 2 folds × 2 epochs, baseline đầy đủ và các variant F3 trên dữ liệu đủ điều kiện.
- ViDoSeek: 970 development queries, f3_approxndcg và f3_topk_hard, QARF và QPAF.
- ViMDoc: 2.000 development queries, thêm f3_lse_pool, chỉ khi tìm được cache chính xác.
- Dùng recipe nguyên bản: 5 folds, seed 20260820, 40 epochs, average 20–40, batch 16; không chọn epoch.
- Baseline tái lập phải có input SHA-256 đúng bản tham chiếu và sai lệch means <= 5e-5.
- Mọi JSON/log và validation nằm dưới evidence/; README là báo cáo hiện hành.
- So sánh ghép cặp với baseline cùng method, bootstrap 10.000 lần và W/T/L.
- verdict() hiện chưa được chốt: báo n/a, không tự đặt luật KEEP/DROP sau khi thấy số.
- Thiếu cache phải ghi rõ phần chưa chạy; không thay bằng dữ liệu giả hay tuyên bố đã chạy đủ.

## Acceptance

Các run thực có schema qpaf-lab-v1, smoke=false, tracked_changes=false, đúng query IDs/folds/recipe/input hashes.
Các mean và paired comparisons phải được tính lại từ per-query scores.
Xác minh bố cục task, links và hashes trước bàn giao. Không push/merge trong phạm vi yêu cầu này.
