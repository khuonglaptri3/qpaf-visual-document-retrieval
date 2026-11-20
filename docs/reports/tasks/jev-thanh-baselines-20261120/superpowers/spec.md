# Spec: Reranker baseline và đánh giá độc lập

Owner: **Thanh**. Branch: `research/jev-thanh-baselines`. Base: `842176c5b707298672629738390a09e222f47e86`.
Ngày bắt đầu branch/brief: 2026-11-20. Status: đã có code runnable; nghiên cứu model/dữ liệu thật còn chờ thực hiện.

## Câu hỏi và phạm vi

Kev có cải thiện nDCG/MRR/Recall hoặc hiệu quả chi phí so với BGE và Qwen4B khi giữ cùng cohort, pool và protocol không?

Baseline không rerank, BGE-v2-m3, Qwen3-Reranker-4B; raw-score reuse và baseline replay; evaluator chung cho tất cả model; score thuần/blend, uncertainty và phân tích lỗi.

Đầu ra: Baseline không rerank; bge_scores.json; qwen4b_scores.json; per-query metric table; nDCG@10/MRR@10/Recall@10/20; paired Δ/CI/W–T–L; failure/latency/cost analysis.

## Ràng buộc chung

ViDoSeek text/OCR trước; cùng split/cohort/top-20/pairs hash. Baseline mạnh là Qwen3-Reranker-4B; BGE là đối chứng chuyên dụng. Không gán mọi trang ViMDoc đúng từ document labels. Không dùng outer-eval cho training/mining/tuning. Dữ liệu đã lộ phục vụ phát triển không trở thành test sạch bằng cách chia lại.

Score cache contract: `pairs_sha256`, `manifest`, `scores` đúng thứ tự/đủ/hữu hạn; manifest có model/base/tokenizer/head/code/deps/input cap/precision. Lỗi/token/timing là sidecar, không silent fallback. Phát sở hữu input contract/launcher, Thanh evaluator, Khương Kev adapter/trainer; phối hợp interface trước khi đổi.

Nghiệm thu: Một evaluator cho toàn bộ model; cùng cohort/pool; metrics có per-query evidence và uncertainty; không silent missing-query skip; không chép mean khác protocol; không tuyên bố Jev thắng khi bằng chứng chưa đủ.

## Lựa chọn và điểm chưa quyết định

Tận dụng F9 + worker Kev riêng theo hướng đã trao đổi; standalone SciFact chỉ là chẩn đoán, không thay dữ liệu đồ án. Không viết lại cả retrieval pipeline. Nhóm còn phải xác nhận split, data availability và budget sau khi smoke. Brief này không tự chấp thuận một job GPU trả phí.

Đã tích hợp toolkit chung từ commit `796410160ee90bbe2a86b6799a76976f958f576f`. Xem [spec triển khai](../../jev-runnable-team-kit-20261120/superpowers/spec.md) và [kết quả kiểm chứng](../../jev-runnable-team-kit-20261120/README.md). Có CLI dữ liệu/evaluation, BGE/Qwen/Kev adapters, train-only export, trainer chính thức và local/Modal worker. Tiny CPU integration đã chạy; benchmark 4B trên dữ liệu đồ án và GPU chưa chạy.
