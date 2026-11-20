# Khương: Kev decision model và domain fine-tuning

**Đã có branch và brief; chưa implement phần nghiên cứu mới.** Branch chứa toàn bộ source F9 từ commit `842176c5b707298672629738390a09e222f47e86`. Bootstrap chỉ thêm task bundle này và một dòng mục lục; không thêm model code hay số benchmark.

Branch: `research/jev-khuong-model`. Câu hỏi: Kev frozen và Kev thích nghi theo miền có giúp reranking hơn baseline mạnh; decision pretraining có thêm lợi ích so với cùng backbone/head khởi tạo từ base không?

## Bắt đầu trên máy của người phụ trách

```powershell
git fetch origin
git switch --track origin/research/jev-khuong-model
```

Nếu local branch đã có, dùng `git switch research/jev-khuong-model`. Đây là lệnh cho checkout của người phụ trách; không tự đổi branch đang làm của người khác.

Đọc [spec](superpowers/spec.md) và [plan](superpowers/plan.md) trước. Các file dự kiến trong plan chưa được tạo; không có lệnh chạy Jev sẵn ở thời điểm bootstrap. Nhận input contract từ Phát; Thanh chấm mọi output bằng evaluator chung; Khương cung cấp model outputs. Chi phí/GPU và cache thực tế còn cần xác nhận.

## Code/tài liệu có sẵn để tận dụng

- [scripts/modal_lab_rerank.py](../../../../scripts/modal_lab_rerank.py)
- [scripts/lab_rerank.py](../../../../scripts/lab_rerank.py)
- [src/qpaf/f9/method.py](../../../../src/qpaf/f9/method.py)

## Đầu ra và nghiệm thu

kev_frozen_scores.json; kev_ft_scores.json; base_ft_scores.json; adapter/head checkpoints; config/seeds/gradient/save-reload/VRAM logs; phân tích ablation.

Loader khôi phục đủ adapter/head; không giấu lỗi bằng score 0; score coverage chính xác; test mapping/save-reload có ý nghĩa; train/eval không lẫn; đối chứng initialization cùng protocol.

Giữ raw cache/pairs/revisions để tránh chạy lại khi tương thích; mean/per-query JSON lịch sử dùng tham chiếu và chẩn đoán, không thay raw examples/scores. Không trộn kết quả khác protocol vào bảng mới.

## Bằng chứng bootstrap

[Workflow](evidence/workflow.md), [kiểm chứng tài liệu](evidence/validation.json), [SHA-256](evidence/hashes.json). Các kiểm tra này không chứng minh môi trường model hoặc chất lượng Jev đã chạy thành công.
