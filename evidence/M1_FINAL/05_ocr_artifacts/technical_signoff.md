# M1 Technical Sign-off

**Status: NOT SIGNED. Planned date: 27/09/2026. Owner: Trần Đình Khương.**

Chưa xác nhận technical freeze. Đây là danh sách điều kiện để Khương review,
không phải chữ ký hoặc sự phê duyệt của Khương/Thanh/Phát.

- [ ] M1.4 inventories phản ánh research assets thật; gap được xử lý/ghi rõ.
- [ ] Revision Git, hash và file manifest được kiểm chứng.
- [ ] M1.6 kiểm corpus thật và đạt tiêu chí collision/alias/split/qrels.
- [ ] OCR calibration và failure thresholds đủ căn cứ, đã review.
- [ ] Artifact namespace thống nhất với registry và protocol.
- [ ] Technical blocker từ G1 được xử lý và có evidence mới.
- [ ] Thanh hoàn tất independent QA; Phát có bộ evidence cho Final G1.

Blocker hiện tại: chưa có source nghiên cứu/corpus/config/run cũ trong
workspace; chưa có calibration, frozen protocol, registry hoặc G1 review.
Không chuyển sang SIGNED chỉ dựa trên số file được tạo hoặc unit tests pass.
