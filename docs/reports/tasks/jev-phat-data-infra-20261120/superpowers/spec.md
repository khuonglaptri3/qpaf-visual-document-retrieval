# Spec: Dữ liệu, tái lập retrieval và hạ tầng thực nghiệm

Owner: **Phát**. Branch: `research/jev-phat-data-infra`. Base: `842176c5b707298672629738390a09e222f47e86`.
Ngày bắt đầu branch/brief: 2026-11-20. Status: đã có code runnable; nghiên cứu model/dữ liệu thật còn chờ thực hiện.

## Câu hỏi và phạm vi

Khôi phục/reuse được artifact nào của F9, candidate pool còn headroom nào, và setup chung nào cho phép so model đúng protocol với chi phí đo được?

Data/cache inventory; input/split/score contract; OCR/query/page/document mapping; cùng top-20; môi trường F9/Kev riêng; launcher/storage/chi phí và tích hợp. Không tự đổi phương pháp hoặc nhãn đánh giá.

Đầu ra: Inventory cache có/còn thiếu; data/split/pairs manifests và SHA-256; pairs.json; input/score contract; môi trường/launcher pin version; GPU/token/time/cost logs; run manifests và bản tích hợp.

## Ràng buộc chung

ViDoSeek text/OCR trước; cùng split/cohort/top-20/pairs hash. Baseline mạnh là Qwen3-Reranker-4B; BGE là đối chứng chuyên dụng. Không gán mọi trang ViMDoc đúng từ document labels. Không dùng outer-eval cho training/mining/tuning. Dữ liệu đã lộ phục vụ phát triển không trở thành test sạch bằng cách chia lại.

Score cache contract: `pairs_sha256`, `manifest`, `scores` đúng thứ tự/đủ/hữu hạn; manifest có model/base/tokenizer/head/code/deps/input cap/precision. Lỗi/token/timing là sidecar, không silent fallback. Phát sở hữu input contract/launcher, Thanh evaluator, Khương Kev adapter/trainer; phối hợp interface trước khi đổi.

Nghiệm thu: Input mapping/hash và cohort rõ; cùng pool cho mọi model; cache chỉ reuse khi tương thích; nhãn không lẫn; jobs có resume/manifests/cost evidence; baseline và Kev giữ môi trường riêng.

## Lựa chọn và điểm chưa quyết định

Tận dụng F9 + worker Kev riêng theo hướng đã trao đổi; standalone SciFact chỉ là chẩn đoán, không thay dữ liệu đồ án. Không viết lại cả retrieval pipeline. Nhóm còn phải xác nhận split, data availability và budget sau khi smoke. Brief này không tự chấp thuận một job GPU trả phí.

Đã tích hợp toolkit chung từ commit `796410160ee90bbe2a86b6799a76976f958f576f`. Xem [spec triển khai](../../jev-runnable-team-kit-20261120/superpowers/spec.md) và [kết quả kiểm chứng](../../jev-runnable-team-kit-20261120/README.md). Có CLI dữ liệu/evaluation, BGE/Qwen/Kev adapters, train-only export, trainer chính thức và local/Modal worker. Tiny CPU integration đã chạy; benchmark 4B trên dữ liệu đồ án và GPU chưa chạy.
