# Kế hoạch tiếp tục của Khương

Spec: [spec.md](spec.md). Branch: `research/jev-khuong-model`.

## Code đã bàn giao

- [x] Giữ F9 base và brief; tích hợp shared implementation `796410160ee90bbe2a86b6799a76976f958f576f` với lịch sử review còn truy cập được.
- [x] Cung cấp `scripts/run_jev_khuong.py`, cấu hình owner và hướng dẫn chung; demo mặc định dùng stdlib/offline.
- [x] Có hợp đồng dữ liệu/cache/split, evaluator chung, model adapters và đường export/train/dry-run thực tế.
- [x] Kiểm chứng shared toolkit và tiny CPU train/reload; đây là kiểm chứng plumbing, chưa phải kết quả 4B/dữ liệu đồ án.

## Nghiên cứu tiếp trên dữ liệu thật

- [ ] Nhận pairs/split/page-level train labels đã khóa từ Phát; kiểm tra ví dụ query–OCR.
- [ ] Chạy Kev-4B frozen trên cùng pairs với BGE/Qwen4B; lưu score/token/time/VRAM thực tế.
- [ ] Smoke GPU forward/backward và save/reload; fine-tune LoRA/head từ Kev và cùng kiến trúc từ Qwen3.5-4B-Base với cùng data/loss/budget.
- [ ] Chọn checkpoint bằng train/validation, gửi scores cho Thanh; viết ablation frozen/adapted và base/Kev.

Lệnh chính xác và prerequisites: [runbook chung](../../jev-runnable-team-kit-20261120/README.md). Không sửa core/receipts lịch sử. Không dùng document labels làm page labels; không dùng outer-eval để train/tune. Budget training của hai initialization phải giống nhau; tránh đúng mười effective optimizer steps do giới hạn scheduler upstream đã ghi trong runbook.
