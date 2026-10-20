# M2.7 — Matched config và kiểm chứng parity

Owner: Tấn Phát. Đặc tả: [`m2.7-matched-configs.md`](../../../docs/03_method/m2.7-matched-configs.md).

`verification.json` ghi: SHA-256 của `configs/m2.7/shared_base.toml` và
`configs/m2.7/matched.json`; base chỉ khác M2.4 ở `experiment_id`; với ba seed
20260820/21/22, QARF và QPAF chỉ khác `gate_granularity` (`query` vs `page`);
tham số khởi tạo giống từng bit (42 tham số) và thứ tự batch giống nhau trên
fixture tổng hợp; hash của split manifest M2.1-002 và M2.5 freeze đã kiểm lại;
SHA-256 của mã nguồn kiểm tra; trần wall-time 60 phút.

Trạng thái `FROZEN_CONFIG_PENDING_M2.8_INPUTS`: score cache, qrels và candidate
set còn `PENDING_M2.8`. Independent review `PENDING` (M2.10). Không có kết quả
retrieval nào ở đây.

File là create-once, sinh bằng
`python scripts/verify_m27_matched.py --output evidence/revisions/m2.7-001/verification.json`
từ code đã commit. Sửa config hoặc mã đã hash thì tạo revision mới, không ghi đè.
