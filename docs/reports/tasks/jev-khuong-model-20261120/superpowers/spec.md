# Spec: Kev decision model và domain fine-tuning

Owner: **Khương**. Branch: `research/jev-khuong-model`. Base: `842176c5b707298672629738390a09e222f47e86`.
Ngày bắt đầu branch/brief: 2026-11-20. Status: nghiên cứu/implementation chưa thực hiện.

## Câu hỏi và phạm vi

Kev frozen và Kev thích nghi theo miền có giúp reranking hơn baseline mạnh; decision pretraining có thêm lợi ích so với cùng backbone/head khởi tạo từ base không?

Adapter chính thức Kev-4B; frozen inference; LoRA r16 + pointer head trên ViDoSeek; đối chứng cùng backbone/head/loss/data/budget từ base. Kev là Jev-style cộng đồng, không phải checkpoint TypeSafe Jev.

Đầu ra: kev_frozen_scores.json; kev_ft_scores.json; base_ft_scores.json; adapter/head checkpoints; config/seeds/gradient/save-reload/VRAM logs; phân tích ablation.

## Ràng buộc chung

ViDoSeek text/OCR trước; cùng split/cohort/top-20/pairs hash. Baseline mạnh là Qwen3-Reranker-4B; BGE là đối chứng chuyên dụng. Không gán mọi trang ViMDoc đúng từ document labels. Không dùng outer-eval cho training/mining/tuning. Dữ liệu đã lộ phục vụ phát triển không trở thành test sạch bằng cách chia lại.

Score cache contract: `pairs_sha256`, `manifest`, `scores` đúng thứ tự/đủ/hữu hạn; manifest có model/base/tokenizer/head/code/deps/input cap/precision. Lỗi/token/timing là sidecar, không silent fallback. Phát sở hữu input contract/launcher, Thanh evaluator, Khương Kev adapter/trainer; phối hợp interface trước khi đổi.

Nghiệm thu: Loader khôi phục đủ adapter/head; không giấu lỗi bằng score 0; score coverage chính xác; test mapping/save-reload có ý nghĩa; train/eval không lẫn; đối chứng initialization cùng protocol.

## Lựa chọn và điểm chưa quyết định

Tận dụng F9 + worker Kev riêng theo hướng đã trao đổi; standalone SciFact chỉ là chẩn đoán, không thay dữ liệu đồ án. Không viết lại cả retrieval pipeline. Nhóm còn phải xác nhận split, data availability và budget sau khi smoke. Brief này không tự chấp thuận một job GPU trả phí.

Code hiện có là F9 tại base; branch bootstrap chỉ thêm tài liệu. Chưa có runner Jev, model training, baseline replay mới, environment installation hoặc model-quality verification.
