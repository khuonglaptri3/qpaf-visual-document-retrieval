# Kế hoạch nghiên cứu: Kev decision model và domain fine-tuning

Spec: [spec.md](spec.md). Owner: Khương. Branch: `research/jev-khuong-model`.

## Bootstrap đã làm

- [x] Tạo branch từ F9 base `842176c5b707298672629738390a09e222f47e86`, giữ source hiện có.
- [x] Ghi scope, contract, ownership, kế hoạch và giới hạn; kiểm chứng tài liệu trước commit.

## Thực hiện tiếp — chưa chạy

- [ ] Đọc loader/trainer Kev tại commit 5e22da2be8ecb2f38790d81d87bb55b0be61a6e2; pin checkpoint jaredpalmer/kev-4b revision 6cfce5c2fa4b4bd64026336ab649c5ca78857d52 cùng base/tokenizer/head. Không dùng generic loader làm mất head.
- [ ] Nhận cặp query–OCR và protocol của Phát; làm ví dụ đọc tay, ghi lỗi rõ, kiểm score đủ/hữu hạn/đúng thứ tự; dùng Noul relevance, không sinh đáp án dài.
- [ ] Chạy Kev-4B frozen trên cùng pool với BGE/Qwen4B, xuất score contract chung cho Thanh; ghi token/truncation/precision/runtime và peak memory.
- [ ] Tạo training records chỉ từ train của ViDoSeek; chia group trước mining/pair creation; không dùng nhãn outer-eval để mine negatives, tune hoặc teacher-label train.
- [ ] Smoke 32–64 record: forward/backward, finite adapter/head gradients, save/reload score agreement và đo VRAM; chưa coi smoke là bằng chứng chất lượng.
- [ ] Pilot LoRA/head và base-initialized cùng kiến trúc/data/loss/budget; chọn checkpoint trong train/validation, xuất score cho evaluator của Thanh.
- [ ] Viết phương pháp và ablation frozen→adapted/base→Kev; chỉ mở rộng 0.8B, QLoRA hoặc joint-context sau khi lõi được kiểm chứng.

## Phạm vi file dự kiến

- `src/qpaf/jev/adapter.py` (dự kiến, chưa tạo)
- `scripts/modal_jev_rerank.py` (dự kiến, chưa tạo)
- `scripts/train_jev_reranker.py` (dự kiến, chưa tạo)
- `tests/test_jev_adapter_contract.py` (dự kiến, chưa tạo)

Trước implementation, người phụ trách đọc spec/plan và hướng dẫn repo, hoàn thiện thiết kế kỹ thuật cụ thể nếu còn thiếu; áp dụng workflow thích hợp và test cho code thay đổi. Những đường dẫn dự kiến không phải scripts đã runnable. Không sửa core lịch sử/receipt đã đóng băng. Khi xong lưu log/raw metrics/checkpoint references trong evidence và cập nhật README hiện hành.
