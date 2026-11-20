# Thanh: Reranker baseline và đánh giá độc lập

**Đã có branch và brief; chưa implement phần nghiên cứu mới.** Branch chứa toàn bộ source F9 từ commit `842176c5b707298672629738390a09e222f47e86`. Bootstrap chỉ thêm task bundle này và một dòng mục lục; không thêm model code hay số benchmark.

Branch: `research/jev-thanh-baselines`. Câu hỏi: Kev có cải thiện nDCG/MRR/Recall hoặc hiệu quả chi phí so với BGE và Qwen4B khi giữ cùng cohort, pool và protocol không?

## Bắt đầu trên máy của người phụ trách

```powershell
git fetch origin
git switch --track origin/research/jev-thanh-baselines
```

Nếu local branch đã có, dùng `git switch research/jev-thanh-baselines`. Đây là lệnh cho checkout của người phụ trách; không tự đổi branch đang làm của người khác.

Đọc [spec](superpowers/spec.md) và [plan](superpowers/plan.md) trước. Các file dự kiến trong plan chưa được tạo; không có lệnh chạy Jev sẵn ở thời điểm bootstrap. Nhận input contract từ Phát; Thanh chấm mọi output bằng evaluator chung; Khương cung cấp model outputs. Chi phí/GPU và cache thực tế còn cần xác nhận.

## Code/tài liệu có sẵn để tận dụng

- [scripts/lab_rerank.py](../../../../scripts/lab_rerank.py)
- [scripts/modal_lab_rerank.py](../../../../scripts/modal_lab_rerank.py)
- [src/qpaf/lab/rerank.py](../../../../src/qpaf/lab/rerank.py)
- [src/qpaf/f9/method.py](../../../../src/qpaf/f9/method.py)
- [docs/feature_lab/KET_LUAN.md](../../../../docs/feature_lab/KET_LUAN.md)

## Đầu ra và nghiệm thu

Baseline không rerank; bge_scores.json; qwen4b_scores.json; per-query metric table; nDCG@10/MRR@10/Recall@10/20; paired Δ/CI/W–T–L; failure/latency/cost analysis.

Một evaluator cho toàn bộ model; cùng cohort/pool; metrics có per-query evidence và uncertainty; không silent missing-query skip; không chép mean khác protocol; không tuyên bố Jev thắng khi bằng chứng chưa đủ.

Giữ raw cache/pairs/revisions để tránh chạy lại khi tương thích; mean/per-query JSON lịch sử dùng tham chiếu và chẩn đoán, không thay raw examples/scores. Không trộn kết quả khác protocol vào bảng mới.

## Bằng chứng bootstrap

[Workflow](evidence/workflow.md), [kiểm chứng tài liệu](evidence/validation.json), [SHA-256](evidence/hashes.json). Các kiểm tra này không chứng minh môi trường model hoặc chất lượng Jev đã chạy thành công.
