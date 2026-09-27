# Research results

Đã nhận [báo cáo Oracle M1.1](m1.1/README.md) và lưu file Word gốc cùng
hash tại `m1.1/reference/`. Đây là báo cáo tổng hợp được cung cấp;
code/config/cache/output từng query của run gốc chưa có trong repo.

M1.1 đã được chấp nhận ở phạm vi báo cáo khả thi; chưa xác minh tái lập corpus
thật. Run mới của Thanh dùng `m1.1/<run-id>/`.

[Bằng chứng method core M1.2](m1.2/README.md) đã có tại `m1.2/<run-id>/`,
gồm feature/gate/fusion/loss/gradient và learning trace trên fixture tổng hợp.
Implementation và kiểm chứng cục bộ hoàn thành; review của thành viên khác
còn chờ. [Đối chiếu trạng thái](../docs/m1.1-m1.2-status.md) ghi rõ từng tiêu chí.
Hướng dẫn bàn giao nằm trong
[README chính](../README.md) và [trạng thái M1](../docs/m1-restart-handoff.md).

Chỉ version bảng kết quả nhỏ khi truy được experiment ID, run ID, config,
commit, data/split/hash, lệnh chạy và output. Checkpoint, index và output lớn
lưu ngoài Git. Kiểm tra unit test của audit không phải thí nghiệm QARF/QPAF.
Đầu ra run chưa có liên kết đầy đủ phải ghi PROVENANCE_UNVERIFIED.
