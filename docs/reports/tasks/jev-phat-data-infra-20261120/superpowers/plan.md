# Kế hoạch tiếp tục của Phát

Spec: [spec.md](spec.md). Branch: `research/jev-phat-data-infra`.

## Code đã bàn giao

- [x] Giữ F9 base và brief; tích hợp shared implementation `796410160ee90bbe2a86b6799a76976f958f576f` với lịch sử review còn truy cập được.
- [x] Cung cấp `scripts/run_jev_phat.py`, cấu hình owner và hướng dẫn chung; demo mặc định dùng stdlib/offline.
- [x] Có hợp đồng dữ liệu/cache/split, evaluator chung, model adapters và đường export/train/dry-run thực tế.
- [x] Kiểm chứng shared toolkit và tiny CPU train/reload; đây là kiểm chứng plumbing, chưa phải kết quả 4B/dữ liệu đồ án.

## Nghiên cứu tiếp trên dữ liệu thật

- [ ] Khôi phục OCR/query/page/document mapping và raw channel/reranker cache riêng; lập inventory có/còn thiếu.
- [ ] Cùng nhóm khóa split/group/cohort/top-20 và input policy; tạo pairs/score manifests cùng hash, kiểm tra coverage.
- [ ] Chuẩn bị môi trường và Volume riêng cho job đồng thời; ghi GPU/token/time/cost, điều phối frozen và training pilot.
- [ ] Tích hợp outputs chung của Thanh/Khương; giữ raw pairs, revisions và log để tái lập.

Lệnh chính xác và prerequisites: [runbook chung](../../jev-runnable-team-kit-20261120/README.md). Không sửa core/receipts lịch sử. Không dùng document labels làm page labels; không dùng outer-eval để train/tune. Budget training của hai initialization phải giống nhau; tránh đúng mười effective optimizer steps do giới hạn scheduler upstream đã ghi trong runbook.
