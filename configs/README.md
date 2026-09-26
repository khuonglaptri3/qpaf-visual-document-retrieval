# Experiment configurations

`m1.1/vidoseek.toml` là preset cho implementation Oracle mới trên Modal, có
dataset/model revision, preprocessing, weight sets, bootstrap và tài nguyên.
Xem [hướng dẫn M1.1](../docs/m1.1-modal-oracle.md). Preset không phải cấu hình
của báo cáo Oracle cũ hoặc protocol learned QARF/QPAF đã được nhóm phê duyệt.
Mỗi run ghi config đã resolve, hash và commit/code hashes.

`m1.2/core.toml` cấu hình schema 13 features, kiến trúc/temperature của gate,
loss và fixture kiểm chứng CPU. Cùng một config tạo QARF và QPAF; chỉ khác
granularity `query`/`page`. Xem [đặc tả M1.2](../docs/m1.2-method-core.md).
