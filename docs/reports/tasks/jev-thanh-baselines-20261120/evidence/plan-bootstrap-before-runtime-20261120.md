# Kế hoạch nghiên cứu: Reranker baseline và đánh giá độc lập

Spec: [spec.md](spec.md). Owner: Thanh. Branch: `research/jev-thanh-baselines`.

## Bootstrap đã làm

- [x] Tạo branch từ F9 base `842176c5b707298672629738390a09e222f47e86`, giữ source hiện có.
- [x] Ghi scope, contract, ownership, kế hoạch và giới hạn; kiểm chứng tài liệu trước commit.

## Thực hiện tiếp — chưa chạy

- [ ] Đọc F5/F7/F9 source; F9 blend top-20 là 2+(1−λ)minmax(base)+λminmax(rerank), không chỉ sort raw reranker scores. Phân biệt ảnh hưởng shortlist, model và blend.
- [ ] Nhận input/split contract của Phát; khôi phục BGE/Qwen raw scores theo pairs/model/OCR hash; nếu thiếu pair thì chạy bổ sung, không dùng mean JSON thay raw cache.
- [ ] Replay lịch sử chỉ khi protocol giữ nguyên; ViDoSeek dev F7 Qwen4B ~0.9220, F9 ~0.9190 là mốc lịch sử, không là kết quả sạch cho một split training mới.
- [ ] Trên protocol mới đã khóa, đánh giá lại baseline không rerank, BGE và Qwen4B; giữ cùng candidate/input policy và ghi truncation/token nếu native APIs khác nhau.
- [ ] Nhận score Kev frozen/fine-tuned/base-control của Khương; kiểm exact coverage, unique IDs, finite values và hashes; không bỏ query lỗi hoặc dùng nhãn để đổi pool.
- [ ] Báo raw-score ranking và blend riêng; λ/checkpoint selection chỉ trên train/validation hợp lệ. Dùng paired query/group uncertainty phù hợp dependence và báo rõ exploratory/heldout exposure.
- [ ] Viết bảng Δ so baseline mạnh, CI/W–T–L, error cases và quality–cost trade-off; kết luận tăng chất lượng, tiết kiệm chi phí có kiểm chứng, hoặc chưa có lợi ích.

## Phạm vi file dự kiến

- `scripts/evaluate_jev_rerank.py` (dự kiến, chưa tạo)
- `src/qpaf/jev/evaluation.py` (dự kiến, chưa tạo)
- `tests/test_jev_evaluation.py` (dự kiến, chưa tạo)

Trước implementation, người phụ trách đọc spec/plan và hướng dẫn repo, hoàn thiện thiết kế kỹ thuật cụ thể nếu còn thiếu; áp dụng workflow thích hợp và test cho code thay đổi. Những đường dẫn dự kiến không phải scripts đã runnable. Không sửa core lịch sử/receipt đã đóng băng. Khi xong lưu log/raw metrics/checkpoint references trong evidence và cập nhật README hiện hành.
