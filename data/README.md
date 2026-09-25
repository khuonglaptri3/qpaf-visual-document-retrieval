# Data access

Chưa có corpus trong workspace này. Không chọn benchmark thay cho protocol.

Khi có dữ liệu: ghi nguồn, phiên bản, điều kiện sử dụng, cách lấy dữ liệu,
local storage path, ID manifest, split manifest, qrels và SHA-256. Đặt payload
ở `data/raw/`, `data/processed/`, `data/external/` hoặc storage ngoài repo.
Các thư mục payload này được Git bỏ qua; manifest nhỏ lưu trong `manifests/`.

Audit CLI kiểm kê payload hiện có dưới `data/` dù Git không track payload.
Dữ liệu ngoài root chưa được công cụ này kiểm kê; phải khai báo vị trí và có
bước kiểm chứng riêng trước khi đóng gap. Không dùng fixture trong `tests/`
để tuyên bố kiểm tra corpus đã hoàn tất.
