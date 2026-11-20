# Phát: Dữ liệu, tái lập retrieval và hạ tầng thực nghiệm

**Đã có branch và brief; chưa implement phần nghiên cứu mới.** Branch chứa toàn bộ source F9 từ commit `842176c5b707298672629738390a09e222f47e86`. Bootstrap chỉ thêm task bundle này và một dòng mục lục; không thêm model code hay số benchmark.

Branch: `research/jev-phat-data-infra`. Câu hỏi: Khôi phục/reuse được artifact nào của F9, candidate pool còn headroom nào, và setup chung nào cho phép so model đúng protocol với chi phí đo được?

## Bắt đầu trên máy của người phụ trách

```powershell
git fetch origin
git switch --track origin/research/jev-phat-data-infra
```

Nếu local branch đã có, dùng `git switch research/jev-phat-data-infra`. Đây là lệnh cho checkout của người phụ trách; không tự đổi branch đang làm của người khác.

Đọc [spec](superpowers/spec.md) và [plan](superpowers/plan.md) trước. Các file dự kiến trong plan chưa được tạo; không có lệnh chạy Jev sẵn ở thời điểm bootstrap. Nhận input contract từ Phát; Thanh chấm mọi output bằng evaluator chung; Khương cung cấp model outputs. Chi phí/GPU và cache thực tế còn cần xác nhận.

## Code/tài liệu có sẵn để tận dụng

- [scripts/lab_rerank.py](../../../../scripts/lab_rerank.py)
- [scripts/modal_lab_rerank.py](../../../../scripts/modal_lab_rerank.py)
- [docs/feature_lab/HUONG_DAN_CHAY.md](../../../../docs/feature_lab/HUONG_DAN_CHAY.md)
- [src/qpaf/f9/method.py](../../../../src/qpaf/f9/method.py)

## Đầu ra và nghiệm thu

Inventory cache có/còn thiếu; data/split/pairs manifests và SHA-256; pairs.json; input/score contract; môi trường/launcher pin version; GPU/token/time/cost logs; run manifests và bản tích hợp.

Input mapping/hash và cohort rõ; cùng pool cho mọi model; cache chỉ reuse khi tương thích; nhãn không lẫn; jobs có resume/manifests/cost evidence; baseline và Kev giữ môi trường riêng.

Giữ raw cache/pairs/revisions để tránh chạy lại khi tương thích; mean/per-query JSON lịch sử dùng tham chiếu và chẩn đoán, không thay raw examples/scores. Không trộn kết quả khác protocol vào bảng mới.

## Bằng chứng bootstrap

[Workflow](evidence/workflow.md), [kiểm chứng tài liệu](evidence/validation.json), [SHA-256](evidence/hashes.json). Các kiểm tra này không chứng minh môi trường model hoặc chất lượng Jev đã chạy thành công.
