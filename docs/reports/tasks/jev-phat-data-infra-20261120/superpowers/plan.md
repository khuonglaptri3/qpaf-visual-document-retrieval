# Kế hoạch nghiên cứu: Dữ liệu, tái lập retrieval và hạ tầng thực nghiệm

Spec: [spec.md](spec.md). Owner: Phát. Branch: `research/jev-phat-data-infra`.

## Bootstrap đã làm

- [x] Tạo branch từ F9 base `842176c5b707298672629738390a09e222f47e86`, giữ source hiện có.
- [x] Ghi scope, contract, ownership, kế hoạch và giới hạn; kiểm chứng tài liệu trước commit.

## Thực hiện tiếp — chưa chạy

- [ ] Kiểm tra bộ qpaf-lab-share và cache ở máy đã chạy/Modal volume qpaf-lab-rerank; xác minh nội dung thực tế, không mặc định tên volume đồng nghĩa dữ liệu còn đủ. Dữ liệu nhạy cảm để ngoài Git.
- [ ] Cùng nhóm khóa ViDoSeek trước, split theo document/query family phù hợp, cohort/top-20/OCR/input policy; giữ những tập đã dùng chọn model là development/exploratory.
- [ ] Khôi phục raw three-channel scores, query/page mapping, OCR và pairs; phân biệt raw score với mean/per-query metrics. Tính Recall@20 và pool ceiling như chẩn đoán chỉ trên dữ liệu được phép đánh giá.
- [ ] Fit lại các anchor/gate phụ thuộc nhãn trong đúng training folds nếu protocol đổi; tạo cùng pairs và SHA-256 cho Thanh/Khương; không gửi qrels evaluation vào inference worker.
- [ ] Định nghĩa score cache contract và kiểm số pair, finite scores, IDs, hash/model/head revision; giữ sidecar lỗi/token/timing, không silent fallback.
- [ ] Setup môi trường F9 cũ và Kev riêng trên Linux/CUDA; pin source/deps, smoke GPU/memory trước khi chốt tài nguyên; 48 GB là đề xuất khảo sát, không phải bảo đảm fit.
- [ ] Điều phối jobs, lưu checkpoint/raw scores theo run riêng và đo retrieval/rerank/end-to-end riêng; ghép báo cáo sau khi Thanh xác nhận evaluator.

## Phạm vi file dự kiến

- `scripts/prepare_jev_inputs.py` (dự kiến, chưa tạo)
- `src/qpaf/jev/contracts.py` (dự kiến, chưa tạo)
- `scripts/modal_jev_environment.py` (dự kiến, chưa tạo)
- `configs/jev/` (dự kiến, chưa tạo)
- `tests/test_jev_input_contract.py` (dự kiến, chưa tạo)

Trước implementation, người phụ trách đọc spec/plan và hướng dẫn repo, hoàn thiện thiết kế kỹ thuật cụ thể nếu còn thiếu; áp dụng workflow thích hợp và test cho code thay đổi. Những đường dẫn dự kiến không phải scripts đã runnable. Không sửa core lịch sử/receipt đã đóng băng. Khi xong lưu log/raw metrics/checkpoint references trong evidence và cập nhật README hiện hành.
