# Kế hoạch tiếp tục của Thanh

Spec: [spec.md](spec.md). Branch: `research/jev-thanh-baselines`.

## Code đã bàn giao

- [x] Giữ F9 base và brief; tích hợp shared implementation `796410160ee90bbe2a86b6799a76976f958f576f` với lịch sử review còn truy cập được.
- [x] Cung cấp `scripts/run_jev_thanh.py`, cấu hình owner và hướng dẫn chung; demo mặc định dùng stdlib/offline.
- [x] Có hợp đồng dữ liệu/cache/split, evaluator chung, model adapters và đường export/train/dry-run thực tế.
- [x] Kiểm chứng shared toolkit và tiny CPU train/reload; đây là kiểm chứng plumbing, chưa phải kết quả 4B/dữ liệu đồ án.

## Nghiên cứu tiếp trên dữ liệu thật

- [ ] Nhận pool/split/protocol đã khóa từ Phát; kiểm tra raw-score reuse theo pairs hash và coverage.
- [ ] Replay lịch sử bằng F9 full-ranking khi đủ cache; chạy baseline không rerank, BGE và Qwen4B trên protocol mới.
- [ ] Chấm mọi model bằng evaluator chung; lưu per-query nDCG/MRR/Recall, paired delta/CI/W–T–L và chi phí.
- [ ] Phân tích lỗi/headroom và ablation cùng Khương; không kết luận Jev thắng từ demo hoặc mean khác protocol.

Lệnh chính xác và prerequisites: [runbook chung](../../jev-runnable-team-kit-20261120/README.md). Không sửa core/receipts lịch sử. Không dùng document labels làm page labels; không dùng outer-eval để train/tune. Budget training của hai initialization phải giống nhau; tránh đúng mười effective optimizer steps do giới hạn scheduler upstream đã ghi trong runbook.
