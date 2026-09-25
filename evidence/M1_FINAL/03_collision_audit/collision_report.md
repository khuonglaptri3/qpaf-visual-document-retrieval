# M1.6 — Primary-corpus collision audit

**Status: BLOCKED / NOT RUN. Owner: Khương.**

Ba CSV trong thư mục hiện chỉ có header. Không có dữ liệu để kết luận zero
collision, zero duplicate hay zero leakage. Không dùng test fixtures làm corpus.

## Đầu vào cần có

- Primary corpus, nguồn/phiên bản và quyền sử dụng.
- Document/page IDs, source paths, nội dung trang và SHA-256.
- Split manifest theo protocol của Phát và qrels tương ứng.
- Quy tắc canonical ID và aliases; chính sách biểu diễn nội dung để hash.

## Quy trình khi có đầu vào

1. Lập page manifest; kiểm ID duy nhất và tất cả source path/hash tồn tại.
2. So sánh ID và content hash; phân biệt alias hợp lệ, nội dung trùng và ID
   xung đột. Hash file gốc và hash nội dung trang là hai trường khác nhau.
3. Kiểm alias có canonical target, không tạo vòng lặp hoặc target mơ hồ.
4. Kiểm tài liệu/trang/nội dung trùng qua các split theo chính sách protocol.
5. Kiểm qrels trỏ tới query/page tồn tại; ghi inconsistent/orphan records.
6. Ghi từng issue và resolution; giữ mapping trước/sau sửa; chạy lại kiểm tra.
7. Gửi manifest/report/hash cho Thanh review độc lập và Phát tổng hợp G1.

## Điều kiện bàn giao

Excel yêu cầu reviewed page/alias manifest với **zero content collisions**.
Không coi CSV rỗng là đạt. Nếu chưa đáp ứng, ghi blocker và owner; chỉ sign-off
khi có kiểm tra thực tế và review theo protocol. Chưa có người review report này.
