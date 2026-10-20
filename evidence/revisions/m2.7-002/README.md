# M2.7 — Matched config và kiểm chứng parity (revision 002)

Owner: Tấn Phát. Đặc tả: [`m2.7-matched-configs.md`](../../../docs/03_method/m2.7-matched-configs.md).

**Thay thế [m2.7-001](../m2.7-001/README.md).** Review độc lập toàn nhánh phát hiện
kiểm tra data order của 001 chỉ so `(valid_queries, pairs)` theo step; trên
fixture tổng hợp, hai giá trị này không đổi khi hoán vị query, nên 001 **chưa**
chứng minh thứ tự batch giống nhau. Revision 002 so trực tiếp query IDs của từng
batch huấn luyện qua 2 epoch, khóa ba seed theo `seed_policy.md`, kiểm
`experiment_id` của base khớp manifest, và hash toàn bộ mã trên đường huấn luyện.
File 001 giữ nguyên, không ghi đè.

`verification.json` ghi: SHA-256 của `configs/m2.7/shared_base.toml` và
`configs/m2.7/matched.json`; base chỉ khác M2.4 ở `experiment_id`; với ba seed
20260820/21/22, QARF và QPAF chỉ khác `gate_granularity` (`query` vs `page`);
tham số khởi tạo giống từng bit (42 tham số); 4 batch huấn luyện (2 epoch) có
cùng query IDs theo cùng thứ tự; hash của split manifest M2.1-002 và M2.5 freeze
đã kiểm lại; SHA-256 của 11 file mã (M2.7, M2.4, M1.2 và hai script); trần
wall-time 60 phút.

Trạng thái `FROZEN_CONFIG_PENDING_M2.8_INPUTS`: score cache, qrels và candidate
set còn `PENDING_M2.8`. Independent review `PENDING` (M2.10). Không có kết quả
retrieval nào ở đây.

File là create-once, sinh bằng
`python scripts/verify_m27_matched.py --output evidence/revisions/m2.7-002/verification.json`
từ code đã commit. Sửa config hoặc mã đã hash thì tạo revision mới, không ghi đè.
